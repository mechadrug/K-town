"""情绪系统 v2（gameplay-design-v4 §3）—— 让居民"会因行为而改变"

对应初心："被老师骂了，你感觉很沮丧，暗自决定下次一定不能再这样。
敏感的人冲击大、决定极端；大大咧咧的人无所谓、改变温和。"

机制：
1. 事件 × 性格 → 4 维情绪偏移（敏感者冲击大）
2. 情绪 → 决策渗透（焦虑→避险、愉悦→社交…）
3. 情绪记忆 → 习惯形成（情境→行为→概率表，近似 RL：行为→反馈→概率更新）
4. 习惯固化 → 性格慢速演化（阈值触发）
5. 情绪传染沿关系网（好友 > 陌生人，稳定高者抗传染）

不依赖 LLM、不做真 RL 训练：全部规则表实现，可调可测。
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, TYPE_CHECKING

from models import Mood

if TYPE_CHECKING:
    from agent import Agent

# 情绪基线（每 tick 向基线回归，速率 = 稳定性调制）
EMOTION_BASELINE = 50.0

# 事件 → 基础情绪偏移（正值=上升）
# 键与 tick._process_event 的 EventType 对应；子键为事件载荷字段
EVENT_EMOTION_OFFSETS: Dict[str, Dict[str, Dict[str, float]]] = {
    "festival": {"default": {"joy": 20, "anxiety": -10, "sadness": -5}},
    "disaster": {"default": {"anxiety": 30, "sadness": 10, "joy": -10}},
    "merchant_arrival": {"default": {"joy": 12, "anxiety": -5}},
    "weather_impact": {"default": {"sadness": 8, "joy": -5}},
    "animal_attack": {"default": {"anxiety": 25, "anger": 10, "sadness": 5}},
    "golden_discovery": {"default": {"joy": 25, "anxiety": -8}},
    "resource_found": {"default": {"joy": 8}},
    "item_crafted": {"default": {"joy": 6}},
    "social_encounter": {"default": {"joy": 5, "anxiety": -3}},
    "social_relation_change": {"default": {"joy": 6, "sadness": -4}},
    "rumor_spread": {"default": {"anxiety": 8}},
    "town_meeting": {"default": {"joy": 5, "anxiety": -2}},
    "mysterious_stranger": {"default": {"anxiety": 12, "joy": 4}},
    "weather_change": {"default": {"sadness": 3}},
    "work": {"default": {"joy": 4}},
    "rest": {"default": {"anxiety": -4, "sadness": -3}},
    "sleep": {"default": {"anxiety": -8, "sadness": -5}},
    "talk": {"default": {"joy": 4, "anxiety": -2}},
    "move": {"default": {"anxiety": -2}},
    "investigate": {"default": {"joy": 3, "anxiety": 3}},
    "criticized": {"default": {"sadness": 20, "anxiety": 10, "anger": 8}},
    "praised": {"default": {"joy": 15, "anxiety": -6}},
    "work_success": {"default": {"joy": 12}},
    "work_fail": {"default": {"sadness": 10, "anxiety": 6}},
    "hungry": {"default": {"anxiety": 8, "sadness": 6}},
    "tired": {"default": {"sadness": 5, "anger": 3}},
    "conflict": {"default": {"anger": 18, "anxiety": 8, "joy": -8}},
}

# 性格调制系数（敏感者=稳定低→冲击大；大大咧咧=稳定高→平淡）
# 各事件可覆盖；未覆盖时用 default 系数
_PERSONALITY_MODIFIERS: Dict[str, Dict[str, float]] = {
    "criticized": {"stability_low": 1.8, "stability_high": 0.5},
    "disaster": {"stability_low": 2.0, "stability_high": 0.7},
    "animal_attack": {"stability_low": 1.6, "stability_high": 0.8},
    "conflict": {"stability_low": 1.5, "stability_high": 0.7},
    "work_success": {"stability_low": 1.3, "stability_high": 0.8},
    "festival": {"extraversion_high": 1.3, "extraversion_low": 0.8},
}

# 习惯固化阈值：同情境同行为累计 N 次 → 触发性格演化
HABIT_SOLIDIFY_THRESHOLD = 7
# 单次行为反馈对概率表的更新幅度
HABIT_LEARNING_RATE = 0.08
# 习惯概率上限（防锁死）
HABIT_BIAS_MAX = 0.9
# 性格演化单次步长
PERSONALITY_DELTA = 1.0
# 性格演化月度上限（慢速演化）
PERSONALITY_MONTHLY_CAP = 2.0


def dominant_emotion(emotions: Dict[str, float]) -> Mood:
    """由 4 维情绪的主导者决定 Mood（UI 表情/光环层）。"""
    if not emotions:
        return Mood.NEUTRAL
    # 愉悦 >= 60 且为最高 → 开心
    if emotions.get("joy", 50) >= 60 and emotions["joy"] >= max(emotions.get("anxiety", 50), emotions.get("anger", 50), emotions.get("sadness", 50)):
        return Mood.HAPPY
    # 焦虑 >= 60 且为最高 → 焦虑
    if emotions.get("anxiety", 50) >= 60 and emotions["anxiety"] >= max(emotions.get("joy", 50), emotions.get("anger", 50), emotions.get("sadness", 50)):
        return Mood.ANXIOUS
    # 愤怒 >= 60 且为最高 → 愤怒
    if emotions.get("anger", 50) >= 60 and emotions["anger"] >= max(emotions.get("joy", 50), emotions.get("anxiety", 50), emotions.get("sadness", 50)):
        return Mood.ANGRY
    # 悲伤 >= 60 且为最高 → 悲伤
    if emotions.get("sadness", 50) >= 60 and emotions["sadness"] >= max(emotions.get("joy", 50), emotions.get("anxiety", 50), emotions.get("anger", 50)):
        return Mood.SAD
    return Mood.NEUTRAL


def apply_event_emotion(agent: Agent, event_key: str, magnitude: float = 1.0) -> Optional[Dict[str, float]]:
    """事件 × 性格 → 情绪偏移，返回实际偏移（供日志）。"""
    table = EVENT_EMOTION_OFFSETS.get(event_key)
    if not table:
        return None
    base = table.get("default", {})
    p = agent.identity.personality
    stability = p.get("stability", 0.5)
    extraversion = p.get("extraversion", 0.5)

    # 性格调制系数
    mods = _PERSONALITY_MODIFIERS.get(event_key, {})
    factor = 1.0
    for key, mult in mods.items():
        if key == "stability_low" and stability < 0.4:
            factor = max(factor, mult)
        elif key == "stability_high" and stability > 0.7:
            factor = min(factor, mult)
        elif key == "extraversion_high" and extraversion > 0.6:
            factor = max(factor, mult)
        elif key == "extraversion_low" and extraversion < 0.4:
            factor = min(factor, mult)

    applied = {}
    for k, v in base.items():
        delta = v * factor * magnitude
        agent.state.emotions[k] = max(0, min(100, agent.state.emotions.get(k, 50) + delta))
        applied[k] = round(delta, 1)
    # 情绪更新后同步 Mood（主导情绪决定 UI 表情）
    agent.state.mood = dominant_emotion(agent.state.emotions)
    return applied


def emotion_drift(agent: Agent) -> None:
    """每 tick 向基线回归（速率 = 稳定性：稳定高者情绪更平稳）。

    速率设计：单 tick 回归 8%-15%（一天 20 tick 足够从极端情绪回到基线），
    否则负面事件累积会把所有人推向 90+（实测 30 天全部焦虑/悲伤爆表）。
    """
    stability = agent.identity.personality.get("stability", 0.5)
    # 稳定高 → 回归快（不易长时间陷入极端情绪）；稳定低 → 慢（情绪波动持久）
    rate = 0.08 + stability * 0.07
    for k in ("joy", "anxiety", "anger", "sadness"):
        cur = agent.state.emotions.get(k, 50)
        agent.state.emotions[k] = cur + (EMOTION_BASELINE - cur) * rate


def emotion_to_decision_bias(agent: Agent) -> Dict[str, float]:
    """情绪 → 决策倾向修正（渗透 decide() 各层）。

    返回 action_type → 概率/系数加成，供 decide() 加权。
    """
    e = agent.state.emotions
    anxiety = e.get("anxiety", 50)
    joy = e.get("joy", 50)
    anger = e.get("anger", 50)
    sadness = e.get("sadness", 50)
    p = agent.identity.personality
    agreeableness = p.get("agreeableness", 0.5)

    bias = {}
    # 高焦虑 → 避险/调查倾向
    if anxiety >= 60:
        bias["investigate"] = (anxiety - 50) / 50 * 0.3
        bias["move"] = (anxiety - 50) / 50 * 0.2
    # 高愉悦 → 社交倾向
    if joy >= 60:
        bias["talk"] = (joy - 50) / 50 * 0.3
    # 高愤怒 → 冲突/效率↑但关系↓（亲和高者压住怒气）
    if anger >= 60:
        if agreeableness < 0.5:
            bias["conflict"] = (anger - 50) / 50 * 0.4
        bias["work"] = (anger - 50) / 50 * 0.15
    # 高悲伤 → 行动力↓、独处倾向
    if sadness >= 60:
        bias["rest"] = (sadness - 50) / 50 * 0.3
        bias["talk"] = -(sadness - 50) / 50 * 0.2
    return bias


def learn_habit(agent: Agent, situation: str, behavior: str, feedback: float) -> None:
    """情绪记忆 → 习惯形成（近似 RL）。

    situation: 情境（如"criticized_work"）
    behavior: 该情境下的行为（如"leave_early"）
    feedback: 行为后的情绪反馈（正=愉悦↑，负=悲伤/焦虑↑）
    """
    if not situation or not behavior:
        return
    table = agent.state.habit_bias.setdefault(situation, {})
    cur = table.get(behavior, 0.0)
    # 正反馈强化、负反馈削弱
    cur += feedback * HABIT_LEARNING_RATE
    cur = max(-0.5, min(HABIT_BIAS_MAX, cur))
    table[behavior] = round(cur, 3)

    # 记录习惯固化计数（达阈值触发性格演化）
    # 用 :: 分隔（situation/behavior 自身可能含下划线，不能用 _ 切分）
    key = f"{situation}::{behavior}"
    agent.state.habit_counts[key] = agent.state.habit_counts.get(key, 0) + 1


def solidify_habits(agent: Agent) -> List[str]:
    """每日结算：检查习惯固化计数 → 触发性格演化。返回演化的描述列表。"""
    changes = []
    p = agent.identity.personality
    stability = p.get("stability", 0.5)
    for key, count in list(agent.state.habit_counts.items()):
        if count >= HABIT_SOLIDIFY_THRESHOLD:
            situation, behavior = key.split("::", 1)
            # 习惯 → 性格演化（尽责性：准时/工作习惯；开放：探索习惯；亲和：社交习惯）
            delta = PERSONALITY_DELTA * (1.0 if stability >= 0.5 else 1.5)  # 敏感者改变更剧烈
            trait = _behavior_to_trait(behavior)
            if trait:
                p[trait] = max(0.0, min(1.0, p.get(trait, 0.5) + delta * 0.05))
                changes.append(f"{agent.identity.name}因习惯「{behavior}」{trait}略微改变")
            # 固化后重置计数（防反复触发）
            agent.state.habit_counts[key] = 0
    return changes


def _behavior_to_trait(behavior: str) -> Optional[str]:
    mapping = {
        "leave_early": "conscientiousness",
        "punctual": "conscientiousness",
        "work": "conscientiousness",
        "rest": "conscientiousness",
        "talk": "extraversion",
        "socialize": "extraversion",
        "explore": "openness",
        "investigate": "openness",
        "help": "agreeableness",
        "share": "agreeableness",
        "avoid": "stability",
    }
    return mapping.get(behavior)


def spread_emotion(agent: Agent, others: List[Agent]) -> None:
    """情绪传染沿关系网（好友 > 陌生人；稳定高者抗传染）。

    在同地点人群中，若周围主导情绪为焦虑/悲伤且强度高，向自己渗透；
    渗透率 = 关系强度加权，抗性 = 稳定性。
    """
    if not others:
        return
    stability = agent.identity.personality.get("stability", 0.5)
    resist = stability * 0.5

    weighted_anxiety = 0.0
    weighted_sadness = 0.0
    total_weight = 0.0
    for other in others:
        tie = agent.state.social_ties.get(other.identity.id, 0)
        weight = max(0.1, (tie + 10) / 20)  # 好友权重大，陌生人权重小
        weighted_anxiety += other.state.emotions.get("anxiety", 50) * weight
        weighted_sadness += other.state.emotions.get("sadness", 50) * weight
        total_weight += weight
    if total_weight <= 0:
        return

    avg_anxiety = weighted_anxiety / total_weight
    avg_sadness = weighted_sadness / total_weight

    # 周围焦虑高 → 自己被传染（抗性削弱）
    if avg_anxiety > 65:
        transfer = (avg_anxiety - 50) * 0.15 * (1 - resist)
        agent.state.emotions["anxiety"] = max(0, min(100, agent.state.emotions.get("anxiety", 50) + transfer))
    if avg_sadness > 65:
        transfer = (avg_sadness - 50) * 0.12 * (1 - resist)
        agent.state.emotions["sadness"] = max(0, min(100, agent.state.emotions.get("sadness", 50) + transfer))

    # 传染后同步 Mood
    agent.state.mood = dominant_emotion(agent.state.emotions)
