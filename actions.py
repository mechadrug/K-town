"""统一动作结算层（v5 rebuild-plan §2.1 ActionResolver）。

所有玩家/NPC 动作必须经 ActionResolver.resolve() 结算，调用方不得自行扣 AP 或推进时间：
- 校验（actor 存在、目标同地点、目标地点合法、夜间限制、AP 足够）
- 扣费（唯一扣费点：玩家白天扣 AP / 夜晚扣 night_ap；NPC 不扣）
- 时间推进（hours > 0 时 advance；失败动作不推进）
- 日志（daily_agent_logs + log_player_action）
- 结果（changes 带 source 可追溯；story_beats / next_observation 供日报与前端）

不依赖 LLM；无异步；可直接被测试驱动。
"""
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models import AgentTask, PlayerAction
from emotions import apply_event_emotion, learn_habit

# 动作成本：AP（玩家白天扣）与推进小时数
ACTION_COSTS = {
    "move": {"ap": 1, "hours": 1},
    "work": {"ap": 1, "hours": 1},
    "talk": {"ap": 1, "hours": 1},
    "investigate": {"ap": 2, "hours": 2},
    "observe": {"ap": 0, "hours": 0},
    "sleep": {"ap": 0, "hours": 0},
    "rest": {"ap": 0, "hours": 0},  # 特殊：推进到次日清晨
    "trade": {"ap": 1, "hours": 1},
    "conflict": {"ap": 0, "hours": 0},
    "add_claim": {"ap": 0, "hours": 0},
    "request_respond": {"ap": 0, "hours": 0},  # 实际成本由请求选项声明
}

# 需要同地点目标居民的动作
_REQUIRE_TARGET_AGENT = {"talk", "conflict", "trade"}
# 目标必须是合法地点的动作
_REQUIRE_TARGET_LOCATION = {"move"}
# 玩家可用的常规动作（其余如 sleep 只在 NPC 决策中出现）
_PLAYER_ACTIONS = {"move", "work", "talk", "investigate", "observe", "rest", "trade"}

NIGHT_AP_ACTIONS = {"move", "work", "talk", "investigate", "observe"}


@dataclass
class Action:
    actor_id: str
    kind: str
    target_id: str = ""
    target_location: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Change:
    target: str
    field: str
    before: Any
    after: Any
    source: str


@dataclass
class ActionResult:
    accepted: bool
    cost: int = 0
    hours: int = 0
    changes: List[Change] = field(default_factory=list)
    story_beats: List[str] = field(default_factory=list)
    next_observation: Optional[str] = None
    error_code: Optional[str] = None
    result: str = ""
    request_id: Optional[str] = None


