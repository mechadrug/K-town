"""Versioned save/restore regression coverage for the v5 playable slice.

The test intentionally closes the first SQLite connection before building a
new engine. It therefore checks the same path used by a real process restart,
without ever opening the default development database.
"""

import asyncio
import copy
import os
import random
import shutil
import tempfile

from actions import Action
from agent import populate_agents
from crisis import CRISIS_RUMOR, Crisis
from events import EventBus
from game_state import build_game_state
from knowledge import KnowledgeEngine
from llm import LLMClient
from models import AgentTask, Event, EventType
from storage import Storage
from tick import TickEngine
from world import World


def build_engine(db_path, *, auto_reset):
    world = World()
    bus = EventBus()
    storage = Storage(db_path)
    agents = populate_agents()
    for agent in agents:
        world.add_agent_to_location(agent.identity.id, agent.state.location)
    return TickEngine(
        world, bus, agents, KnowledgeEngine(storage), storage,
        LLMClient("", "", "mock", "mock"), day_length=20,
        auto_reset=auto_reset, db=storage,
    )


def agent_by_id(engine, agent_id):
    return next(agent for agent in engine.agents if agent.identity.id == agent_id)


def move_without_cost(engine, agent, destination):
    engine.world.remove_agent_from_location(agent.identity.id, agent.state.location)
    agent.state.location = destination
    engine.world.add_agent_to_location(agent.identity.id, destination)


def normalized_snapshot(engine):
    snapshot = copy.deepcopy(build_game_state(engine))
    snapshot.pop("saved_at", None)
    return snapshot


async def main():
    root = tempfile.mkdtemp(prefix="ktown_save_restore_")
    db_path = os.path.join(root, "save.db")
    random.seed(341)
    engine = build_engine(db_path, auto_reset=True)
    try:
        engine.world.state.tick = 5
        engine.scheduler.generate_daily_schedule(
            1, [agent.identity.id for agent in engine.agents], engine.world
        )
        player = agent_by_id(engine, "agent_player")
        lina = agent_by_id(engine, "agent_carpenter")
        move_without_cost(engine, player, "workshop")
        player.state.ap = 9
        player.state.inventory = ["rope", "old_note"]
        player.state.emotions = {"joy": 61.0, "anxiety": 38.0, "anger": 19.0, "sadness": 27.0}
        player.state.habit_bias = {"rainy": {"observe": 0.25}}
        player.state.habit_counts = {"rainy_observe": 3}
        player.state.short_term_memory = [{"tick": 5, "text": "工坊屋檐正在滴水"}]
        player.state.current_task = AgentTask("检查漏雨", "workshop", started_at=5.0)
        player.diary.append("第1天：决定先听听莉娜的计划。")

        response = engine.resolver.resolve(
            player,
            Action(
                player.identity.id,
                "request_respond",
                payload={"request_id": "lina_dry_wood", "option": "share_roof_plan"},
            ),
        )
        assert response.accepted and engine._pending_advance == 1

        claim = engine.knowledge.observe_with_action(
            "agent_scout", "old_mine", "旧矿道入口需要在暴雨前复查", "wilderness",
            confidence=0.87, action_type="avoid_location", action_target="mine",
            emotional_valence=-0.6,
        )
        engine.knowledge.propagate(claim.id, "agent_scout", "agent_carpenter", 0.8)
        assert claim.id in {item.id for item in engine.knowledge.agent_knowledge(lina.identity.id)}

        engine.world.state.weather = "rainy"
        engine.world.set_workshop_roof(1, engine.current_day)
        engine.world.state.rain_forecast_announced = True
        engine.world.state.mine_rumor_status = "needs_verification"
        engine.world.state.mine_rumor_confidence = 0.55
        engine.world.state.lantern_fair_preparedness = 4
        engine.world.resources["workshop"]["materials"] = 17
        engine.world.record_demand("food", 4)
        engine.bus.publish(Event(6, EventType.RUMOR_SPREAD, "square", {"claim": "旧矿道待核实"}))

        crisis = Crisis(CRISIS_RUMOR, engine.current_day, engine)
        crisis.progress = 15.0
        crisis.interventions = [{"agent": player.identity.id, "type": "clarify", "desc": "澄清", "day": 1}]
        crisis.last_intervene_day = 1
        engine.crises.append(crisis)
        engine.current_day_events.append({"tick": 5, "type": "request", "action": "莉娜摊开了屋顶草图"})
        engine.current_day_decisions.append({"agent_id": "agent_carpenter", "reason": "先把木料移进工坊"})
        engine.daily_agent_logs[player.identity.id].append("因为先讨论草图，所以莉娜愿意一起安排木料。")

        engine.persist_game_state()
        before = normalized_snapshot(engine)
        expected_logs = copy.deepcopy(engine.daily_agent_logs)
        engine.db.close()

        restored = build_engine(db_path, auto_reset=False)
        try:
            assert restored.restored_from_save
            assert normalized_snapshot(restored) == before
            restored_player = agent_by_id(restored, "agent_player")
            assert restored_player.state.inventory == ["rope", "old_note"]
            assert restored_player.state.ap == 8
            assert restored.world.workshop_roof_status()["id"] == "temporary_cover"
            assert restored.crises[0].progress == 15.0
            assert restored.bus.all_events[0].type == EventType.RUMOR_SPREAD
            print("  [save] world, residents, knowledge, requests, crisis, events, logs, and RNG restored")

            # Starting the normal loop must preserve the saved partial-day logs.
            run_task = asyncio.create_task(restored.run())
            await asyncio.sleep(0.08)
            restored.stop()
            await run_task
            for agent_id, original_lines in expected_logs.items():
                assert restored.daily_agent_logs.get(agent_id, [])[:len(original_lines)] == original_lines
            assert restored.world.state.tick > before["world"]["state"]["tick"]
            print("  [save] restored run loop preserves same-day logs and settles pending time")
        finally:
            restored.db.close()
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("[save-restore] ALL PASS OK")


if __name__ == "__main__":
    asyncio.run(main())
