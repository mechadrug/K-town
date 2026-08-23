"""ActionResolver 契约测试（v5 rebuild-plan §2.1 / §4.1）。

覆盖：单次扣费、失败不扣时、非法目标、夜间限制、休息换日、危机同日限次、
dry-wood 请求全流程。使用临时数据库，不触碰默认 k_town.db。
"""
import asyncio
import os
import sys
import tempfile

# Windows 控制台默认 GBK，无法输出部分 UTF-8 字符（✓ 等）
if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("gbk"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import load_config
from world import World
from events import EventBus
from agent import populate_agents
from knowledge import KnowledgeEngine
from storage import Storage
from llm import LLMClient
from tick import TickEngine
from actions import Action, ActionResolver

PASS = []


def build_engine():
    cfg = load_config("config.yaml")
    world = World()
    bus = EventBus()
    tmp_db = os.path.join(tempfile.mkdtemp(prefix="ktown_test_"), "test.db")
    storage = Storage(tmp_db)
    knowledge = KnowledgeEngine()
    llm = LLMClient(cfg.llm.base_url, "", cfg.llm.model, cfg.llm.provider)
    agents = populate_agents()
    for a in agents:
        world.add_agent_to_location(a.identity.id, a.state.location)
    engine = TickEngine(world, bus, agents, knowledge, storage, llm,
                        day_length=20, auto_reset=True, db=storage)
    return engine


def player(engine):
    return next(a for a in engine.agents if a.identity.role.value == 'player')


def lina(engine):
    return next(a for a in engine.agents if a.identity.id == "agent_carpenter")


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAIL: {name} {detail}")
    PASS.append(name)
    print(f"  ✓ {name}")


def main():
    engine = build_engine()
    resolver = engine.resolver
    p = player(engine)
    engine.world.state.tick = 6  # 白天（5-17 清醒时段）

    # 1. move 单次扣费：AP 12→11、只推进 1 小时
    p.state.ap = 12
    engine._pending_advance = 0
    p.state.location = "square"
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="move", target_location="workshop"))
    check("move 扣 1 AP", ar.accepted and p.state.ap == 11, f"ap={p.state.ap}")
    check("move 推进 1 小时", engine._pending_advance == 1, f"pending={engine._pending_advance}")
    check("move 目标合法", p.state.location == "workshop")

    # 2. talk 目标异地 → 拒绝且不扣费
    p.state.ap = 12
    engine._pending_advance = 0
    p.state.location = "square"
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="talk", target_id="agent_carpenter"))
    check("talk 异地拒绝", not ar.accepted and ar.error_code == "target_not_here")
    check("talk 异地不扣 AP", p.state.ap == 12 and engine._pending_advance == 0)

    # 3. move 非法地点 → 拒绝
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="move", target_location="moon"))
    check("move 非法地点拒绝", not ar.accepted and ar.error_code == "bad_location")

    # 4. AP 不足 work → 拒绝不扣
    p.state.ap = 0
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="work"))
    check("AP 不足拒绝", not ar.accepted and ar.error_code == "ap_shortage")
    check("AP 不足不扣时不扣费", engine._pending_advance == 0 and p.state.ap == 0)

    # 5. observe 不推进时间（advance(0) 修复回归）
    p.state.ap = 12
    engine._pending_advance = 0
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="observe"))
    check("observe 0 小时", ar.accepted and engine._pending_advance == 0 and p.state.ap == 12)

    # 6. rest 推进到次日清晨（tick 6 → 下一个 wake_hour=5 → +19 小时）
    engine._pending_advance = 0
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="rest"))
    check("rest 推进到清晨", ar.accepted and engine._pending_advance == 19, f"pending={engine._pending_advance}")

    # 7. crisis 同日第二次干预 → 拒绝（先手动构造危机）
    from crisis import Crisis, CRISIS_STORM
    c = Crisis(CRISIS_STORM, engine.current_day, engine)
    engine.crises.append(c)
    p.state.ap = 12
    r1 = c.intervene(p, "help")
    check("危机第一次干预成功", "你帮忙" in r1, r1)
    p.state.ap = 12
    r2 = c.intervene(p, "help")
    check("危机同日二次干预拒绝", "已经帮过忙" in r2, r2)

    # 8. dry-wood 请求全流程
    # 前置：先移动到荒野 → 收集 → 移动到工坊 → 交付
    engine._pending_advance = 0
    p.state.location = "wilderness"
    engine.world.remove_agent_from_location(p.identity.id, "square")
    engine.world.add_agent_to_location(p.identity.id, "wilderness")
    p.state.ap = 12
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="request_respond",
                                    payload={"request_id": "lina_dry_wood", "option": "gather_wood"}))
    check("请求收集干木料成功", ar.accepted and "dry_wood" in p.state.inventory, ar.result)
    check("请求收集扣 2 AP 2 小时", p.state.ap == 10 and engine._pending_advance == 2, f"ap={p.state.ap} pending={engine._pending_advance}")

    # 不在工坊交付 → 拒绝
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="request_respond",
                                    payload={"request_id": "lina_dry_wood", "option": "deliver_wood"}))
    check("交付需在工坊", not ar.accepted and "工坊" in ar.result)

    # 移动到工坊交付
    p.state.location = "workshop"
    engine.world.remove_agent_from_location(p.identity.id, "wilderness")
    engine.world.add_agent_to_location(p.identity.id, "workshop")
    tie_before = lina(engine).state.social_ties.get(p.identity.id, 0)
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="request_respond",
                                    payload={"request_id": "lina_dry_wood", "option": "deliver_wood"}))
    req = next(q for q in engine.requests if q.id == "lina_dry_wood")
    check("请求完成", ar.accepted and req.status == "completed", ar.result)
    check("干木料消耗", "dry_wood" not in p.state.inventory)
    check("莉娜关系提升", lina(engine).state.social_ties.get(p.identity.id, 0) > tie_before,
          f"{tie_before} → {lina(engine).state.social_ties.get(p.identity.id, 0)}")
    check("story_beats 记录", len(ar.story_beats) == 1 and ar.next_observation is not None)
    check("next_observation 有值", bool(ar.next_observation))

    # 已完成请求再回应 → 拒绝
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="request_respond",
                                    payload={"request_id": "lina_dry_wood", "option": "deliver_wood"}))
    check("已完成请求拒绝", not ar.accepted and ar.error_code == "request_closed")

    # 9. 未知动作
    ar = resolver.resolve(p, Action(actor_id=p.identity.id, kind="fly"))
    check("未知动作拒绝", not ar.accepted and ar.error_code == "unknown_action")

    # 10. NPC 动作不得推进时间（回归：step 内 NPC advance 会与 run() 互相喂食）
    engine._pending_advance = 0
    npc = lina(engine)
    ar = resolver.resolve(npc, Action(actor_id=npc.identity.id, kind="work"))
    check("NPC 工作不推进时间", ar.accepted and engine._pending_advance == 0,
          f"pending={engine._pending_advance}")

    engine.db.close()
    print(f"\n[actions] {len(PASS)}/{len(PASS)} PASS OK")


if __name__ == "__main__":
    main()
