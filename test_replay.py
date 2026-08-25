"""Deterministic replay regression for a persisted mid-day checkpoint."""

import asyncio
import copy
import os
import random
import shutil
import tempfile

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
    bus = EventBus()
    storage = Storage(db_path)
    agents = populate_agents()
    for agent in agents:
        world.add_agent_to_location(agent.identity.id, agent.state.location)
    engine = TickEngine(
        world, bus, agents, KnowledgeEngine(storage), storage,
        LLMClient("", "", "mock", "mock"), day_length=20,
        auto_reset=auto_reset, db=storage,
    )
    if not engine.restored_from_save:
        engine.world.state.tick = engine.wake_hour
        engine.scheduler.generate_daily_schedule(
            engine.current_day, [agent.identity.id for agent in engine.agents], engine.world
        )
    return engine


def snapshot(engine):
    data = copy.deepcopy(build_game_state(engine))
    data.pop("saved_at", None)
    return data


def write_checkpoint(db_path, checkpoint):
    storage = Storage(db_path)
    storage.save_game_state(checkpoint)
    storage.close()


async def drive(engine, steps):
    for _ in range(steps):
        await engine.step()


async def replay_from(checkpoint, db_path):
    write_checkpoint(db_path, checkpoint)
    engine = build_engine(db_path, auto_reset=False)
    try:
        assert engine.restored_from_save
        await drive(engine, 28)
        return snapshot(engine)
    finally:
        engine.db.close()


async def main():
    root = tempfile.mkdtemp(prefix="ktown_replay_")
    source_path = os.path.join(root, "source.db")
    random.seed(2048)
    source = build_engine(source_path, auto_reset=True)
    try:
        await drive(source, 8)
        checkpoint = snapshot(source)
        assert checkpoint["knowledge"]["claims"], "checkpoint must contain generated knowledge"
    finally:
        source.db.close()

    try:
        outcomes = []
        for index in range(3):
            outcomes.append(await replay_from(checkpoint, os.path.join(root, f"replay_{index}.db")))
        assert outcomes[0] == outcomes[1] == outcomes[2]
        assert len(outcomes[0]["knowledge"]["claims"]) > len(checkpoint["knowledge"]["claims"])
        print("[replay] checkpoint restore produces identical state and day summaries three times")
        print("[replay] ALL PASS OK")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
