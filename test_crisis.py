"""危机系统专项验证（Phase 7）—— "小镇会出事，你能伸手"

运行：python test_crisis.py
"""
import sys
sys.path.insert(0, '.')

from agent import Agent, AgentIdentity
from models import Role, Mood
from crisis import (
    Crisis, roll_crisis, CRISIS_STORM, CRISIS_PLAGUE, CRISIS_RUMOR, CRISIS_FAMINE,
    INTERVENTIONS,
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

class FakeTown:
    def __init__(self, agents, current_day=1):
        self.agents = agents
        self.current_day = current_day
        self.crises = []

def make_agent(name, personality):
    a = Agent(AgentIdentity(id=f"t_{name}", name=name, role=Role.FORAGER, personality=personality))
    a.state.ap = 12
    return a

# 玩家与 NPC
player = make_agent("玩家", {"stability": 0.5, "extraversion": 0.6, "conscientiousness": 0.5, "openness": 0.7, "agreeableness": 0.6})
player.identity.id = "agent_player"
player.identity.role = Role.PLAYER
organizer = make_agent("尽责者", {"stability": 0.6, "extraversion": 0.5, "conscientiousness": 0.9, "openness": 0.5, "agreeableness": 0.6})
panic = make_agent("敏感者", {"stability": 0.2, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5})
carer = make_agent("亲善者", {"stability": 0.7, "extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.9})
agents = [player, organizer, panic, carer]

print("=== 1. 危机触发（概率门 + 不叠加） ===\n")
town = FakeTown(agents)
# 强制触发一次
crisis = Crisis(CRISIS_STORM, 1, town)
town.crises.append(crisis)
check("危机创建且激活", crisis.active)
check("持续 3 天", crisis.days_remaining == 3)
check("达标进度 60", crisis.target == 60)

print("\n=== 2. 性格化反应（同一危机，不同性格不同反应） ===\n")
r_org = crisis.react(organizer)
r_panic = crisis.react(panic)
r_care = crisis.react(carer)
print(f"  尽责者: {r_org}")
print(f"  敏感者: {r_panic}")
print(f"  亲善者: {r_care}")
check("尽责者组织", "组织" in r_org)
check("敏感者慌张", "慌张" in r_panic or "躲" in r_panic)
check("亲善者帮忙", "帮忙" in r_care)
check("敏感者体力下降(恐慌代价)", panic.state.energy < 100)

print("\n=== 3. 玩家干预（帮忙/调查/澄清/旁观） ===\n")
crisis2 = Crisis(CRISIS_STORM, 1, town)
town.crises.append(crisis2)
result = crisis2.intervene(player, "help")
print(f"  帮忙: {result}")
check("帮忙消耗 3 AP", player.state.ap == 9)
# 帮忙对暴风雨（灾害）效果×1.2：25×1.2=30
check("进度 +30（灾害加成）", crisis2.progress == 30)
check("帮忙提升关系", carer.state.social_ties["agent_player"] == 6)

result2 = crisis2.intervene(player, "watch")
print(f"  旁观: {result2}")
check("旁观不消耗 AP", player.state.ap == 9)
check("旁观不加进度", crisis2.progress == 30)

# 澄清对谣言特别有效
crisis3 = Crisis(CRISIS_RUMOR, 1, town)
town.crises.append(crisis3)
result3 = crisis3.intervene(player, "clarify")
print(f"  谣言澄清: {result3}")
check("谣言澄清效果×1.5", crisis3.progress == 15)

print("\n=== 4. 结局分支：达标→缓解，未达标→恶化 ===\n")
# 缓解
resolved = Crisis(CRISIS_PLAGUE, 1, town)
resolved.progress = 100
resolved.duration_days = 1
town.current_day = 2
outcome = resolved.advance_day(agents)
print(f"  达标结局: {outcome} | 描述: {resolved.apply_outcome(agents)}")
check("达标 → resolved", outcome == "resolved")
check("缓解后愉悦↑", all(a.state.emotions["joy"] > 50 for a in agents))

# 恶化
worsened = Crisis(CRISIS_FAMINE, 1, town)
worsened.progress = 10
worsened.duration_days = 1
town.current_day = 2
energy_before = {a.identity.id: a.state.energy for a in agents}
outcome2 = worsened.advance_day(agents)
desc = worsened.apply_outcome(agents)
print(f"  未达标结局: {outcome2} | 描述: {desc}")
check("未达标 → worsened", outcome2 == "worsened")
check("恶化后体力下降", all(a.state.energy < energy_before[a.identity.id] for a in agents))
check("恶化后焦虑↑", all(a.state.emotions["anxiety"] > 50 for a in agents))

print("\n=== 5. 无人干预时 NPC 自救（尽责者/亲善者推进进度） ===\n")
drift = Crisis(CRISIS_RUMOR, 1, town)
drift.progress = 40
drift.duration_days = 3
town.current_day = 2
drift.advance_day(agents)  # 第一天没人干预，但尽责者/亲善者/开放者自救
print(f"  无人干预进度: {drift.progress}（NPC 自救应推进）")
check("无人干预 → NPC 自救推进进度", drift.progress > 40)

print("\n=== 6. 危机触发不叠加 ===\n")
town2 = FakeTown(agents, current_day=5)
town2.crises.append(Crisis(CRISIS_STORM, 5, town2))
new = roll_crisis(5, town2)
check("已有危机时不触发新危机", new is None)

print(f"\n===== 结果: {PASS} passed, {FAIL} failed =====")
sys.exit(1 if FAIL else 0)
