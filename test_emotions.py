"""情绪闭环专项验证（Phase 6）—— 验证初心核心："被批评→悲伤→行为改变→习惯→性格演化"

运行：python test_emotions.py
"""
import random
import sys
sys.path.insert(0, '.')

from agent import Agent, AgentIdentity, populate_agents
from models import Role, Mood
from emotions import (
    apply_event_emotion, dominant_emotion, emotion_to_decision_bias,
    learn_habit, solidify_habits, spread_emotion, HABIT_SOLIDIFY_THRESHOLD,
)

PASS = 0
FAIL = 0

def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")

def make_agent(name, personality):
    return Agent(AgentIdentity(id=f"test_{name}", name=name, role=Role.FORAGER, personality=personality))

print("=== 1. 同一事件，敏感者 vs 大大咧咧 → 情绪偏移不同（初心核心） ===\n")
sensitive = make_agent("敏感者", {"stability": 0.2, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})
casual = make_agent("大大咧咧", {"stability": 0.9, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})

d1 = apply_event_emotion(sensitive, "criticized")
d2 = apply_event_emotion(casual, "criticized")
print(f"  敏感者被批评 → {d1}")
print(f"  大大咧咧被批评 → {d2}")
check("敏感者悲伤冲击 > 大大咧咧", d1["sadness"] > d2["sadness"])
check("敏感者悲伤显著上升(×1.8)", d1["sadness"] >= 36)
check("大大咧咧悲伤温和(×0.5)", d2["sadness"] <= 12)

print("\n=== 2. 情绪 → 决策渗透（焦虑→避险/调查） ===\n")
anxious = make_agent("焦虑者", {"stability": 0.2, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})
anxious.state.emotions["anxiety"] = 85
bias = emotion_to_decision_bias(anxious)
print(f"  高焦虑者决策偏置: {bias}")
check("高焦虑 → investigate 偏置 > 0", bias.get("investigate", 0) > 0)

angry = make_agent("愤怒者", {"stability": 0.2, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.2})
angry.state.emotions["anger"] = 90
bias2 = emotion_to_decision_bias(angry)
print(f"  高愤怒者决策偏置: {bias2}")
check("高愤怒+低亲和 → conflict 偏置 > 0", bias2.get("conflict", 0) > 0)

print("\n=== 3. 主导情绪 → Mood（UI 表情层） ===\n")
check("joy 主导 → HAPPY", dominant_emotion({"joy": 80, "anxiety": 40, "anger": 20, "sadness": 10}) == Mood.HAPPY)
check("anxiety 主导 → ANXIOUS", dominant_emotion({"joy": 30, "anxiety": 80, "anger": 20, "sadness": 40}) == Mood.ANXIOUS)
check("全低 → NEUTRAL", dominant_emotion({"joy": 50, "anxiety": 50, "anger": 50, "sadness": 50}) == Mood.NEUTRAL)

print("\n=== 4. 习惯形成（近似 RL）：行为→反馈→概率表更新 ===\n")
worker = make_agent("勤奋者", {"stability": 0.5, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})
# 模拟"被批评后决定提早出门"：每次准时工作获得正反馈
for i in range(5):
    learn_habit(worker, "criticized_work", "leave_early", 1.0)
    learn_habit(worker, "criticized_work", "late", -1.0)
print(f"  习惯表: {worker.state.habit_bias}")
check("'准时'习惯概率为正", worker.state.habit_bias["criticized_work"]["leave_early"] > 0)
check("'迟到'习惯概率为负", worker.state.habit_bias["criticized_work"]["late"] < 0)
check("习惯计数达阈值", worker.state.habit_counts["criticized_work::leave_early"] >= 5)

print("\n=== 5. 习惯固化 → 性格演化（初心：性格做出改变） ===\n")
before = worker.identity.personality["conscientiousness"]
# 补足到阈值
while worker.state.habit_counts.get("criticized_work::leave_early", 0) < HABIT_SOLIDIFY_THRESHOLD:
    learn_habit(worker, "criticized_work", "leave_early", 1.0)
changes = solidify_habits(worker)
after = worker.identity.personality["conscientiousness"]
print(f"  演化: {changes}")
print(f"  尽责性: {before} → {after}")
check("尽责性提升", after > before)
check("演化记录可观测", len(changes) > 0)

print("\n=== 6. 情绪传染沿关系网（好友 > 陌生人，稳定高者抗传染） ===\n")
calm = make_agent("平静者", {"stability": 0.9, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})
nervous = make_agent("易感者", {"stability": 0.2, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})
source = make_agent("恐慌源", {"stability": 0.5, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})
source.state.emotions["anxiety"] = 95
# 恐慌源是平静者的好友、易感者的陌生人
calm.state.social_ties[source.identity.id] = 40
nervous.state.social_ties[source.identity.id] = 0
spread_emotion(calm, [source])
spread_emotion(nervous, [source])
print(f"  平静者(好友,高稳定) anxiety: {calm.state.emotions['anxiety']:.1f}")
print(f"  易感者(陌生人,低稳定) anxiety: {nervous.state.emotions['anxiety']:.1f}")
check("易感者被传染更多", nervous.state.emotions["anxiety"] > calm.state.emotions["anxiety"])

print("\n=== 7. 完整闭环示例（初心：被骂→沮丧→决定不再迟到→习惯→性格改变） ===\n")
pupil = make_agent("学生", {"stability": 0.3, "extraversion": 0.4, "conscientiousness": 0.4, "openness": 0.6, "agreeableness": 0.5})
# 第一天：被批评（敏感者冲击大）
apply_event_emotion(pupil, "criticized")
print(f"  第1天被批评 → 情绪: {pupil.state.emotions}, Mood: {pupil.state.mood.value}")
check("被批评后悲伤显著", pupil.state.emotions["sadness"] >= 55)
# 次日：因为沮丧，决定提早出门（行为改变）
learn_habit(pupil, "criticized_work", "leave_early", 1.0)
# 连续几天准时 → 愉悦反馈
for _ in range(HABIT_SOLIDIFY_THRESHOLD - 1):
    learn_habit(pupil, "criticized_work", "leave_early", 1.0)
# 性格演化
p_before = pupil.identity.personality["conscientiousness"]
pupil_changes = solidify_habits(pupil)
p_after = pupil.identity.personality["conscientiousness"]
print(f"  尽责性: {p_before} → {p_after} | 演化: {pupil_changes}")
check("敏感者改变剧烈(演化发生)", p_after > p_before and len(pupil_changes) > 0)

print(f"\n===== 结果: {PASS} passed, {FAIL} failed =====")
sys.exit(1 if FAIL else 0)
