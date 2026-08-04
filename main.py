"""K-town server entry point."""
import asyncio,json
from typing import Set
from fastapi import WebSocket
from config import load_config
from world import World
from events import EventBus
from agent import populate_agents
from knowledge import KnowledgeEngine
from storage import Storage
from llm import LLMClient
from tick import TickEngine
from api import create_app
from quests import QuestEngine
from dialogue import DialogueSystem
import uvicorn

# Global set of connected WebSocket clients
ws_clients: Set[WebSocket] = set()

async def broadcast(msg: dict):
    disconnected = set()
    for ws in ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            disconnected.add(ws)
    ws_clients.difference_update(disconnected)


def init_system():
    cfg = load_config("config.yaml")
    print("=== K-town Server ===")
    print(f"LLM: {cfg.llm.model} @ {cfg.llm.base_url}")
    print(f"Day: {cfg.tick.day_length}h, Wake: {cfg.tick.wake_hour}")

    world = World()
    bus = EventBus()
    # 唯一数据访问层：main/tick/api 共享同一实例
    storage = Storage()
    knowledge = KnowledgeEngine()
    llm = LLMClient(cfg.llm.base_url, cfg.llm.api_key, cfg.llm.model, cfg.llm.provider)

    agents = populate_agents()
    for a in agents:
        world.add_agent_to_location(a.identity.id, a.state.location)
        storage.log_world_event(0, "agent_spawned", a.state.location, [a.identity.id], None)
    print(f"Spawned {len(agents)} agents")

    engine = TickEngine(world, bus, agents, knowledge, storage, llm, cfg.tick.day_length,
                        db=storage, wake_hour=cfg.tick.wake_hour, waking_hours=cfg.tick.waking_hours)

    # 知识持久化：新知识写穿到 knowledge_pool；并尝试断点恢复（关闭自动重置时生效）
    knowledge.persistence = storage
    knowledge.load_from_db(storage.get_knowledge_pool())

    # 初始化任务系统
    quest_engine = QuestEngine()
    engine.quest_engine = quest_engine
    # 第 1 天启动即生成每日目标（此后每天日结时重新生成）
    quest_engine.generate_daily_goals(1)

    # 初始化对话系统
    dialogue_sys = DialogueSystem()
    engine.dialogue_sys = dialogue_sys

    # Wire up broadcast callbacks
    async def on_day_summary(summary):
        await broadcast({"type": "day_summary", "data": summary})

    async def on_event(evt):
        await broadcast({"type": "event", "data": evt})

    engine.on_day_summary = on_day_summary
    engine.on_event = on_event

    agent_ids = [a.identity.id for a in agents]
    engine.scheduler.generate_daily_schedule(1, agent_ids, world)
    # 世界观：从清晨醒来开始（清醒时段 5–17），玩家登录即可行动
    world.state.tick = cfg.tick.wake_hour
    print("Day 1 events scheduled")

    app = create_app(world, agents, bus, storage, knowledge, llm, engine, ws_clients, dialogue_sys)
    return app, engine, llm, cfg


async def main():
    app, engine, llm, cfg = init_system()
    asyncio.create_task(engine.run())
    print("Tick engine running (回合制)")

    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=cfg.server.http_port, log_level="info"))
    print(f"Dashboard: http://localhost:{cfg.server.http_port}")
    print(f"API: http://localhost:{cfg.server.http_port}/api/state")
    print(f"WS: ws://localhost:{cfg.server.http_port}/ws")
    print("Press Ctrl+C to stop")

    try:
        await server.serve()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        engine.stop()
        await llm.close()
        # Close database safely
        if engine.db:
            engine.db.close()
        print("=== Stopped ===")

if __name__ == "__main__":
    asyncio.run(main())
