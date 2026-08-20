"""危机系统（gameplay-design-v4 §4）—— "小镇会出事，你能伸手"

设计：
- 4 种危机：灾害（暴风雨）/ 疫病 / 谣言风暴 / 资源危机
- 生命周期：触发 → 性格化反应（NPC 按性格各自应对）→ 玩家每日可干预 → 结局分支
- 干预：帮忙（3 AP）/ 调查（2 AP）/ 澄清（1 AP）/ 旁观（0 AP）
- 结局：倒计时内进度达标 → 缓解（关系↑、居民记住你）；失败/旁观 → 恶化（关系↓、有人受伤/离开）

不依赖 LLM：规则表 + 状态机，可调可测。
"""
import random
from typing import Dict, List, Optional

from models import Event, EventType, Mood

# 危机类型
CRISIS_STORM = "storm"          # 灾害：暴风雨
CRISIS_PLAGUE = "plague"        # 疫病：旧世界病
CRISIS_RUMOR = "rumor"          # 谣言风暴：传闻失控
CRISIS_FAMINE = "famine"        # 资源危机：食物短缺

# 危机配置：类型 → (持续天数, 达标进度, 恶化代价)
CRISIS_CONFIG = {
    CRISIS_STORM: {"duration_days": 3, "target": 60, "energy_loss": 15, "gold_loss": 5, "desc": "一场罕见的暴风雨正在逼近小镇"},
    CRISIS_PLAGUE: {"duration_days": 4, "target": 70, "energy_loss": 12, "gold_loss": 8, "desc": "旧世界流传下来的疫病在镇里蔓延"},
    CRISIS_RUMOR: {"duration_days": 3, "target": 50, "energy_loss": 0, "gold_loss": 3, "desc": "一则谣言在小镇里疯传，人心惶惶"},
    CRISIS_FAMINE: {"duration_days": 4, "target": 60, "energy_loss": 8, "gold_loss": 6, "desc": "食物储备告急，小镇面临饥荒"},
}

# 危机类型 → 事件类型（用于 tick 触发）
CRISIS_TO_EVENT = {
    CRISIS_STORM: EventType.DISASTER,
    CRISIS_PLAGUE: EventType.DISASTER,
    CRISIS_RUMOR: EventType.RUMOR_SPREAD,
    CRISIS_FAMINE: EventType.RESOURCE_FOUND,
}

# 干预类型 → (AP 消耗, 进度增益)
INTERVENTIONS = {
    "help": {"ap": 3, "progress": 25, "desc": "帮忙"},
    "investigate": {"ap": 2, "progress": 15, "desc": "调查"},
    "clarify": {"ap": 1, "progress": 10, "desc": "澄清"},
    "watch": {"ap": 0, "progress": 0, "desc": "旁观"},
}

# 性格 → 危机反应（NPC 在危机中的倾向）
PERSONALITY_REACTIONS = {
    CRISIS_STORM: {
        "organize": lambda p: p.get("conscientiousness", 0.5) > 0.7,   # 尽责者组织
        "flee": lambda p: p.get("stability", 0.5) < 0.4,               # 敏感者逃跑
        "help": lambda p: p.get("agreeableness", 0.5) > 0.7,           # 亲善者帮忙
    },
    CRISIS_PLAGUE: {
        "care": lambda p: p.get("agreeableness", 0.5) > 0.7,           # 亲善者照顾
        "panic": lambda p: p.get("stability", 0.5) < 0.4,              # 敏感者恐慌
        "isolate": lambda p: p.get("extraversion", 0.5) < 0.3,         # 内向者隔离
    },
    CRISIS_RUMOR: {
        "investigate": lambda p: p.get("openness", 0.5) > 0.7,         # 开放者探究
        "believe": lambda p: p.get("stability", 0.5) < 0.4,            # 敏感者全信
        "clarify": lambda p: p.get("agreeableness", 0.5) > 0.7,        # 亲善者澄清
    },
    CRISIS_FAMINE: {
        "farm": lambda p: p.get("conscientiousness", 0.5) > 0.6,       # 尽责者多种
        "hoard": lambda p: p.get("agreeableness", 0.5) < 0.4,          # 自私者囤积
        "leave": lambda p: p.get("stability", 0.5) < 0.3,              # 极敏感者出走
    },
}


