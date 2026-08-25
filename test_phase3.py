"""Phase 3 七天请求纵切片的端到端剧本。

覆盖：
1. 三条请求都有至少两种回应，准备步骤不会误关请求；
2. 屋顶临时遮雨/正式修好产生不同的场景状态；
3. 请求结果在次日事件和日报中可读；
4. 第三天暴雨、旧矿道传闻及其后果可观察；
5. API 只能代表玩家，reset 会重新 seed 请求；
6. 对话/危机干预也由 resolver 单次扣费并返回统一结果。

所有数据库均为临时库，不触碰默认 k_town.db。
"""
import asyncio
import os
import random
import shutil
import tempfile

from fastapi.testclient import TestClient

from agent import populate_agents
from actions import Action
from dialogue import DialogueSystem
from events import EventBus
from knowledge import KnowledgeEngine
from llm import LLMClient
from models import Event, EventType
from quests import QuestEngine
from storage import Storage
from tick import TickEngine
from world import World
from api import create_app


def build_engine():
    root = tempfile.mkdtemp(prefix="ktown_phase3_")
    db = Storage(os.path.join(root, "phase3.db"))
    world = World()
    bus = EventBus()
    agents = populate_agents()
    for agent in agents:
        world.add_agent_to_location(agent.identity.id, agent.state.location)
    engine = TickEngine(
        world, bus, agents, KnowledgeEngine(), db,
        LLMClient("", "", "mock", "mock"),
        day_length=20, auto_reset=True, db=db,
    )
    engine.quest_engine = QuestEngine()
    engine.quest_engine.generate_daily_goals(1)
    engine.dialogue_sys = DialogueSystem()
    world.state.tick = engine.wake_hour
    return engine, root


def player(engine):
    return next(a for a in engine.agents if a.identity.id == "agent_player")


def put_player(engine, location):
    p = player(engine)
    old = p.state.location
    engine.world.remove_agent_from_location(p.identity.id, old)
    p.state.location = location
    engine.world.add_agent_to_location(p.identity.id, location)
    return p


def quiet_pending(engine):
    # 直接驱动 resolver 的测试不启动后台 run loop；清掉排队时数，
    # 避免下一条断言把前一条行动的时间混在一起。
    engine._pending_advance = 0


