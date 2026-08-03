"""K-town server - run with: python -m server"""
import asyncio
from .config import load_config
from .world import World
from .events import EventBus
from .agent import populate_agents
from .knowledge import KnowledgeEngine
from .logger import Logger
from .llm import LLMClient
from .tick import TickEngine
from .api import create_app
import uvicorn


def init_system():
    """Initialize all systems and return (app, engine, llm)."""
    cfg = load_config("config.yaml")
    print("=== K-town Server ===")
    print(f"LLM: {cfg.llm.model} @ {cfg.llm.base_url}")
    print(f"Tick: {cfg.tick.rate}s, Day: {cfg.tick.day_length}h")

    world = World()
    bus = EventBus()
    logger = Logger()
    knowledge = KnowledgeEngine()
    llm = LLMClient(cfg.llm.base_url, cfg.llm.api_key, cfg.llm.model, cfg.llm.provider)

    agents = populate_agents()
    for a in agents:
        world.add_agent_to_location(a.identity.id, a.state.location)
        logger.log_world_event(0, "agent_spawned", a.state.location, [a.identity.id], None)
    print(f"Spawned {len(agents)} agents")

    engine = TickEngine(
        world=world, bus=bus, agents=agents,
        knowledge=knowledge, logger=logger, llm=llm,
        rate=cfg.tick.rate, day_length=cfg.tick.day_length,
    )
    agent_ids = [a.identity.id for a in agents]
    engine.scheduler.generate_daily_schedule(1, agent_ids)
    print("Day 1 events scheduled")

    app = create_app(world, agents, bus, logger, knowledge, llm)
    return app, engine, llm, cfg


async def main():
    app, engine, llm, cfg = init_system()

    asyncio.create_task(engine.run())
    print(f"Tick engine running ({cfg.tick.rate}s/tick)")

    server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=cfg.server.http_port, log_level="info")
    )
    print(f"HTTP: http://localhost:{cfg.server.http_port}")
    print(f"WS: ws://localhost:{cfg.server.http_port}/ws")
    print("Press Ctrl+C to stop")

    try:
        await server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        await llm.close()
        print("=== Stopped ===")


if __name__ == "__main__":
    asyncio.run(main())