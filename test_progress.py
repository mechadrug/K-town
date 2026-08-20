"""长期目标线专项验证（Phase 8）—— 身世之谜碎片收集 + 重建弧线

运行：python test_progress.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from config import load_config
from world import World
from events import EventBus
from agent import populate_agents
from knowledge import KnowledgeEngine
from storage import Storage
from llm import LLMClient
from tick import TickEngine

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


def build_engine():
    cfg = load_config("config.yaml")
    world = World()
    bus = EventBus()
    storage = Storage("test_progress.db")
    knowledge = KnowledgeEngine()
    llm = LLMClient(cfg.llm.base_url, "", cfg.llm.model, cfg.llm.provider)
    agents = populate_agents()
    for a in agents:
        world.add_agent_to_location(a.identity.id, a.state.location)
    engine = TickEngine(world, bus, agents, knowledge, storage, llm, day_length=20, auto_reset=True, db=storage)
    return engine, agents, storage


async def main():
    print("=== 1. 身世之谜：思考得线索 → 调查收集碎片（游戏化流程） ===\n")
    engine, agents, storage = build_engine()
    player = next(a for a in agents if a.identity.role.value == 'player')
    # 依次提交触及不同真相的思考 → 获得线索
    keywords = ["遗迹", "石碑", "十三", "玉佩", "大缓变"]
    for i, kw in enumerate(keywords):
        engine._insight_day = 0  # 重置每日限制
        msg = engine._check_insight(player, f"我今天在思考关于{kw}的事情")
        print(f"  线索{i+1}: {msg}")
    check("思考获得 5 条线索", len(engine.lore_clues) == 5)
    check("线索指向具体地点", all(loc in ("square", "workshop", "wilderness", "school", "mine") for loc in engine.lore_clues.values()))
    # 去对应地点调查（模拟夜间探索→必得）
    for lore_key, loc in list(engine.lore_clues.items()):
        player.state.location = loc
        msg = engine._collect_lore_fragment(player, loc, at_night=True)
        print(f"  收集[{lore_key}@{loc}]: {msg}")
    check("调查收集 5 片碎片", len(engine.lore_fragments) == 5)
    check("解锁大缓变真相", "大缓变" in str(engine.lore_unlocked))
    check("碎片总数上限", engine.LORE_TOTAL_FRAGMENTS == 5)
    # 重复思考同一关键词 → 已收集不再给线索
    engine._insight_day = 0
    engine._check_insight(player, "我今天在思考关于遗迹的事情")
    check("已收集碎片不再重复给线索", "ruins" not in engine.lore_clues)

    print("\n=== 2. 重建弧线：小镇修缮进度 ===\n")
    engine._upgrades_done = 0
    total_gold = sum(a.state.gold for a in agents)
    threshold = 100 * (engine._upgrades_done + 1) ** 2
    print(f"  当前金币 {total_gold}, 下一修缮阈值 {threshold}")
    check("修缮进度可计算", threshold == 100)
    check("等级上限 5", all(lvl <= 5 for lvl in engine.world.state.location_levels.values()))

    print("\n=== 3. 重建触发（注入金币到阈值） ===\n")
    for a in agents:
        a.state.gold += 200  # 注入足够金币
    engine._town_upgrade_check()
    check("金币达标触发修缮", engine._upgrades_done >= 1)
    check("某地点等级提升", any(lvl > 1 for lvl in engine.world.state.location_levels.values()))

    storage.close()
    import os
    try:
        os.remove("test_progress.db")
    except Exception:
        pass

    print(f"\n===== 结果: {PASS} passed, {FAIL} failed =====")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