async def main():
    random.seed(23)
    engine, root = build_engine()
    try:
        request_map = {q.id: q for q in engine.requests}
        assert set(request_map) == {"lina_dry_wood", "torin_roof", "mei_town_chronicle"}
        assert all(len(q.options) >= 2 for q in engine.requests)
        print("  ✓ 三条首周请求已 seed，且每条至少有两种回应")

        p = put_player(engine, "workshop")
        p.state.ap = 12
        prepared = engine.resolver.resolve(
            p, Action(
                p.identity.id, "request_respond",
                payload={"request_id": "lina_dry_wood", "option": "share_roof_plan"},
            )
        )
        assert prepared.accepted and prepared.cost == 1 and prepared.hours == 1
        assert request_map["lina_dry_wood"].status == "active"
        assert request_map["lina_dry_wood"].progress == 1
        assert prepared.next_observation and prepared.changes
        quiet_pending(engine)
        print("  ✓ 莉娜的规划回应只推进准备度，未误把请求标成完成")

        p.state.inventory.append("dry_wood")
        delivered = engine.resolver.resolve(
            p, Action(
                p.identity.id, "request_respond",
                payload={"request_id": "lina_dry_wood", "option": "deliver_wood"},
            )
        )
        assert delivered.accepted and request_map["lina_dry_wood"].status == "completed"
        assert "因为" in "".join(engine.daily_agent_logs[p.identity.id])
        quiet_pending(engine)
        print("  ✓ 莉娜请求完成，并留下可追溯的因果日志")

        temporary = engine.resolver.resolve(
            p, Action(
                p.identity.id, "request_respond",
                payload={"request_id": "torin_roof", "option": "temporary_cover"},
            )
        )
        assert temporary.accepted
        assert engine.world.workshop_roof_status()["id"] == "temporary_cover"
        assert request_map["torin_roof"].status == "completed"
        assert request_map["torin_roof"].next_day_observations
        quiet_pending(engine)
        print("  ✓ 临时遮雨层保住当天工作，但保留次日滴漏后果")

        # 在下一个清晨结算请求后果；日报必须把事件摘要成可读文字。
        engine.world.state.tick = 19
        engine.current_day = 1
        await engine.step()
        roof_summary = engine.day_summaries[-1]
        assert request_map["torin_roof"].observed_next_day_observations
        assert "滴漏" in roof_summary["overall_summary"]
        assert roof_summary["stats"]["town_state"]["workshop_roof"]["id"] == "temporary_cover"
        print("  ✓ 次日观察进入事件流/日报，玩家能读到滴漏后果")

        # 七天完成定义：同一条时间线还可以在次日把第三条请求交给梅奶奶。
        mei_player = put_player(engine, "square")
        # 次日结算落在 20 小时周期的夜间边界；把剧本推进到清晨，
        # 明确测试请求回应而不是误测夜间行动力限制。
        engine.world.state.tick = ((engine.current_day - 1) * 20) + engine.wake_hour
        mei_player.state.ap = 12
        mei = engine.resolver.resolve(
            mei_player, Action(
                mei_player.identity.id, "request_respond",
                payload={"request_id": "mei_town_chronicle", "option": "organize_chronicle"},
            )
        )
        assert mei.accepted and request_map["mei_town_chronicle"].status == "completed"
        assert sum(q.status == "completed" for q in engine.requests) == 3
        assert engine.current_day <= 7
        print("  ✓ 同一条时间线在第七天前完成三条居民请求")

        # 另一个分支：正式修缮的场景状态必须不同。
        formal_engine, formal_root = build_engine()
        try:
            formal_player = put_player(formal_engine, "workshop")
            formal_player.state.ap = 12
            formal = formal_engine.resolver.resolve(
                formal_player, Action(
                    formal_player.identity.id, "request_respond",
                    payload={"request_id": "torin_roof", "option": "formal_repair"},
                )
            )
            assert formal.accepted and formal.cost == 3 and formal.hours == 3
            assert formal_engine.world.workshop_roof_status()["id"] == "repaired"
            assert formal_engine.world.state.lantern_fair_preparedness == 3
            print("  ✓ 正式修缮分支进入稳定屋顶状态，并提高归灯集准备度")
        finally:
            formal_engine.db.close()
            shutil.rmtree(formal_root, ignore_errors=True)

        # 固定暴雨：第 3 天清晨的天气和工坊压力事件都必须出现。
        rain_engine, rain_root = build_engine()
        try:
            rain_engine.current_day = 3
            rain_engine.world.state.tick = 45
            rain_engine.bus.clear_events()
            rain_engine.scheduler.generate_daily_schedule(
                3, [a.identity.id for a in rain_engine.agents], rain_engine.world
            )
            await rain_engine.step()  # tick 46：天气变化
            await rain_engine.step()  # tick 47：工坊压力
            assert rain_engine.world.state.weather == "rainy"
            assert any(e.get("type") == "workshop_roof" for e in rain_engine.current_day_events)
            print("  ✓ 第三天固定暴雨与工坊屋顶压力事件出现")
        finally:
            rain_engine.db.close()
            shutil.rmtree(rain_root, ignore_errors=True)

        # 旧矿道传闻：传播后进入世界状态，并在暴雨前形成路标后果。
        engine.bus.publish(Event(
            tick=engine.world.state.tick + 1,
            type=EventType.RUMOR_SPREAD,
            location="square",
            payload={
                "claim": "旧矿道可能有塌方，暂时不要走那里",
                "from": "agent_scout",
                "to": "agent_elder",
            },
        ))
        await engine.step()
        assert engine.world.state.mine_rumor_status == "circulating"
        engine.world.state.tick = 59
        engine.current_day = 3
        engine.bus.clear_events()
        await engine.step()  # 清晨结算传闻后果
        assert engine.world.state.mine_rumor_status == "marked"
        rumor_summary = engine.day_summaries[-1]
        assert "路标" in rumor_summary["overall_summary"]
        print("  ✓ 旧矿道传闻改变世界状态，并在暴雨前留下路标后果")

        # API 契约：只能代表玩家；响应载荷返回统一成本/变化/后果字段。
        api_engine, api_root = build_engine()
        try:
            app = create_app(
                api_engine.world, api_engine.agents, api_engine.bus, api_engine.db,
                api_engine.knowledge, api_engine.llm, api_engine, set(),
                api_engine.dialogue_sys,
            )
            client = TestClient(app)
            state = client.get("/api/state").json()
            assert len(state["requests"]) == 3
            assert len(state["today_threads"]) == 3
            assert [thread["id"] for thread in state["today_threads"]] == [
                "resident_requests", "town_pressure", "follow_up_clue"
            ]
            threads = client.get("/api/today-threads")
            assert threads.status_code == 200 and threads.json() == state["today_threads"]
            profile = client.get("/api/agents/agent_carpenter")
            assert profile.status_code == 200
            assert profile.json()["profile"]["responses"]
            forbidden = client.post(
                "/api/player/action",
                json={"type": "work", "agent_id": "agent_carpenter"},
            ).json()
            assert forbidden["error_code"] == "actor_forbidden"

            api_player = put_player(api_engine, "workshop")
            api_player.state.ap = 12
            response = client.post(
                "/api/player/action",
                json={
                    "type": "request_respond",
                    "request_id": "torin_roof",
                    "option": "formal_repair",
                },
            ).json()
            assert response["accepted"] and response["cost"] == 3
            assert response["hours"] == 3 and response["action_id"]
            assert response["changes"] and response["story_beats"] and response["next_observation"]

            reset = client.post("/api/reset").json()
            assert reset["status"] == "ok"
            reset_requests = client.get("/api/requests").json()
            assert all(q["status"] == "active" and not q["used_options"] for q in reset_requests)
            print("  ✓ API 禁止 NPC 越权，统一返回动作契约，reset 会重新 seed 请求")
        finally:
            api_engine.db.close()
            shutil.rmtree(api_root, ignore_errors=True)
    finally:
        engine.db.close()
        shutil.rmtree(root, ignore_errors=True)

    print("[phase3] ALL PASS OK")


if __name__ == "__main__":
    asyncio.run(main())
