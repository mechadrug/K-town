"""Isolated multi-week campaign contract and progression test."""

import asyncio
import copy
import os
import shutil
import tempfile

from actions import Action
from agent import populate_agents
from events import EventBus
from game_state import build_game_state
from knowledge import KnowledgeEngine
from llm import LLMClient
from storage import Storage
from tick import TickEngine
from world import World


def build_engine(db_path, *, auto_reset):
    world = World()
    storage = Storage(db_path)
    bus = EventBus()
    agents = populate_agents()
    for agent in agents:
        world.add_agent_to_location(agent.identity.id, agent.state.location)
    return TickEngine(
        world,
        bus,
        agents,
        KnowledgeEngine(storage),
        storage,
        LLMClient("", "", "mock", "mock"),
        day_length=20,
        auto_reset=auto_reset,
        db=storage,
    )


def player(engine):
    return next(agent for agent in engine.agents if agent.identity.id == "agent_player")


def put_player(engine, location):
    actor = player(engine)
    engine.world.remove_agent_from_location(actor.identity.id, actor.state.location)
    actor.state.location = location
    engine.world.add_agent_to_location(actor.identity.id, location)
    engine.world.state.tick = ((engine.current_day - 1) * engine.day_length) + engine.wake_hour
    actor.state.ap = 12
    actor.state.night_ap = 0
    return actor


def request_map(engine):
    return {request.id: request for request in engine.requests}


def main():
    root = tempfile.mkdtemp(prefix="ktown_campaign_")
    db_path = os.path.join(root, "campaign.db")
    engine = build_engine(db_path, auto_reset=True)
    try:
        assert engine.campaign.payload(1)["week"] == 1
        assert {request.id for request in engine.requests} == {
            "lina_dry_wood", "torin_roof", "mei_town_chronicle"
        }
        print("  [week 1] tutorial chapter and three requests are available")

        engine.current_day = 7
        unlock_2 = engine.campaign.sync_for_day(8)
        requests = request_map(engine)
        assert engine.campaign.payload(8)["week"] == 2
        assert {"school_cistern", "scout_safe_path"}.issubset(requests)
        assert any(event["type"] == "campaign_chapter" for event in unlock_2)
        print("  [week 2] water/path chapter unlocks with two requests")

        actor = put_player(engine, "school")
        result = engine.resolver.resolve(
            actor,
            Action(actor.identity.id, "request_respond", payload={
                "request_id": "school_cistern", "option": "clear_cistern"
            }),
        )
        assert result.accepted and result.cost == 2 and result.hours == 2
        assert requests["school_cistern"].status == "completed"
        assert engine.world.state.campaign_markers["school_water"] == "清理干净"
        assert engine.campaign.state["scores"]["care"] >= 2
        assert any(claim.subject == "clean_water" for claim in engine.knowledge.claims.values())
        print("  [week 2] request choice changes marker, score, knowledge, and time once")

        engine.current_day = 14
        engine.campaign.sync_for_day(15)
        requests = request_map(engine)
        assert engine.campaign.payload(15)["week"] == 3
        assert {"merchant_route", "school_lanterns"}.issubset(requests)
        actor = put_player(engine, "square")
        result = engine.resolver.resolve(
            actor,
            Action(actor.identity.id, "request_respond", payload={
                "request_id": "merchant_route", "option": "open_market"
            }),
        )
        assert result.accepted and result.cost == 2
        assert engine.world.state.campaign_markers["market_route"] == "开放集市"
        print("  [week 3] merchant request exposes a different social trade-off")

        engine.current_day = 21
        engine.campaign.sync_for_day(22)
        requests = request_map(engine)
        assert engine.campaign.payload(22)["week"] == 4
        assert "lantern_fair_council" in requests
        actor = put_player(engine, "square")
        result = engine.resolver.resolve(
            actor,
            Action(actor.identity.id, "request_respond", payload={
                "request_id": "lantern_fair_council", "option": "open_council"
            }),
        )
        assert result.accepted and result.cost == 3
        assert engine.world.state.campaign_markers["fair_table"] == "公开商议"
        print("  [week 4] fair request closes the multi-week decision arc")

        engine.current_day = 28
        final_events = engine.campaign.sync_for_day(29)
        outcome = engine.campaign.payload(29)["final_outcome"]
        assert outcome and outcome["lead_value"] in {"care", "safety", "trust", "welcome"}
        assert any(event["type"] == "campaign_complete" for event in final_events)
        assert len(engine.campaign.state["chapter_history"]) == 4
        print("  [ending] day 29 produces a choice-shaped fair outcome and chapter history")

        snapshot = copy.deepcopy(build_game_state(engine))
        snapshot.pop("saved_at", None)
        engine.persist_game_state()
        engine.db.close()

        restored = build_engine(db_path, auto_reset=False)
        try:
            restored_snapshot = copy.deepcopy(build_game_state(restored))
            restored_snapshot.pop("saved_at", None)
            assert restored_snapshot == snapshot
            assert restored.campaign.payload(29)["final_outcome"] == outcome
            assert restored.world.state.campaign_markers["fair_table"] == "公开商议"
            print("  [save] chapter state, markers, requests, and outcome survive restart")
        finally:
            restored.db.close()
    finally:
        if engine.db.conn is not None:
            engine.db.close()
        shutil.rmtree(root, ignore_errors=True)

    print("[campaign] ALL PASS OK")


if __name__ == "__main__":
    main()