class Crisis:
    """单个进行中的危机。"""

    def __init__(self, crisis_type: str, day: int, town):
        cfg = CRISIS_CONFIG[crisis_type]
        self.crisis_type = crisis_type
        self.start_day = day
        self.duration_days = cfg["duration_days"]
        self.target = cfg["target"]
        self.energy_loss = cfg["energy_loss"]
        self.gold_loss = cfg["gold_loss"]
        self.desc = cfg["desc"]
        # 进度 0-100（玩家干预推进；恶化会倒退）
        self.progress = 0.0
        # 玩家干预记录
        self.interventions: List[Dict] = []
        # 结果：None / "resolved" / "worsened"
        self.outcome: Optional[str] = None
        self.town = town

    @property
    def active(self) -> bool:
        return self.outcome is None

    @property
    def days_remaining(self) -> int:
        return max(0, self.duration_days - (self.town.current_day - self.start_day))

    def react(self, agent) -> str:
        """NPC 性格化反应（每天触发一次，返回反应描述）。"""
        p = agent.identity.personality
        reactions = PERSONALITY_REACTIONS.get(self.crisis_type, {})
        # 依优先级匹配性格倾向
        for reaction, cond in reactions.items():
            if cond(p):
                desc_map = {
                    "organize": "组织大家转移物资",
                    "flee": "慌张地躲进屋里",
                    "help": "主动帮忙照顾邻里",
                    "care": "悉心照顾病人",
                    "panic": "惊慌失措，四处奔走",
                    "isolate": "把自己关在屋里",
                    "investigate": "四处打听真相",
                    "believe": "对谣言深信不疑",
                    "clarify": "努力向人们解释真相",
                    "farm": "拼命补种庄稼",
                    "hoard": "悄悄囤积食物",
                    "leave": "收拾行装准备离开小镇",
                }
                # 行为影响状态：逃跑/恐慌耗体力，囤积耗关系
                if reaction in ("flee", "panic", "leave"):
                    agent.state.energy = max(0, agent.state.energy - 10)
                    agent.state.mood = Mood.ANXIOUS
                elif reaction == "hoard":
                    for other_id in agent.state.social_ties:
                        agent.state.social_ties[other_id] -= 1
                return f"{agent.identity.name}{desc_map[reaction]}"
        return f"{agent.identity.name}照常生活，但心里记挂着这件事"

    def intervene(self, agent, action_type: str) -> str:
        """玩家干预。返回结果描述。"""
        if not self.active:
            return "这场危机已经结束了"
        inter = INTERVENTIONS.get(action_type)
        if not inter:
            return "无效的干预方式"

        # 玩家 AP 检查（旁观不消耗）
        if action_type != "watch":
            ap_cost = inter["ap"]
            if agent.state.ap < ap_cost:
                return f"行动力不足（剩余{agent.state.ap}点，需要{ap_cost}点）"
            agent.state.ap -= ap_cost

        if action_type == "watch":
            return "你选择袖手旁观，看着小镇自己面对这场危机"

        # 干预效果（澄清对谣言特别有效；帮忙对灾害/疫病有效）
        gain = inter["progress"]
        if action_type == "clarify" and self.crisis_type == CRISIS_RUMOR:
            gain *= 1.5
        elif action_type == "help" and self.crisis_type in (CRISIS_STORM, CRISIS_PLAGUE):
            gain *= 1.2
        self.progress = min(100, self.progress + gain)

        # 干预记录（供日报/档案可见）
        self.interventions.append({
            "agent": agent.identity.id,
            "type": action_type,
            "desc": inter["desc"],
            "day": self.town.current_day,
        })
        # 干预者与小镇居民关系提升（帮忙最多，澄清次之，调查最少）
        tie_bonus = {"help": 6, "clarify": 4, "investigate": 2}[action_type]
        for other in self.town.agents:
            if other.identity.id != agent.identity.id:
                other.state.social_ties[agent.identity.id] = other.state.social_ties.get(agent.identity.id, 0) + tie_bonus

        return f"你{inter['desc']}，小镇的危机缓解了一些（进度+{gain:.0f}）"

    def advance_day(self, agents: Optional[list] = None) -> Optional[str]:
        """每日结算：倒计时结束判定结局。返回结局（resolved/worsened）或 None。

        无人干预时，NPC 的性格化反应本身会推进危机（尽责者组织、亲善者帮忙）
        ——小镇能自己面对自己的危机，玩家伸手是锦上添花。
        """
        if not self.active:
            return None
        if self.days_remaining <= 0:
            if self.progress >= self.target:
                self.outcome = "resolved"
            else:
                self.outcome = "worsened"
            return self.outcome
        if not self.interventions:
            # 无玩家干预：NPC 自救（性格化反应贡献进度）
            npc_effort = 0
            if agents:
                for a in agents:
                    if a.identity.role.value == 'player':
                        continue
                    p = a.identity.personality
                    # 尽责者组织 / 亲善者帮忙 / 开放者调查 → 各贡献少量进度
                    if p.get("conscientiousness", 0.5) > 0.7:
                        npc_effort += 4
                    elif p.get("agreeableness", 0.5) > 0.7:
                        npc_effort += 3
                    elif p.get("openness", 0.5) > 0.7:
                        npc_effort += 2
            self.progress = max(0, min(100, self.progress + npc_effort - 5))
        return None

    def apply_outcome(self, agents) -> str:
        """结算结局对小镇的影响，返回日报描述。"""
        if self.outcome == "resolved":
            # 缓解：居民关系普遍提升，愉悦↑
            for a in agents:
                a.state.emotions["joy"] = min(100, a.state.emotions.get("joy", 50) + 15)
                a.state.mood = Mood.HAPPY
                for other_id in a.state.social_ties:
                    a.state.social_ties[other_id] += 1
            return f"危机「{self.desc}」在小镇的共同努力下化解了，大家都很感激"
        elif self.outcome == "worsened":
            # 恶化：体力/金币损失，焦虑↑，可能有人受伤
            victims = random.sample(agents, min(3, len(agents)))
            for a in agents:
                a.state.energy = max(0, a.state.energy - self.energy_loss)
                a.state.gold = max(0, a.state.gold - self.gold_loss)
                a.state.emotions["anxiety"] = min(100, a.state.emotions.get("anxiety", 50) + 20)
                a.state.mood = Mood.ANXIOUS
            victim_names = "、".join(v.identity.name for v in victims)
            return f"危机「{self.desc}」失控了，{victim_names}在这场灾难中受了伤，小镇元气大伤"
        return ""


def roll_crisis(day: int, town) -> Optional[Crisis]:
    """每日事件调度时，按概率触发危机（避免与已有危机叠加）。

    概率调低（合计约 12%/天）——危机是"小镇自己的事"，玩家旁观时小镇不应被频繁危机拖垮。
    """
    if any(c.active for c in town.crises):
        return None
    roll = random.random()
    if roll < 0.03:
        return Crisis(CRISIS_STORM, day, town)
    elif roll < 0.055:
        return Crisis(CRISIS_PLAGUE, day, town)
    elif roll < 0.09:
        return Crisis(CRISIS_RUMOR, day, town)
    elif roll < 0.12:
        return Crisis(CRISIS_FAMINE, day, town)
    return None
