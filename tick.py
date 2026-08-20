"""Tick loop engine."""

import asyncio

import random

import time

from typing import List, Dict, Any, Callable, Optional, Tuple

from world import World

from events import EventBus, EventScheduler

from knowledge import KnowledgeEngine

from llm import LLMClient

from models import Event, EventType, Mood, AgentTask

from storage import Storage

from factions import FactionSystem

from emotions import (apply_event_emotion, spread_emotion, solidify_habits, learn_habit)

from crisis import roll_crisis





class TickEngine:

    def __init__(self, world: World, bus: EventBus, agents: list,

                 knowledge: KnowledgeEngine, logger, llm: LLMClient,

                 day_length: int = 20, auto_reset: bool = True,

                 db: Storage = None, wake_hour: int = 5, waking_hours: int = 12):

        self.world = world

        self.bus = bus

        self.agents = agents

        self.knowledge = knowledge

        self.logger = logger

        self.llm = llm


        self.day_length = day_length

        # 世界观：玩家清醒时段 = [wake_hour, wake_hour + waking_hours)，其余为夜晚
        self.wake_hour = wake_hour
        self.waking_hours = waking_hours

        self._running = False

        # 回合制：玩家行动累积的待推进小时数（1 AP = 1 小时）
        self._pending_advance = 0

        self.scheduler = EventScheduler(bus)

        # 统一持久层：外部注入（与 api/logger 共享同一实例），否则自建
        self.db = db if db is not None else Storage()

        self.faction_system = FactionSystem()


        self.day_summaries: List[Dict[str, Any]] = []

        self.current_day_events: List[Dict[str, Any]] = []

        self.current_day: int = 1

        self.on_day_summary: Optional[Callable] = None

        self.on_event: Optional[Callable] = None

        # 前一天状态，用于计算每日变化

        self.prev_agent_states: List[Dict[str, Any]] = []

        self.prev_knowledge_count: int = 0

        self.prev_total_gold: int = 0

        # 每日行为日志

        self.daily_agent_logs: Dict[str, List[str]] = {}

        # 数据库写入缓冲（每10个Tick写入一次）

        self._pending_snapshots: List[Tuple[int, int, Dict[str, Any]]] = []

        self._tick_since_last_db_write: int = 0

        self._db_write_interval: int = 10

        # 已处理事件去重集合（避免重复处理相同事件）


        # LLM调用追踪（每天限制次数）

        self._llm_calls_today = 0

        self._llm_daily_limit = 10

        self._llm_cache = {}  # 缓存相同输入的结果

        # 经济监控



        self._upgrades_done = 0  # 小镇修缮次数（世界观：末世重建）

        self._insight_day = 0  # 每日领悟：记录最近一次提交思考的天数（每日限一次）

        # 危机系统（v4 §4）：进行中的危机列表
        self.crises: List[Any] = []

        # 自动重置

        if auto_reset:

            self.db.reset()

        # 加载历史摘要

        self._load_history()

    

    def _load_history(self):

        """加载历史每日摘要"""

        summaries = self.db.get_day_summaries()

        if summaries:

            self.day_summaries = summaries

            self.current_day = summaries[-1]["day"] + 1

            print(f"[OK] 已加载 {len(summaries)} 条历史每日摘要，当前第 {self.current_day} 天")

        # 初始化当天的agent行为日志

        self.daily_agent_logs = {a.identity.id: [] for a in self.agents}



    async def run(self):

        """主循环（纯回合制）：世界时间只随玩家 AP 推进（1 AP = 1 小时），无闲时自动前进。"""

        self._save_current_state()

        self._running = True

        try:

            while self._running:

                if self._pending_advance > 0:

                    while self._pending_advance > 0:

                        self._pending_advance -= 1

                        await self.step()

                await asyncio.sleep(0.05)

        finally:

            # 确保退出时刷新所有缓冲数据到数据库

            self._flush_db_writes()

    def advance(self, hours: int = 1) -> None:
        """玩家行动驱动世界推进：消耗 1 AP 度过 1 小时（回合制）"""
        self._pending_advance += max(1, hours)

    async def wait_caught_up(self, timeout: float = 5.0) -> None:
        """等待回合制推进全部落地（run 循环处理完待推进小时），避免竞态"""
        waited = 0.0
        while self._pending_advance > 0 and waited < timeout:
            await asyncio.sleep(0.02)
            waited += 0.02



    def _save_current_state(self):

        """保存当前状态作为前一天的基准"""

        self.prev_agent_states = [a.to_dict() for a in self.agents]

        self.prev_knowledge_count = len(self.knowledge.claims)

        self.prev_total_gold = sum(a.state.gold for a in self.agents)

        # 初始化当天的agent行为日志

        self.daily_agent_logs = {a.identity.id: [] for a in self.agents}



    def _flush_db_writes(self):
        if not hasattr(self.db, "conn") or self.db.conn is None:
            return

        """将缓冲的数据库写入批量刷新到数据库"""

        if self._pending_snapshots:

            for tick, day, state in self._pending_snapshots:

                self.db.save_world_snapshot(tick, day, state)

            self._pending_snapshots.clear()



    async def step(self):

        tick = self.world.state.tick + 1

        hour = tick % self.day_length



        self.world.advance(tick)

        self.bus.flush_scheduled(tick)



        # 缓冲世界快照，每10个Tick批量写入一次数据库

        self._pending_snapshots.append(

            (tick, self.current_day, self.world.state.__dict__.copy())

        )

        self._tick_since_last_db_write += 1

        if self._tick_since_last_db_write >= self._db_write_interval:

            self._flush_db_writes()

            self._tick_since_last_db_write = 0



        # 处理事件，避免重复处理，同时保存到数据库

        processed_events = set()

        for event in self.bus.all_events:

            event_key = f"{event.type.value}_{event.tick}_{event.location}"

            if event_key in processed_events:

                continue

            processed_events.add(event_key)

            # 保存事件到数据库

            self.db.save_event(tick, self.current_day, event.type.value, event.location, event.payload)

            # 保存事件到数据库

            self.current_day_events.append({

                "tick": tick, "type": event.type.value,

                "location": event.location, "payload": str(event.payload)[:100],

            })

            await self._process_event(event)

            # 检查事件链

            await self._check_event_chains(event)

            # 自动固化高置信度知识

            self.knowledge.auto_solidify()

        self.bus.clear_events()



        # 优化循环，减少重复计算

        loc_map: Dict[str, list] = {}

        for a in self.agents:

            loc_map.setdefault(a.state.location, []).append(a.identity.id)

        for loc_id, loc_data in self.world.locations.items():

            loc_data["agents"] = loc_map.get(loc_id, [])



        # 批量处理Agent行动

        for agent in self.agents:

            evts = self.bus.get_events_at(agent.state.location)

            evt_strs = [f"{e.type.value} at {e.location}" for e in evts]

            # 同地点 Agent 对象列表（decide 需要 Agent 对象而非 ID）
            here = [a for a in self.agents if a.state.location == agent.state.location]

            agent.perceive(evt_strs)

            agent.think(hour)

            # 情绪传染（v4 §3.5）：沿关系网（好友 > 陌生人），稳定高者抗传染

            nearby = [o for o in self.agents if o.identity.id != agent.identity.id and o.state.location == agent.state.location]

            if nearby:

                spread_emotion(agent, nearby)

            # 玩家由用户操作驱动（经 api 走 _handle_action），不参与 NPC 自主决策
            if agent.identity.role.value == 'player':
                continue

            # LLM辅助决策检测（仅在关键场景调用）

            llm_action = await self._try_llm_decision(agent, hour, here, evt_strs)

            if llm_action:

                action = llm_action

                source = 'llm'

            else:

                action = agent.decide(hour, here, evt_strs, knowledge_engine=self.knowledge, world=self.world)

                source = 'rule'

            self.logger.log_decision(tick, agent.identity.id, action['desc'], action['type'],

                                     agent.top_goal().description if agent.top_goal() else '', 0.9 if source == 'llm' else 0.8, source)

            self.daily_agent_logs[agent.identity.id].append(f"{hour}点: {action['desc']}")

            # ★核心修复：执行决策结果，让动作真实改变世界（move/work/talk/trade/rest...）
            try:
                await self._handle_action(agent, action, tick)
            except Exception as e:
                self.daily_agent_logs[agent.identity.id].append(f"[执行异常] {e}")

            if action["type"] in ("talk", "work", "trade", "move"):

                evt = {"tick": tick, "agent": agent.identity.name, "action": action["desc"], "location": agent.state.location}

                self.current_day_events.append(evt)

                if self.on_event:

                    await self.on_event(evt)



        # 正午更新派系结构（低代价，让"小镇社会结构"可读）
        if hour == 10:
            self.faction_system.update_faction_membership(self.agents)

        if hour == 0 and tick > 1:

            # 每日金币回收（防通胀）
            self._apply_gold_sinks()

            # NPC 响应玩家交易（经济修复：交易不再是单方面空转）
            self._process_npc_trades()

            # 食物经济闭环：按当天饥饿程度记录需求（供>需价跌、需>供价涨）
            hungry = sum(1 for a in self.agents if a.state.hunger > 20)
            self.world.record_demand('food', max(1, hungry))

            # 小镇重建（世界观：末世后居民合力修缮破旧建筑）
            self._town_upgrade_check()

            # === 危机系统（v4 §4）：每日推进 ===
            # 1. 现有危机：性格化反应 + 倒计时结算
            for crisis in list(self.crises):
                if not crisis.active:
                    continue
                # NPC 性格化反应（每个非玩家 Agent 每天反应一次）
                for a in self.agents:
                    if a.identity.role.value != 'player':
                        reaction = crisis.react(a)
                        self.daily_agent_logs[a.identity.id].append(reaction)
                outcome = crisis.advance_day(self.agents)
                if outcome:
                    result_desc = crisis.apply_outcome(self.agents)
                    self.current_day_events.append({"tick": tick, "agent": "", "action": result_desc, "location": ""})
                    self.daily_agent_logs.setdefault("", []).append(result_desc)
                    # 危机期间玩家有干预 → 关系已在 intervene 时提升；恶化时降低
                    if outcome == "worsened" and crisis.interventions:
                        for a in self.agents:
                            if a.identity.id != "agent_player":
                                a.state.social_ties["agent_player"] = a.state.social_ties.get("agent_player", 0) - 3
            # 2. 尝试触发新危机
            new_crisis = roll_crisis(self.current_day, self)
            if new_crisis:
                self.crises.append(new_crisis)
                self.current_day_events.append({"tick": tick, "agent": "", "action": f"⚠️ 危机来袭：{new_crisis.desc}", "location": ""})
                self.daily_agent_logs.setdefault("", []).append(f"⚠️ 危机来袭：{new_crisis.desc}（持续{new_crisis.duration_days}天，可帮忙/调查/澄清）")

            # 新的一天：生成玩家每日目标
            if hasattr(self, 'quest_engine') and self.quest_engine:
                self.quest_engine.generate_daily_goals(self.current_day)

            summary = self._generate_day_summary(self.current_day)

            self.day_summaries.append(summary)

            # 保存每日摘要到数据库

            self.db.save_day_summary(summary)

            # 保存行为日志到数据库

            for agent in self.agents:

                self.db.save_agent_log(

                    day=self.current_day,

                    agent_id=agent.identity.id,

                    agent_name=agent.identity.name,

                    behaviors=self.daily_agent_logs.get(agent.identity.id, [])

                )

            # 写日记（档案"最近日记"可见）：概括一天的所见所为
            prev_map = {a["id"]: a for a in self.prev_agent_states}
            for agent in self.agents:
                agent.write_diary(self.current_day,
                                  self.daily_agent_logs.get(agent.identity.id, []),
                                  prev_map.get(agent.identity.id, {}).get("gold", agent.state.gold))

            self.current_day_events = []

            self._llm_calls_today = 0

            # 重置玩家AP（每日基础 12；十三时 = 独立的夜间行动力池，仅夜晚可用）
            for a in self.agents:
                if a.identity.role.value == 'player':
                    a.state.ap_max = 12
                    a.state.ap = 12
                    a.state.night_ap = (self.current_day + 1) // 13

            self.current_day += 1

            # 关系衰减：每天好感度向0回归5%（需要持续维护关系）

            for agent in self.agents:

                for other_id in agent.state.social_ties:

                    tie = agent.state.social_ties[other_id]

                    # 衰减量 = 当前值的5%，最小衰减0.1

                    decay = max(0.1, abs(tie) * 0.05)

                    if tie > 0:

                        agent.state.social_ties[other_id] = max(0, tie - decay)

                    elif tie < 0:

                        agent.state.social_ties[other_id] = min(0, tie + decay)

            # 习惯固化 → 性格演化（v4 §3.4：同情境同行为累计达阈值，性格维度微调）

            for agent in self.agents:

                if agent.identity.role.value == 'player':

                    continue

                changes = solidify_habits(agent)

                for c in changes:

                    self.daily_agent_logs[agent.identity.id].append(c)

                    self.current_day_events.append({"tick": tick, "agent": agent.identity.name, "action": c, "location": agent.state.location})

            aids = [a.identity.id for a in self.agents]

            self.scheduler.generate_daily_schedule(self.current_day, aids, self.world)

            # 保存下一天的前置状态

            self._save_current_state()

            if self.on_day_summary:

                await self.on_day_summary(summary)





    async def _try_llm_decision(self, agent, hour, agents_here, events) -> Optional[Dict[str, Any]]:

        """尝试LLM辅助决策，仅在关键场景调用"""

        # 检查每日限制

        if self._llm_calls_today >= self._llm_daily_limit:

            return None

        

        # 检测是否需要LLM介入

        scenario = None

        context = {}

        

        # 场景1：情绪危机（体力低+心情差）

        if agent.state.energy < 25 and agent.state.mood in (Mood.SAD, Mood.ANGRY):

            scenario = "emotional_crisis"

            context = {

                "energy": agent.state.energy,

                "mood": agent.state.mood.value,

                "personality": agent.identity.personality,

                "location": agent.state.location

            }

        

        # 场景2：社交困境（朋友需要帮忙但自己很累）

        elif agent.state.energy < 35 and agents_here:

            best_friend = None

            best_tie = 30

            for other in agents_here:

                other_id = other.identity.id

                tie = agent.state.social_ties.get(other_id, 0)

                if tie > best_tie:

                    best_tie = tie

                    best_friend = other_id

            if best_friend:

                scenario = "social_dilemma"

                context = {

                    "energy": agent.state.energy,

                    "friend": best_friend,

                    "tie_strength": best_tie,

                    "location": agent.state.location

                }

        

        if not scenario:

            return None

        

        # 检查缓存

        cache_key = f"{agent.identity.id}_{scenario}_{agent.state.energy}_{hour}"

        if cache_key in self._llm_cache:

            return self._llm_cache[cache_key]

        

        # 生成prompt

        prompt = self._generate_llm_prompt(agent, scenario, context)

        

        # 调用LLM

        try:

            response = await self.llm.call(prompt, system="你是K-town小镇的居民。根据你的状态和性格，决定你接下来做什么。用一句话描述你的行动。")

            self._llm_calls_today += 1

            

            # 解析响应

            action = self._parse_llm_response(agent, response)

            if action:

                self._llm_cache[cache_key] = action

                return action

        except Exception:

            pass

        

        return None

    

    def _generate_llm_prompt(self, agent, scenario, context) -> str:

        """为不同场景生成LLM prompt"""

        n = agent.identity.name

        role = agent.get_role_cn(agent.identity.role.value)

        p = agent.identity.personality

        

        if scenario == "emotional_crisis":

            return (

                f"你是{n}，一个{role}。"

                f"你现在的体力只有{int(context['energy'])}点，心情{context['mood']}。"

                f"你的性格：外向{p['extraversion']:.1f}、尽责{p['conscientiousness']:.1f}、开放{p['openness']:.1f}、宜人{p['agreeableness']:.1f}、稳定{p['stability']:.1f}。"

                f"你目前在{context['location']}。请用一句话描述你会做什么来改善现状。"

            )

        elif scenario == "knowledge_conflict":

            conflicts = context["conflicting_knowledge"]

            conflict_text = "；".join([f"你知道{c['claim']}，但有人质疑它" for c in conflicts])

            return (

                f"你是{n}，一个{role}。{conflict_text}。"

                f"你的性格：开放{p['openness']:.1f}、宜人{p['agreeableness']:.1f}。"

                f"你会如何处理这个知识冲突？用一句话描述。"

            )

        elif scenario == "social_dilemma":

            return (

                f"你是{n}，一个{role}。你的好朋友{context['friend']}需要帮助。"

                f"但你现在的体力只有{int(context['energy'])}点，感觉很累。"

                f"你们的好感度是{context['tie_strength']:.1f}。"

                f"你会怎么做？用一句话描述。"

            )

        return ""

    

    def _parse_llm_response(self, agent, response: str) -> Optional[Dict[str, Any]]:

        """解析LLM返回的行动描述"""

        if not response:

            return None

        

        response = response.strip()

        if len(response) > 100:

            response = response[:100]

        

        # 判断行动类型

        action_type = "observe"

        if "休息" in response or "睡" in response:

            action_type = "rest"

        elif "聊天" in response or "说话" in response or "告诉" in response:

            action_type = "talk"

        elif "工作" in response or "做" in response or "制作" in response:

            action_type = "work"

        elif "去" in response or "走" in response or "移动" in response:

            action_type = "move"

        elif "调查" in response or "探索" in response or "看" in response:

            action_type = "investigate"

        

        return {

            "type": action_type,

            "desc": response,

            "target": ""

        }














    def _apply_gold_sinks(self):

        """应用金币回收机制，防止通胀"""

        for agent in self.agents:

            # 食物税：每天固定消耗金币买食物

            if agent.state.hunger > 10 and agent.state.food < 3:

                food_price = self.world.get_price("food")

                if agent.state.gold >= food_price:

                    agent.state.gold -= food_price

                    agent.state.food += 1



            

            # 装备损耗：有工具的Agent每天有10%概率损耗1金币维护

            if "tool" in agent.state.inventory and random.random() < 0.1:

                if agent.state.gold >= 1:

                    agent.state.gold -= 1



            

            # 技能学习费：有目标的Agent可能花费金币学习

            if agent.top_goal() and agent.state.gold > 20 and random.random() < 0.05:

                fee = random.randint(2, 5)

                agent.state.gold -= fee



    def _process_npc_trades(self):
        """NPC 响应玩家的交易请求（v4 §2.4 经济修复：NPC 不再无视交易）。

        依据：NPC 是否有足够金币 + 是否真的需要该物品 + 价格是否合理。
        接受 → 双方金币/物品转移；拒绝 → 关系微降（玩家被扫了面子）。
        """
        if not self.world.state.trade_offers:
            return
        still_pending = []
        for offer in self.world.state.trade_offers:
            if offer.status != "pending":
                continue
            # 定位买家 NPC
            buyer = next((a for a in self.agents if a.identity.id == offer.to_agent), None)
            if not buyer:
                still_pending.append(offer)
                continue
            # 价格合理性：物品当前价 vs 出价（出价 <= 市价×1.5 视为合理——容忍市价波动）
            item_price = self.world.get_price(offer.item) if offer.item in self.world.base_prices else 5
            reasonable = offer.price <= item_price * 1.5
            # 需求判断：食物/工具是刚需
            needed = offer.item in ("food", "tools", "medicine", "ore", "materials")
            if buyer.state.gold >= offer.price and reasonable and needed:
                buyer.state.gold -= offer.price
                buyer.state.inventory.append(offer.item)
                offer.status = "accepted"
                # 买家愉悦↑（买到需要的东西）
                apply_event_emotion(buyer, "work_success")
                self.daily_agent_logs.setdefault(buyer.identity.id, []).append(f"接受了{offer.from_agent}的{offer.item}交易（{offer.price}金）")
            else:
                # 拒绝：价格离谱或买不起
                offer.status = "rejected"
                buyer.state.social_ties[offer.from_agent] = buyer.state.social_ties.get(offer.from_agent, 0) - 2
                self.daily_agent_logs.setdefault(buyer.identity.id, []).append(f"拒绝了{offer.from_agent}的{offer.item}交易")
            still_pending.append(offer)
        self.world.state.trade_offers = still_pending

    def _town_upgrade_check(self):
        """小镇重建（世界观：几十万年后末世，居民合力修缮破旧建筑）"""
        total_gold = sum(a.state.gold for a in self.agents)
        threshold = 100 * (self._upgrades_done + 1) ** 2
        if total_gold < threshold:
            return
        upgradable = [loc for loc, lvl in self.world.state.location_levels.items() if lvl < 5]
        if not upgradable:
            return
        loc = random.choice(upgradable)
        self.world.state.location_levels[loc] += 1
        self._upgrades_done += 1
        # 修缮后资源更丰（镇民合力投入）
        for res, amt in self.world.resources.get(loc, {}).items():
            self.world.resources[loc][res] = amt + 5
        loc_cn = self.world.locations.get(loc, {}).get("name", loc)
        self.current_day_events.append(
            {"type": "building_upgrade", "action": f"{loc_cn}修缮一新，焕然重生！", "tick": self.world.state.tick})
        self.db.log_world_event(self.world.state.tick, self.current_day,
                                "building_upgrade", loc, {"level": self.world.state.location_levels[loc]})
        print(f"[town] {loc_cn} 修缮至 Lv{self.world.state.location_levels[loc]}")

    def _night_mystery(self, agent):
        """主角的"十三时"：夜深人静时出门，能看到镇民看不到的东西（末世伏笔）。

        镇上铁律是"天黑别出门"——但主角那块古玉佩在逢 13 之数时会发烫，
        让人能在夜里行走。每次夜晚行动都有机会撞见遗迹的残响。
        """
        if random.random() < 0.2 and not agent.identity.skills.get("守夜人"):
            return None
        mysteries = [
            ("广场的石碑在月光下泛着微光，古老的纹路仿佛活了过来。", "square"),
            ("矿洞深处传来规律的敲击声，像有人在开采——可镇上的人都在睡觉。", "mine"),
            ("学校的老钟在午夜无人自鸣，不多不少，正好十三下。", "school"),
            ("荒野尽头亮起一片不属于这个时代的灯火，转瞬即逝。", "wilderness"),
            ("你看见一个模糊的人影在废墟间走动，随即消失不见。", "square"),
            ("工坊的火炉明明熄灭了，却在夜色里发出温暖的光。", "workshop"),
        ]
        if agent.identity.skills.get("遗迹共鸣"):
            mysteries.append(("你闭上眼，听见了整座小镇在很久以前的声音——那是另一个时代的回响。", "square"))
        text, loc = random.choice(mysteries)
        self.knowledge.observe(agent.identity.id, "夜之秘", text, loc, confidence=0.8)
        unlocked = None
        if random.random() < 0.4:
            for sk in ("夜视", "遗迹共鸣", "守夜人"):
                if sk not in agent.identity.skills:
                    agent.identity.skills[sk] = 1
                    unlocked = sk
                    break
        self.daily_agent_logs[agent.identity.id].append(f"🌙 夜深人静，{text}")
        self.current_day_events.append({"type": "night_mystery", "action": text, "tick": self.world.state.tick})
        msg = f"🌙 {text}"
        if unlocked:
            msg += f" 你感到古玉佩微微发烫，掌握了技能「{unlocked}」！"
        return msg

    # 每日领悟：触及隐藏剧情的知识关键词 → 松一丝封印，领悟技能/记忆碎片
    INSIGHT_TOPICS = [
        ("遗迹", "溯源", "你仿佛看见了整座城市沉入大地——那是很久以前的事了。"),
        ("废墟", "溯源", "你仿佛看见了整座城市沉入大地——那是很久以前的事了。"),
        ("石碑", "铭文识读", "石碑上的纹路，你竟然认得几个字。"),
        ("纹路", "铭文识读", "石碑上的纹路，你竟然认得几个字。"),
        ("十三", "十三时", "你梦见自己数过十二个时辰，又数到了第十三。"),
        ("玉佩", "溯源", "这块玉佩……你好像知道它原本属于谁。"),
        ("黑夜", "夜行者", "你忽然记起，很久以前，黑夜没有这么长。"),
        ("地球", "溯源", "你脱口而出「地球」二字，却不知这词从何而来。"),
        ("时间", "观星", "你意识到：时间本身，在很久以前出了一点差错。"),
        ("转速", "观星", "你意识到：时间本身，在很久以前出了一点差错。"),
        ("文明", "溯源", "你仿佛听见了整座城市的低语——那是很久以前的事了。"),
        ("秘密", "记忆", "这玉佩……你好像知道它属于谁。"),
    ]

    # 身世之谜：记忆碎片收集（v4 §5.2）—— 触及真相关键词 → 碎片入账
    # 集齐 5 片解锁"大缓变真相"线索
    LORE_FRAGMENTS = {
        "遗迹": {"skill": "溯源", "fragment": "你仿佛看见了整座城市沉入大地——那是很久以前的事了。", "lore_key": "ruins"},
        "废墟": {"skill": "溯源", "fragment": "你仿佛看见了整座城市沉入大地——那是很久以前的事了。", "lore_key": "ruins"},
        "石碑": {"skill": "铭文识读", "fragment": "石碑上的纹路，你竟然认得几个字。", "lore_key": "stele"},
        "纹路": {"skill": "铭文识读", "fragment": "石碑上的纹路，你竟然认得几个字。", "lore_key": "stele"},
        "十三": {"skill": "十三时", "fragment": "你梦见自己数过十二个时辰，又数到了第十三。", "lore_key": "thirteen"},
        "玉佩": {"skill": "溯源", "fragment": "这块玉佩……你好像知道它原本属于谁。", "lore_key": "jade"},
        "黑夜": {"skill": "夜行者", "fragment": "你忽然记起，很久以前，黑夜没有这么长。", "lore_key": "night"},
        "地球": {"skill": "溯源", "fragment": "你脱口而出「地球」二字，却不知这词从何而来。", "lore_key": "earth"},
        "时间": {"skill": "观星", "fragment": "你意识到：时间本身，在很久以前出了一点差错。", "lore_key": "time"},
        "转速": {"skill": "观星", "fragment": "你意识到：时间本身，在很久以前出了一点差错。", "lore_key": "time"},
        "文明": {"skill": "溯源", "fragment": "你仿佛听见了整座城市的低语——那是很久以前的事了。", "lore_key": "civilization"},
        "秘密": {"skill": "记忆", "fragment": "这玉佩……你好像知道它属于谁。", "lore_key": "secret"},
        "大缓变": {"skill": "溯源", "fragment": "大缓变……那不是天灾，是有人按下的开关。", "lore_key": "great_slow"},
    }
    # 碎片收集目标与解锁的线索
    LORE_TOTAL_FRAGMENTS = 5

    def _check_insight(self, agent, claim_text):
        """每日领悟：若提交的思考触及遗迹真相，封印松动，领悟技能 + 想起记忆碎片 + 收集身世碎片。"""
        if not claim_text:
            return None
        # 初始化身世碎片记录
        if not hasattr(self, 'lore_fragments'):
            self.lore_fragments = set()
            self.lore_unlocked = []
        for kw, info in self.LORE_FRAGMENTS.items():
            if kw in claim_text:
                skill = info["skill"]
                unlocked = skill not in agent.identity.skills
                agent.identity.skills[skill] = agent.identity.skills.get(skill, 0) + 1
                fragment = info["fragment"]
                agent.diary.append(f"第{self.current_day}天·记忆碎片：{fragment}")
                self.daily_agent_logs[agent.identity.id].append(f"✨ 你忽然想起了什么：{fragment}")
                self.current_day_events.append(
                    {"type": "insight", "action": f"✨ 领悟「{skill}」", "tick": self.world.state.tick})
                msg = f"✨ {fragment}"
                if unlocked:
                    msg += f" 封印松动了一丝——你领悟了「{skill}」！"
                # 身世碎片收集（v4 §5.2：集齐解锁大缓变线索）
                lore_key = info["lore_key"]
                if lore_key not in self.lore_fragments:
                    self.lore_fragments.add(lore_key)
                    collected = len(self.lore_fragments)
                    msg += f"【身世碎片 {collected}/{self.LORE_TOTAL_FRAGMENTS}】"
                    if collected >= self.LORE_TOTAL_FRAGMENTS:
                        self.lore_unlocked.append("大缓变的真相：那不是天灾，而是旧世界留下的最后一道指令。")
                        msg += " 你忽然明白了一切——大缓变不是天灾！"
                return msg
        return None







    async def _check_event_chains(self, event):

        """检查事件是否触发后续事件链"""

        chains = {

            EventType.RUMOR_SPREAD.value: self._chain_rumor_investigation,

            EventType.RESOURCE_FOUND.value: self._chain_resource_rush,

            EventType.SOCIAL_RELATION_CHANGE.value: self._chain_relationship_change,

            EventType.DISASTER.value: self._chain_disaster_aftermath,

        }

        

        chain_func = chains.get(event.type.value)

        if chain_func:

            await chain_func(event)

    

    async def _chain_rumor_investigation(self, event):

        """传闻→有人去调查→可能发现真相"""

        claim = event.payload.get("claim", "")

        if not claim or random.random() > 0.3:

            return

        

        # 找一个开放性高的Agent去调查

        investigators = [a for a in self.agents 

                        if a.identity.personality.get("openness", 0.5) > 0.6 

                        and a.state.energy > 30]

        if investigators:

            investigator = random.choice(investigators)

            self.daily_agent_logs[investigator.identity.id].append(f"听说'{claim}'，决定去调查真相")

            # 50%概率发现新知识

            if random.random() < 0.5:

                self.knowledge.observe(investigator.identity.id, "investigation", 

                                      f"调查了'{claim}'，发现了一些线索", 

                                      investigator.state.location)

    

    async def _chain_resource_rush(self, event):

        """资源发现→更多Agent去采集"""

        resource = event.payload.get("resource", "")

        location = event.location

        if not resource or random.random() > 0.4:

            return

        

        # 找2-3个Agent去采集

        gatherers = [a for a in self.agents 

                    if a.identity.role.value in ("forager", "farmer", "scout")

                    and a.state.energy > 40

                    and a.state.location != location]

        if gatherers:

            for g in random.sample(gatherers, min(2, len(gatherers))):

                self.daily_agent_logs[g.identity.id].append(f"听说{location}有{resource}，赶过去采集")

    

    async def _chain_relationship_change(self, event):

        """关系变化→可能引发连锁反应"""

        agent1 = event.payload.get("agent1", "")

        agent2 = event.payload.get("agent2", "")

        change = event.payload.get("change", 0)

        

        # 关系变好→朋友们也变好

        if change > 0 and random.random() < 0.3:

            for a in self.agents:

                if a.identity.id in (agent1, agent2):

                    continue

                tie1 = a.state.social_ties.get(agent1, 0)

                tie2 = a.state.social_ties.get(agent2, 0)

                if tie1 > 20 and tie2 > 20:

                    # 共同朋友也增加好感

                    a.state.social_ties[agent1] = tie1 + 0.5

                    a.state.social_ties[agent2] = tie2 + 0.5

    

    async def _chain_disaster_aftermath(self, event):

        """灾害→居民互助→关系提升"""

        if random.random() > 0.5:

            return

        

        # 找稳定性高的Agent去帮助他人

        helpers = [a for a in self.agents 

                  if a.identity.personality.get("stability", 0.5) > 0.6

                  and a.state.energy > 50]

        if helpers:

            helper = random.choice(helpers)

            self.daily_agent_logs[helper.identity.id].append("灾害发生后，主动帮助受影响的邻居")

            # 帮助他人→关系提升

            for a in self.agents:

                if a.identity.id != helper.identity.id:

                    tie = a.state.social_ties.get(helper.identity.id, 0)

                    a.state.social_ties[helper.identity.id] = tie + 1





    def _generate_day_summary(self, day: int) -> Dict[str, Any]:

        """生成中文每日叙事摘要"""

        weather_name = self.world.get_weather_name()

        current_total_gold = sum(a.state.gold for a in self.agents)

        gold_change = current_total_gold - self.prev_total_gold

        knowledge_change = len(self.knowledge.claims) - self.prev_knowledge_count

        avg_energy = sum(a.state.energy for a in self.agents) / max(1, len(self.agents))

        happy_count = sum(1 for a in self.agents if a.state.mood.value == "happy")

        anxious_count = sum(1 for a in self.agents if a.state.mood.value in ("anxious", "sad", "angry"))



        # 生成每个居民的叙事描述

        agent_summaries = []

        prev_state_map = {a["id"]: a for a in self.prev_agent_states}

        location_agents: Dict[str, List[str]] = {}

        for agent in self.agents:

            loc = agent.state.location

            location_agents.setdefault(loc, []).append(agent.identity.name)



        for agent in self.agents:

            prev = prev_state_map.get(agent.identity.id, {})

            energy_change = round(agent.state.energy - prev.get("energy", 100), 1)

            gold_change_agent = agent.state.gold - prev.get("gold", 0)

            behavior_log = self.daily_agent_logs.get(agent.identity.id, [])



            # 统计行为类型

            work_count = sum(1 for b in behavior_log if "工作" in b or "锻造" in b or "采集" in b or "耕种" in b or "挖掘" in b or "制作" in b or "救治" in b)

            talk_count = sum(1 for b in behavior_log if "聊天" in b or "讲" in b or "教" in b)

            move_count = sum(1 for b in behavior_log if "前往" in b or "移动" in b)

            rest_count = sum(1 for b in behavior_log if "休息" in b or "睡觉" in b)

            trade_count = sum(1 for b in behavior_log if "交易" in b or "摆摊" in b)



            # 心情描述

            mood_map = {

                "happy": "心情愉快", "neutral": "心情平静",

                "anxious": "有些焦虑", "angry": "非常生气", "sad": "心情低落"

            }

            mood_desc = mood_map.get(agent.state.mood.value, "心情未知")



            # 生成叙事描述

            narrative_parts = []

            if work_count > 0:

                role_work_desc = {

                    "blacksmith": f"在工坊勤劳地锻造了{work_count}次工具",

                    "carpenter": f"在工坊精心制作了{work_count}次木工家具",

                    "forager": f"前往荒野采集了{work_count}次食物和草药",

                    "farmer": f"在田地里耕种了{work_count}次庄稼",

                    "scout": f"探索了{work_count}次未知区域",

                    "healer": f"在学校救治了{work_count}次病人",

                    "miner": f"在矿洞挖掘了{work_count}次矿石",

                    "merchant": f"在广场摆摊交易了{trade_count}次" if trade_count > 0 else "在广场打理生意",

                    "elder": f"给年轻人们分享了{work_count}次古老的知识",

                    "teacher": f"教导了{work_count}次孩子们读书写字",

                    "storyteller": f"讲述了{work_count}次有趣的冒险故事",

                    "player": "在小镇里四处探索"

                }

                narrative_parts.append(role_work_desc.get(agent.identity.role.value, f"完成了{work_count}次工作"))

            if talk_count > 0:

                narrative_parts.append(f"和镇民们交谈了{talk_count}次")

            if move_count > 0:

                narrative_parts.append(f"在小镇中往返了{move_count}次")

            if rest_count > 0:

                narrative_parts.append(f"休息了{rest_count}次恢复体力")



            if not narrative_parts:

                narrative_parts.append("今天比较悠闲，在附近散步观察")



            # 变化描述

            changes = []

            if energy_change > 5:

                changes.append("精神饱满")

            elif energy_change < -10:

                changes.append("显得有些疲惫")

            elif energy_change < -5:

                changes.append("体力有所下降")



            if gold_change_agent > 10:

                changes.append(f"收入了{gold_change_agent}金币，小有积蓄")

            elif gold_change_agent > 0:

                changes.append(f"赚了{gold_change_agent}金币")

            elif gold_change_agent < -5:

                changes.append(f"花费了{abs(gold_change_agent)}金币")



            change_text = "，".join(changes) if changes else "状态平稳"



            # 组合叙事

            narrative = f"{agent.identity.name}（{agent.get_role_cn(agent.identity.role.value)}）"

            narrative += "，".join(narrative_parts) + "。"

            narrative += f"目前{mood_desc}，{change_text}。"

            narrative += f"当前位于{agent.get_location_cn(agent.state.location)}，体力{round(agent.state.energy,1)}点，持有{agent.state.gold}金币。"



            # 确定变化类型（用于前端显示）

            if gold_change_agent > 5 or energy_change > 5:

                change_type = "positive"

            elif gold_change_agent < -5 or energy_change < -10:

                change_type = "negative"

            else:

                change_type = "neutral"



            agent_summaries.append({

                "id": agent.identity.id,

                "name": agent.identity.name,

                "role": agent.identity.role.value,

                "role_cn": agent.get_role_cn(agent.identity.role.value),

                "location": agent.state.location,

                "location_cn": agent.get_location_cn(agent.state.location),

                "energy": round(agent.state.energy, 1),

                "energy_change": energy_change,

                "mood": agent.state.mood.value,

                "mood_desc": mood_desc,

                "gold": agent.state.gold,

                "gold_change": gold_change_agent,

                "knowledge_count": len(self.knowledge.agent_knowledge(agent.identity.id)),

                "narrative": narrative,

                "change_type": change_type,

                "goal": agent.top_goal().description if agent.top_goal() else "暂无目标"

            })



        # 重大事件摘要

        important_events = []

        for evt in self.current_day_events:

            t = evt.get("type", "")

            if t == EventType.WEATHER_CHANGE.value:

                important_events.append(f"天气变为{self.world.get_weather_name(evt.get('payload', ''))}")

            elif t == EventType.RESOURCE_FOUND.value:

                important_events.append(f"在{self._get_location_cn(evt.get('location', ''))}发现了新资源")

            elif t == EventType.ITEM_CRAFTED.value:

                important_events.append(f"有人制作了新的{evt.get('payload', '物品')}")

            elif t == EventType.FESTIVAL.value:

                important_events.append("全镇举办了节日庆典")

            elif t == EventType.DISASTER.value:

                important_events.append(f"发生了{evt.get('type', '灾害')}，居民们受到了影响")

            elif t == EventType.RUMOR_SPREAD.value:

                important_events.append("镇上有新的传闻在流传")

            elif t == EventType.SOCIAL_RELATION_CHANGE.value:

                important_events.append("一些居民之间的关系发生了变化")



        # 整体叙事摘要

        overall = f"第{day}天过去了，{weather_name}的天空下，小镇迎来了新的变化。"

        overall += f"镇上的{len(self.agents)}位居民"

        if happy_count >= len(self.agents) * 0.6:

            overall += "大多心情愉快，整个小镇洋溢着欢乐的气氛。"

        elif anxious_count >= len(self.agents) * 0.4:

            overall += "中有不少人显得焦虑，似乎有什么事情困扰着大家。"

        else:

            overall += "各司其职，过着平静的生活。"



        overall += f"今天平均体力为{round(avg_energy,1)}点。"

        if knowledge_change > 0:

            overall += f"知识库新增了{knowledge_change}条知识，小镇的文化更加丰富了。"

        if gold_change > 0:

            overall += f"全镇金币总量增加了{gold_change}，经济有所增长。"

        elif gold_change < -10:

            overall += f"全镇金币总量减少了{abs(gold_change)}，需要更加节约。"



        if important_events:

            overall += f"今天发生的重大事件：{'；'.join(important_events[:5])}。"



        # 地点动态

        location_dynamics = []

        for loc_id, agents_here in location_agents.items():

            if len(agents_here) >= 3:

                location_dynamics.append(f"{self._get_location_cn(loc_id)}非常热闹，有{len(agents_here)}位居民聚集")

            elif len(agents_here) == 0:

                location_dynamics.append(f"{self._get_location_cn(loc_id)}空无一人")

        if location_dynamics:

            overall += " " + "，".join(location_dynamics) + "。"



        return {

            "day": day,

            "weather": self.world.state.weather,

            "weather_name": weather_name,

            "overall_summary": overall,

            "agents": agent_summaries,

            "stats": {

                "total_gold": current_total_gold,

                "gold_change": gold_change,

                "total_knowledge": len(self.knowledge.claims),

                "knowledge_change": knowledge_change,

                "avg_energy": round(avg_energy, 1),

                "happy_count": happy_count,

                "anxious_count": anxious_count,

                "events_count": len(self.current_day_events)

            }

        }

    def _get_location_cn(self, location: str) -> str:

        """获取地点中文名"""

        loc_map = {

            "square": "广场",

            "workshop": "工坊",

            "wilderness": "荒野",

            "school": "学校",

            "mine": "矿洞"

        }

        return loc_map.get(location, location)



    async def _process_event(self, event):

        if event.type == EventType.WEATHER_CHANGE:

            # 天气以 world.advance 的实时值唯一为准（事件载荷只是播报占位）
            w = self.world.state.weather

            w_cn = self.world.get_weather_name(w) if w != "unknown" else "未知"

            for a in self.agents:

                if a.state.location == event.location:

                    c = self.knowledge.observe(a.identity.id, "weather", f"今天天气是{w_cn}", a.state.location)

                    self.logger.log_knowledge(0, c.id, a.identity.id, "create", "", c.claim)

        elif event.type == EventType.RESOURCE_FOUND:

            r = event.payload.get("resource", "unknown")

            aid = event.payload.get("agent_id", "")

            if aid:
                self.knowledge.observe(aid, "resource", f"在{event.location}发现了{r}", event.location)
                a = next((x for x in self.agents if x.identity.id == aid), None)
                if a: apply_event_emotion(a, "resource_found")

        elif event.type == EventType.SOCIAL_ENCOUNTER:

            aids = event.payload.get("agents", [])

            for aid in aids:
                self.knowledge.observe(aid, "social", f"在{event.location}遇到了其他人", event.location)
                a = next((x for x in self.agents if x.identity.id == aid), None)
                if a: apply_event_emotion(a, "social_encounter")

            if len(aids) >= 2:

                claims_a = self.knowledge.agent_knowledge(aids[0])

                if claims_a:

                    top = max(claims_a, key=lambda c: c.confidence)

                    self.knowledge.propagate(top.id, aids[0], aids[1], 0.8)

        elif event.type == EventType.ITEM_CRAFTED:

            item = event.payload.get("item", "unknown")

            aid = event.payload.get("agent_id", "")

            if aid:
                self.knowledge.observe(aid, "craft", f"制作了{item}", event.location)
                a = next((x for x in self.agents if x.identity.id == aid), None)
                if a: apply_event_emotion(a, "item_crafted")

        elif event.type == EventType.WEATHER_IMPACT:

            impact = event.payload.get("impact", 0)

            for a in self.agents:

                if a.state.location == event.location:

                    # 天气影响工作效率：降低体力消耗

                    a.state.energy = max(0, a.state.energy + impact * 10)

                    apply_event_emotion(a, "weather_impact")

        elif event.type == EventType.SOCIAL_RELATION_CHANGE:

            agent1 = event.payload.get("agent1", "")

            agent2 = event.payload.get("agent2", "")

            change = event.payload.get("change", 0)

            for a in self.agents:

                if a.identity.id == agent1:

                    a.state.social_ties[agent2] = a.state.social_ties.get(agent2, 0) + change

                elif a.identity.id == agent2:

                    a.state.social_ties[agent1] = a.state.social_ties.get(agent1, 0) + change

            # 关系变化是情绪事件（v4 §3.2）

            if change > 0:

                for aid in (agent1, agent2):
                    a = next((x for x in self.agents if x.identity.id == aid), None)
                    if a: apply_event_emotion(a, "social_relation_change")




        elif event.type == EventType.FESTIVAL:

            # 节日：所有人愉悦↑（外向者更开心，内向者平淡）—— 情绪系统 v4 §3.2

            for a in self.agents:

                apply_event_emotion(a, "festival")

                extraversion = a.identity.personality.get('extraversion', 0.5)

                a.state.energy = min(100, a.state.energy + (15 if extraversion > 0.6 else 8))

        elif event.type == EventType.DISASTER:

            # 灾害：根据人格不同反应不同（敏感者冲击大—— v4 §3.2 核心示例）

            disaster_type = event.payload.get('type', 'unknown')

            for a in self.agents:

                stability = a.identity.personality.get('stability', 0.5)

                openness = a.identity.personality.get('openness', 0.5)

                # 稳定性低→反应更强烈（更害怕）

                energy_loss = 10 + int((1 - stability) * 10)

                gold_loss = 3 + int((1 - stability) * 5)

                a.state.energy = max(0, a.state.energy - energy_loss)

                a.state.gold = max(0, a.state.gold - gold_loss)

                # 情绪偏移：敏感者焦虑×2.0，稳定高者×0.7（emotions.py 调制系数）

                apply_event_emotion(a, "disaster")

            # 减少受灾地点资源

            if event.location in self.world.resources:

                for r in self.world.resources[event.location]:

                    self.world.resources[event.location][r] = max(0, self.world.resources[event.location][r] - 10)

        elif event.type == EventType.RUMOR_SPREAD:

            claim = event.payload.get("claim", "")

            f = event.payload.get("from", "")

            t = event.payload.get("to", "")

            if f and t and claim:

                self.knowledge.observe(f, "rumor", claim, event.location)

                self.knowledge.observe(t, "rumor", f"听说{claim}", event.location)



        elif event.type == EventType.MERCHANT_ARRIVAL:

            for a in self.agents:

                if a.state.location == 'square':

                    apply_event_emotion(a, "merchant_arrival")

                    a.state.gold += random.randint(3, 8)

            self.world.record_supply('food', 5)


        elif event.type == EventType.TOWN_MEETING:

            square_agents = [a for a in self.agents if a.state.location == 'square']

            for a in square_agents:

                for b in square_agents:

                    if a.identity.id != b.identity.id:

                        tie = a.state.social_ties.get(b.identity.id, 0)

                        a.state.social_ties[b.identity.id] = tie + 0.5

        elif event.type == EventType.MYSTERIOUS_STRANGER:

            claims = ['一个陌生人来到了小镇', '有人在森林里看到了奇怪的光', '据说矿洞深处有宝藏']

            agent_ids = [a.identity.id for a in self.agents]

            f, t = random.sample(agent_ids, 2)

            self.bus.schedule(Event(tick=event.tick + 2, type=EventType.RUMOR_SPREAD, 

                location='square', payload={'claim': random.choice(claims), 'from': f, 'to': t}), event.tick + 2)


        elif event.type == EventType.ANIMAL_ATTACK:

            for a in self.agents:

                if a.state.location == 'wilderness':

                    a.state.energy = max(0, a.state.energy - 20)

                    apply_event_emotion(a, "animal_attack")

        elif event.type == EventType.GOLDEN_DISCOVERY:

            aid = event.payload.get('agent_id', '')

            for a in self.agents:

                if a.identity.id == aid:

                    a.state.gold += random.randint(20, 50)

                    apply_event_emotion(a, "golden_discovery")

                    break




    async def _handle_action(self, agent, action, tick):

        """执行单个动作，真实改变世界状态。玩家与 NPC 共用同一动作管线。"""

        t = action.get("type", "")

        # 归一化：craft/gather 类动作视为劳作（work 分支按职业产出金币/资源/知识）
        # 修复：此前这些动作无分支，铁匠/木匠/采集者/农民/矿工的劳作是静默空操作
        if t in ("craft_tool", "craft_furniture", "gather_food", "gather_material"):
            t = "work"

        tgt = action.get("target", "")

        loc_cn = agent.get_location_cn(agent.state.location)

        # 记录"正在做的事"（档案/对话语境显示；休息/观察时清空）
        if t in ("work", "move", "talk", "investigate", "trade"):
            agent.state.current_task = AgentTask(description=f"在{loc_cn}忙活着", location=agent.state.location)
        elif t in ("rest", "sleep", "observe"):
            agent.state.current_task = None

        # 玩家行动消耗AP（不足则拦截；夜晚走十三时夜间行动力，不扣常规AP）
        cur_hour = tick % self.day_length
        at_night = not (self.wake_hour <= cur_hour < self.wake_hour + self.waking_hours)
        if agent.identity.role.value == 'player' and t in ('move', 'work', 'talk', 'rest', 'investigate'):
            if not at_night:
                ap_cost = 2 if t == 'investigate' else 1
                if agent.state.ap < ap_cost:
                    self.daily_agent_logs[agent.identity.id].append('AP不足，无法行动')
                    return
                agent.state.ap -= ap_cost

        # 记录动作前金币（用于每日目标"赚取金币"进度）

        gold_before = agent.state.gold

        if t == "move" and tgt:

            self.world.remove_agent_from_location(agent.identity.id, agent.state.location)

            agent.state.location = tgt

            self.world.add_agent_to_location(agent.identity.id, tgt)

            agent.state.energy -= 5

            apply_event_emotion(agent, "move")

            self.daily_agent_logs[agent.identity.id].append(f"移动到了{self._get_location_cn(tgt)}")

        elif t == "work":

            agent.state.energy -= 8

            role = agent.identity.role.value

            work_knowledge = {

                "blacksmith": ("锻造", f"在工坊锻造了优质的工具"),

                "carpenter": ("木工", f"在工坊制作了精美的木家具"),

                "forager": ("采集", f"在森林里采集了新鲜的食材和草药"),

                "farmer": ("农耕", f"在田地里辛勤耕种，期待丰收"),

                "scout": ("探索", f"探索了荒野的未知区域，绘制了新地图"),

                "healer": ("医疗", f"在学校救治了病人，配制药剂"),

                "miner": ("采矿", f"在矿洞深处挖掘出珍贵的矿石"),

                "merchant": ("商业", f"在广场打理生意，了解市场行情"),

                "elder": ("知识", f"给年轻人们讲述了古老的传说和智慧"),

                "teacher": ("教育", f"教导孩子们读书写字，传播知识"),

                "storyteller": ("故事", f"给大家讲述精彩的冒险故事"),

            }

            if role in work_knowledge:

                subject, desc = work_knowledge[role]

                self.knowledge.observe(agent.identity.id, subject, desc, agent.state.location)

            if role in ["blacksmith", "carpenter"]:

                agent.state.gold += 5

                agent.state.inventory.append("tool")

            elif role in ["forager", "farmer"]:

                agent.state.gold += 3

                agent.state.inventory.append("food")

                # 食物经济闭环：采集行为计入供给
                self.world.record_supply('food', 3)

            elif role == "scout":

                agent.state.gold += 4

            elif role == "healer":

                agent.state.gold += 4

            elif role == "miner":

                agent.state.gold += 5

            else:

                agent.state.gold += 2

            # 知识驱动发展：劳作中精进技能（技能等级提升产出）
            skill = agent.identity.skills.get(role, 0)
            if skill > 0:
                agent.state.gold += min(3, skill)
            if random.random() < 0.12:
                agent.identity.skills[role] = skill + 1
                self.daily_agent_logs[agent.identity.id].append(
                    f"{agent.get_role_cn(role)}技能提升到{skill + 1}级，手艺更精进了")

            # 情绪反馈（v4 §3.4）：工作有产出 → 愉悦↑，强化"工作"习惯
            apply_event_emotion(agent, "work_success")
            learn_habit(agent, "work", "work", 1.0)

            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}工作")

        elif t == "rest":

            agent.state.energy = min(100, agent.state.energy + 10)

            apply_event_emotion(agent, "rest")

            learn_habit(agent, "tired", "rest", 1.0)

            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}休息恢复体力")

        elif t == "sleep":

            agent.state.energy = min(100, agent.state.energy + 20)

            apply_event_emotion(agent, "sleep")

            self.daily_agent_logs[agent.identity.id].append("睡觉休息")

        elif t == "talk":

            agent.state.energy -= 2

            agent.state.gold += 1

            # 社交时传播知识给同地点所有 Agent（信任度高者更易传）

            claims = self.knowledge.agent_knowledge(agent.identity.id)

            if claims and len(claims) > 0:

                top = max(claims, key=lambda c: c.confidence)

                if top.confidence > 0.5:

                    for other in self.agents:

                        if other.identity.id != agent.identity.id and other.state.location == agent.state.location:

                            self.knowledge.propagate(top.id, agent.identity.id, other.identity.id, 0.7)

            # 社交时增加与在场Agent的好感度

            for other in self.agents:

                if other.identity.id == agent.identity.id:

                    continue

                if other.state.location == agent.state.location:

                    # 宜人性高→更容易增加好感

                    agreeableness = agent.identity.personality.get('agreeableness', 0.5)

                    extraversion = agent.identity.personality.get('extraversion', 0.5)

                    tie_change = 0.5 + agreeableness * 0.5 + extraversion * 0.3

                    current_tie = agent.state.social_ties.get(other.identity.id, 0)

                    agent.state.social_ties[other.identity.id] = current_tie + tie_change

                    # 双向关系也增加（但少一些）

                    other_tie = other.state.social_ties.get(agent.identity.id, 0)

                    other.state.social_ties[agent.identity.id] = other_tie + tie_change * 0.7

            # 情绪反馈：社交→愉悦↑、焦虑↓；强化"社交"习惯（外向者更受益）
            apply_event_emotion(agent, "talk")
            learn_habit(agent, "socialize", "talk", 1.0)

            self.daily_agent_logs[agent.identity.id].append(f'和{loc_cn}的人聊天')

        elif t == "trade":

            if agent.identity.role.value == "merchant":

                agent.state.gold += 8

            else:

                agent.state.gold += 2

            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}进行交易")

        elif t == "conflict":

            # 冲突（v4 §3.3：高愤怒者可能爆发）—— 双方关系受损，双方愤怒↑/愉悦↓
            agent.state.energy -= 5
            target_id = tgt
            target = next((a for a in self.agents if a.identity.id == target_id), None)
            if target:
                agent.state.social_ties[target_id] = agent.state.social_ties.get(target_id, 0) - 5
                target.state.social_ties[agent.identity.id] = target.state.social_ties.get(agent.identity.id, 0) - 4
                apply_event_emotion(agent, "conflict")
                apply_event_emotion(target, "conflict")
                self.daily_agent_logs[agent.identity.id].append(f"与{target.identity.name}发生了冲突")
                self.daily_agent_logs[target.identity.id].append(f"与{agent.identity.name}发生了冲突")
            else:
                apply_event_emotion(agent, "conflict")
                self.daily_agent_logs[agent.identity.id].append("感到愤怒，独自生闷气")

        elif t == "investigate":

            agent.state.energy -= 3

            # 调查：可能发现当前地点的线索/知识（末世遗迹伏笔的入口）
            # 拥有"夜视"技能则必定发现（十三时夜晚探索的回报）
            if random.random() < 0.4 or agent.identity.skills.get("夜视"):
                discoveries = {
                    "wilderness": "荒野的草丛里似乎有被踩踏的痕迹",
                    "mine": "矿洞深处的岩壁上刻着古老的符号",
                    "square": "广场石碑上刻着看不懂的纹路",
                    "workshop": "工坊旧炉子里藏着半张发黄的图纸",
                    "school": "学校书架里夹着一本没见过的旧书",
                }
                claim = discoveries.get(agent.state.location, f"在{loc_cn}发现了不寻常的痕迹")
                # 资源富集地点的线索记为"可行动知识"（seek_resource）→ 驱动其他 Agent 前来采集
                if agent.state.location in ("wilderness", "mine"):
                    self.knowledge.observe_with_action(
                        agent.identity.id, "investigate", claim, agent.state.location,
                        confidence=0.7, action_type="seek_resource",
                        action_target=agent.state.location, emotional_valence=0.5)
                else:
                    self.knowledge.observe(agent.identity.id, "investigate", claim, agent.state.location, confidence=0.7)
                # 探索成功 → 愉悦↑，强化"探索"习惯（开放型探索者受益）
                apply_event_emotion(agent, "work_success")
                learn_habit(agent, "explore", "investigate", 1.0)
                self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}调查，发现了线索：「{claim}」")
            else:
                self.knowledge.observe(agent.identity.id, "investigate", f"在{loc_cn}仔细调查了一遍", agent.state.location, confidence=0.5)
                apply_event_emotion(agent, "investigate")
                self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}调查了周围的环境，暂时没有特别发现")

        elif t == "observe":

            agent.state.energy -= 1

            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}观察四周")

        agent.state.energy = max(0, min(100, agent.state.energy))

        # 每日目标进度（仅玩家，薄层）—— 动作执行后追踪，完成即发奖励
        if agent.identity.role.value == 'player' and hasattr(self, 'quest_engine') and self.quest_engine:
            gold_earned = max(0, agent.state.gold - gold_before)
            reward = self.quest_engine.update_progress(agent, action_type=t, gold_earned=gold_earned)
            if reward:
                self.daily_agent_logs[agent.identity.id].append(f"🎯 完成每日目标，获得{reward}金币奖励")



    def stop(self):

        self._running = False

        self.db.close()

    