class ActionResolver:
    """统一动作入口：校验 → 扣费 → 执行 → 日志。"""

    def __init__(self, engine):
        self.engine = engine
        self.world = engine.world
        self.knowledge = engine.knowledge
        self.agents = engine.agents

    # ------------------------------------------------------------ 公共入口

    def resolve(self, actor, action: Action) -> ActionResult:
        """结算一个动作。失败动作不扣 AP、不推进时间。"""
        r = ActionResult(accepted=False)
        if action.kind not in ACTION_COSTS:
            r.error_code = "unknown_action"
            r.result = f"未知操作：{action.kind}"
            return r
        if actor is None:
            r.error_code = "no_actor"
            r.result = "找不到执行者"
            return r

        is_player = actor.identity.role.value == 'player'

        # ---- 校验 ----
        valid = self._validate(actor, action, is_player)
        if valid is not None:
            return valid

        # ---- 扣费（唯一扣费点） ----
        if action.kind == "rest" and is_player:
            hours = self._hours_until_next_wake()
            r.hours = hours
            self._log_action(actor, action, "你睡了一觉，迎来了新的一天")
            self.engine.advance(hours)
            r.accepted = True
            r.result = "你睡了一觉，迎来了新的一天"
            r.next_observation = "清晨，小镇在雨后的微光中醒来。"
            return r
        if action.kind == "rest":
            # NPC 决策中的 rest = 原地恢复（与 _handle_action 原语义一致）
            return self._execute(actor, action, r, is_player)

        cost = ACTION_COSTS[action.kind]["ap"]
        hours = ACTION_COSTS[action.kind]["hours"]
        if action.kind == "request_respond":
            # 成本由请求选项声明（校验在 _validate 中先行，失败不扣费）
            req, opt = self._find_request_option(action)
            if req is None or opt is None:
                return self._fail(r, "no_request", "找不到这个请求")
            cost = opt.cost_ap
            hours = opt.cost_hours
        # 请求选项成本 ≥1 时也走夜间通道
        if is_player and action.kind in NIGHT_AP_ACTIONS and self._is_night():
            if cost > 0:
                if actor.state.night_ap < cost:
                    return self._fail(r, "night_ap", "夜深了，镇上的人都睡了。你虽有古玉佩护佑，却也困倦难当——点「休息」吧。")
                actor.state.night_ap -= cost
                self._record_change(r, actor.identity.id, "night_ap", actor.state.night_ap + cost, actor.state.night_ap, action.kind)
        elif is_player and cost > 0:
            if actor.state.ap < cost:
                return self._fail(r, "ap_shortage", f"行动力不足（剩余{actor.state.ap}点，需要{cost}点）")
            actor.state.ap -= cost
            self._record_change(r, actor.identity.id, "ap", actor.state.ap + cost, actor.state.ap, action.kind)
        r.cost = cost
        r.hours = hours
        # 只有玩家动作排队推进时间；NPC 动作的时间已在 step() 的当前 tick 内消耗，
        # 若也 advance() 会与 run() 循环互相喂食 → 无限推进（v5 验收：任一动作只结算一次）
        if hours > 0 and is_player:
            self.engine.advance(hours)

        # ---- 执行 ----
        return self._execute(actor, action, r, is_player)

    # ------------------------------------------------------------ 校验

    def _validate(self, actor, action: Action, is_player: bool) -> Optional[ActionResult]:
        if action.kind in _REQUIRE_TARGET_AGENT and action.target_id:
            target = next((a for a in self.agents if a.identity.id == action.target_id), None)
            if target is None:
                return self._fail(None, "no_target", "找不到目标居民")
            if target.state.location != actor.state.location:
                return self._fail(None, "target_not_here", f"{target.identity.name}不在这里")
        if action.kind in _REQUIRE_TARGET_LOCATION and action.target_location:
            if action.target_location not in self.world.locations:
                return self._fail(None, "bad_location", "目标地点不存在")
        if action.kind == "request_respond":
            req, opt = self._find_request_option(action)
            if req is None:
                return self._fail(None, "no_request", "找不到这个请求")
            if opt is None:
                return self._fail(None, "no_option", "请求选项不存在")
            # 截止日到期 → 自动过期（deadline 真实生效）
            if req.status == "active" and self.engine.current_day > req.deadline:
                req.status = "expired"
            if req.status != "active":
                return self._fail(None, "request_closed", "这个请求已经结束了")
            if opt.requires == "wilderness" and actor.state.location != "wilderness":
                return self._fail(None, "wrong_location", f"需要到荒野去{opt.label}（{opt.requires_cn}）")
            if opt.requires == "workshop" and actor.state.location != "workshop":
                return self._fail(None, "wrong_location", "需要把干木料送到工坊（莉娜在那里）")
            if opt.requires == "dry_wood":
                if "dry_wood" not in actor.state.inventory:
                    return self._fail(None, "missing_item", "你还没有干木料——先去荒野收集吧")
                if actor.state.location != req.location:
                    return self._fail(None, "wrong_location", "需要把干木料送到工坊（莉娜在那里）")
        return None

    def _find_request_option(self, action: Action):
        """按 request_id/option 定位请求与选项（校验与执行共用）。"""
        req = next((q for q in getattr(self.engine, 'requests', []) if q.id == action.payload.get("request_id")), None)
        if req is None:
            return None, None
        opt = next((o for o in req.options if o.id == action.payload.get("option")), None)
        return req, opt

    def _fail(self, r: Optional[ActionResult], code: str, msg: str) -> ActionResult:
        if r is None:
            r = ActionResult(accepted=False)
        r.error_code = code
        r.result = msg
        return r

    def _is_night(self) -> bool:
        hour = self.world.state.tick % self.engine.day_length
        return not (self.engine.wake_hour <= hour < self.engine.wake_hour + self.engine.waking_hours)

    def _hours_until_next_wake(self) -> int:
        hour = self.world.state.tick % self.engine.day_length
        ws = self.engine.wake_hour
        return (ws - hour) % self.engine.day_length or self.engine.day_length

    # ------------------------------------------------------------ 执行

    def _execute(self, actor, action: Action, r: ActionResult, is_player: bool) -> ActionResult:
        t = action.kind
        # 归一化：craft/gather 类动作视为劳作
        if t in ("craft_tool", "craft_furniture", "gather_food", "gather_material"):
            t = "work"
        tgt = action.target_id or action.target_location
        loc_cn = actor.get_location_cn(actor.state.location)

        # 记录"正在做的事"（档案/对话语境显示；休息/观察时清空）
        if t in ("work", "move", "talk", "investigate", "trade"):
            actor.state.current_task = AgentTask(description=f"在{loc_cn}忙活着", location=actor.state.location)
        elif t in ("rest", "sleep", "observe"):
            actor.state.current_task = None

        gold_before = actor.state.gold

        if t == "move" and tgt:
            self.world.remove_agent_from_location(actor.identity.id, actor.state.location)
            self._record_change(r, actor.identity.id, "location", actor.state.location, tgt, t)
            actor.state.location = tgt
            self.world.add_agent_to_location(actor.identity.id, tgt)
            actor.state.energy -= 5
            apply_event_emotion(actor, "move")
            self._append_log(actor, f"移动到了{self._loc_cn(tgt)}")

        elif t == "work":
            actor.state.energy -= 8
            role = actor.identity.role.value
            work_knowledge = {
                "blacksmith": ("锻造", "在工坊锻造了优质的工具"),
                "carpenter": ("木工", "在工坊制作了精美的木家具"),
                "forager": ("采集", "在森林里采集了新鲜的食材和草药"),
                "farmer": ("农耕", "在田地里辛勤耕种，期待丰收"),
                "scout": ("探索", "探索了荒野的未知区域，绘制了新地图"),
                "healer": ("医疗", "在学校救治了病人，配制药剂"),
                "miner": ("采矿", "在矿洞深处挖掘出珍贵的矿石"),
                "merchant": ("商业", "在广场打理生意，了解市场行情"),
                "elder": ("知识", "给年轻人们讲述了古老的传说和智慧"),
                "teacher": ("教育", "教导孩子们读书写字，传播知识"),
                "storyteller": ("故事", "给大家讲述精彩的冒险故事"),
            }
            if role in work_knowledge:
                subject, desc = work_knowledge[role]
                self.knowledge.observe(actor.identity.id, subject, desc, actor.state.location)

            if role in ("blacksmith", "carpenter"):
                self._record_change(r, actor.identity.id, "gold", actor.state.gold, actor.state.gold + 5, t)
                actor.state.gold += 5
                actor.state.inventory.append("tool")
            elif role in ("forager", "farmer"):
                self._record_change(r, actor.identity.id, "gold", actor.state.gold, actor.state.gold + 3, t)
                actor.state.gold += 3
                actor.state.inventory.append("food")
                self.world.record_supply('food', 3)
            elif role == "scout":
                self._record_change(r, actor.identity.id, "gold", actor.state.gold, actor.state.gold + 4, t)
                actor.state.gold += 4
            elif role == "healer":
                self._record_change(r, actor.identity.id, "gold", actor.state.gold, actor.state.gold + 4, t)
                actor.state.gold += 4
            elif role == "miner":
                self._record_change(r, actor.identity.id, "gold", actor.state.gold, actor.state.gold + 5, t)
                actor.state.gold += 5
            elif role == "player":
                loc_gold = {"wilderness": 6, "mine": 7, "workshop": 5, "square": 4, "school": 4}
                self._record_change(r, actor.identity.id, "gold", actor.state.gold, actor.state.gold + loc_gold.get(actor.state.location, 4), t)
                actor.state.gold += loc_gold.get(actor.state.location, 4)
                self._append_log(actor, f"在{loc_cn}打工挣了些金币")
            else:
                self._record_change(r, actor.identity.id, "gold", actor.state.gold, actor.state.gold + 2, t)
                actor.state.gold += 2

            # 知识驱动发展：劳作中精进技能
            skill = actor.identity.skills.get(role, 0)
            if skill > 0:
                actor.state.gold += min(3, skill)
            if random.random() < 0.12:
                actor.identity.skills[role] = skill + 1
                self._append_log(actor, f"{actor.get_role_cn(role)}技能提升到{skill + 1}级，手艺更精进了")

            apply_event_emotion(actor, "work_success")
            learn_habit(actor, "work", "work", 1.0)
            self._append_log(actor, f"在{loc_cn}工作")

        elif t == "rest":
            actor.state.energy = min(100, actor.state.energy + 10)
            apply_event_emotion(actor, "rest")
            learn_habit(actor, "tired", "rest", 1.0)
            self._append_log(actor, f"在{loc_cn}休息恢复体力")

        elif t == "sleep":
            actor.state.energy = min(100, actor.state.energy + 20)
            apply_event_emotion(actor, "sleep")
            self._append_log(actor, "睡觉休息")

        elif t == "talk":
            actor.state.energy -= 2
            actor.state.gold += 1
            claims = self.knowledge.agent_knowledge(actor.identity.id)
            if claims:
                top = max(claims, key=lambda c: c.confidence)
                if top.confidence > 0.5:
                    for other in self.agents:
                        if other.identity.id != actor.identity.id and other.state.location == actor.state.location:
                            self.knowledge.propagate(top.id, actor.identity.id, other.identity.id, 0.7)
            for other in self.agents:
                if other.identity.id == actor.identity.id:
                    continue
                if other.state.location == actor.state.location:
                    agreeableness = actor.identity.personality.get('agreeableness', 0.5)
                    extraversion = actor.identity.personality.get('extraversion', 0.5)
                    tie_change = 0.5 + agreeableness * 0.5 + extraversion * 0.3
                    before = actor.state.social_ties.get(other.identity.id, 0)
                    actor.state.social_ties[other.identity.id] = before + tie_change
                    self._record_change(r, f"{actor.identity.id}:{other.identity.id}", "tie", before, actor.state.social_ties[other.identity.id], t)
                    other_tie = other.state.social_ties.get(actor.identity.id, 0)
                    other.state.social_ties[actor.identity.id] = other_tie + tie_change * 0.7
            apply_event_emotion(actor, "talk")
            learn_habit(actor, "socialize", "talk", 1.0)
            self._append_log(actor, f"和{loc_cn}的人聊天")

        elif t == "trade":
            if actor.identity.role.value == "merchant":
                actor.state.gold += 8
            else:
                actor.state.gold += 2
            self._append_log(actor, f"在{loc_cn}进行交易")

        elif t == "conflict":
            actor.state.energy -= 5
            target = next((a for a in self.agents if a.identity.id == tgt), None)
            if target:
                actor.state.social_ties[tgt] = actor.state.social_ties.get(tgt, 0) - 5
                target.state.social_ties[actor.identity.id] = target.state.social_ties.get(actor.identity.id, 0) - 4
                apply_event_emotion(actor, "conflict")
                apply_event_emotion(target, "conflict")
                self._append_log(actor, f"与{target.identity.name}发生了冲突")
                self._append_log(target, f"与{actor.identity.name}发生了冲突")
            else:
                apply_event_emotion(actor, "conflict")
                self._append_log(actor, "感到愤怒，独自生闷气")

        elif t == "investigate":
            actor.state.energy -= 3
            at_night = self._is_night()
            lore_msg = self.engine._collect_lore_fragment(actor, actor.state.location, at_night)
            if lore_msg:
                self._append_log(actor, lore_msg)
            if random.random() < 0.4 or actor.identity.skills.get("夜视"):
                discoveries = {
                    "wilderness": "荒野的草丛里似乎有被踩踏的痕迹",
                    "mine": "矿洞深处的岩壁上刻着古老的符号",
                    "square": "广场石碑上刻着看不懂的纹路",
                    "workshop": "工坊旧炉子里藏着半张发黄的图纸",
                    "school": "学校书架里夹着一本没见过的旧书",
                }
                claim = discoveries.get(actor.state.location, f"在{loc_cn}发现了不寻常的痕迹")
                if actor.state.location in ("wilderness", "mine"):
                    self.knowledge.observe_with_action(
                        actor.identity.id, "investigate", claim, actor.state.location,
                        confidence=0.7, action_type="seek_resource",
                        action_target=actor.state.location, emotional_valence=0.5)
                else:
                    self.knowledge.observe(actor.identity.id, "investigate", claim, actor.state.location, confidence=0.7)
                apply_event_emotion(actor, "work_success")
                learn_habit(actor, "explore", "investigate", 1.0)
                self._append_log(actor, f"在{loc_cn}调查，发现了线索：「{claim}」")
            else:
                self.knowledge.observe(actor.identity.id, "investigate", f"在{loc_cn}仔细调查了一遍", actor.state.location, confidence=0.5)
                apply_event_emotion(actor, "investigate")
                self._append_log(actor, f"在{loc_cn}调查了周围的环境，暂时没有特别发现")

        elif t == "observe":
            actor.state.energy -= 1
            self._append_log(actor, f"在{loc_cn}观察四周")

        elif t == "request_respond":
            self._handle_request_respond(actor, action, r)

        actor.state.energy = max(0, min(100, actor.state.energy))

        # 每日目标进度（仅玩家，薄层）
        if is_player and hasattr(self.engine, 'quest_engine') and self.engine.quest_engine:
            gold_earned = max(0, actor.state.gold - gold_before)
            reward = self.engine.quest_engine.update_progress(actor, action_type=t, gold_earned=gold_earned, location=actor.state.location)
            if reward:
                self._append_log(actor, f"🎯 完成每日目标，获得{reward}金币奖励")

        r.accepted = True
        r.result = r.result or self._last_log(actor)
        return r

    # ------------------------------------------------------------ 请求（v5 纵切片）

    def _handle_request_respond(self, actor, action: Action, r: ActionResult):
        """请求选项结算：前置校验已在 _validate 完成（失败不扣费），此处只执行。"""
        req, opt = self._find_request_option(action)
        if req is None or opt is None:
            return
        if opt.requires == "wilderness":
            actor.state.inventory.append("dry_wood")
            self._record_change(r, actor.identity.id, "inventory", "无", "dry_wood", "request_respond")
            r.next_observation = "干木料到手了，莉娜在工坊等着这批料。"
            self._append_log(actor, opt.result_desc)
            return

        if opt.requires == "dry_wood":
            actor.state.inventory.remove("dry_wood")
            req.status = "completed"
            req.completed_day = self.engine.current_day
            lina = next((a for a in self.agents if a.identity.id == req.requester_id), None)
            if lina:
                before_tie = lina.state.social_ties.get(actor.identity.id, 0)
                lina.state.social_ties[actor.identity.id] = before_tie + 6
                self._record_change(r, f"{lina.identity.id}:{actor.identity.id}", "tie", before_tie, before_tie + 6, "request_respond")
                apply_event_emotion(lina, "work_success")
            r.result = opt.result_desc
            r.story_beats.append(opt.result_desc)
            r.next_observation = "莉娜的工坊重新转了起来。"
            self._append_log(actor, opt.result_desc)
            r.request_id = req.id

    # ------------------------------------------------------------ 日志

    def _record_change(self, r: ActionResult, target: str, field: str, before, after, source: str):
        if before == after:
            return
        r.changes.append(Change(target=target, field=field, before=before, after=after, source=source))

    def _append_log(self, actor, msg: str):
        self.engine.daily_agent_logs.setdefault(actor.identity.id, []).append(msg)

    def _last_log(self, actor) -> str:
        logs = self.engine.daily_agent_logs.get(actor.identity.id, [])
        return logs[-1] if logs else "完成"

    def _log_action(self, actor, action: Action, result: str):
        if actor.identity.role.value == 'player' and hasattr(self.engine, 'logger'):
            self.engine.logger.log_player_action(PlayerAction(
                tick=self.world.state.tick, action_type=action.kind,
                payload={"action": action.kind, "target": action.target_id or action.target_location},
                result=result))

    def _loc_cn(self, location: str) -> str:
        loc_map = {
            "square": "广场", "workshop": "工坊", "wilderness": "荒野",
            "school": "学校", "mine": "矿洞",
        }
        return loc_map.get(location, location)
