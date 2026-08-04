"""K-town 冒烟测试：直驱 TickEngine.step()，验证核心闭环真实运转。

对应设计主计划（docs/design-master-plan-2026-08-04.md）Phase 0.7 验收：
1. Agent 的动作（move/work/talk...）真实改变世界（位置、体力变化）。
2. 模拟可跨天：每日摘要生成并落库，current_day 递增。
3. 知识引擎产生并传播知识。
4. 全程无未捕获异常。

运行：python test_smoke.py
"""

import asyncio

from config import load_config
from world import World
from events import EventBus
from agent import populate_agents
from knowledge import KnowledgeEngine
from storage import Storage
from llm import LLMClient
from tick import TickEngine


def build_engine():
    cfg = load_config("config.yaml")
    world = World()
    bus = EventBus()
    storage = Storage()
    knowledge = KnowledgeEngine()
    # 空 key → LLM 走 mock 路径，保证测试确定性与速度
    llm = LLMClient(cfg.llm.base_url, "", cfg.llm.model, cfg.llm.provider)
    agents = populate_agents()
    for a in agents:
        world.add_agent_to_location(a.identity.id, a.state.location)
    engine = TickEngine(world, bus, agents, knowledge, storage, llm,
                        day_length=20, auto_reset=True, db=storage)
    return engine, agents


async def run():
    engine, agents = build_engine()
    initial_locs = {a.identity.id: a.state.location for a in agents}
    errors = []
    moved = set()

    for tick in range(1, 61):  # 跑 60 tick（跨 2 天以上）
        try:
            await engine.step()
        except Exception as e:
            errors.append(f"tick {tick}: {type(e).__name__}: {e}")
            break
        for a in agents:
            if a.state.location != initial_locs[a.identity.id]:
                moved.add(a.identity.id)

    moved_count = len(moved)
    energy_changed = sum(1 for a in agents if a.state.energy < 100)
    db_summaries = engine.db.get_day_summaries()

    print(f"[smoke] 60 ticks | moved {moved_count}/{len(agents)} | energy<100 {energy_changed}/{len(agents)}")
    print(f"[smoke] current_day={engine.current_day} | in-mem summaries={len(engine.day_summaries)} | persisted={len(db_summaries)}")
    print(f"[smoke] knowledge claims={len(engine.knowledge.claims)}")
    if errors:
        print("[smoke] EXCEPTIONS:"); [print("   ", e) for e in errors[:8]]

    assert moved_count > 0, "FAIL: 没有 Agent 移动 —— 决策未执行"
    assert energy_changed > 0, "FAIL: 体力从未消耗 —— 动作未执行"
    assert engine.current_day >= 2, f"FAIL: 未能跨天 (current_day={engine.current_day})"
    assert len(engine.day_summaries) >= 1, "FAIL: 每日摘要未生成"
    assert len(db_summaries) >= 1, "FAIL: 每日摘要未落库"
    assert len(engine.knowledge.claims) > 0, "FAIL: 知识从未产生"
    assert not errors, f"FAIL: 存在异常 {len(errors)} 次"
    print("[smoke] ALL PASS OK")


if __name__ == "__main__":
    asyncio.run(run())
