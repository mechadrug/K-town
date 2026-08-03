"""Tick loop engine."""
import asyncio
import random
from typing import List, Dict, Any, Callable, Optional, Tuple
from world import World
from events import EventBus, EventScheduler
from knowledge import KnowledgeEngine
from logger import Logger
from llm import LLMClient
from models import EventType
from db import Database


class TickEngine:
    def __init__(self, world: World, bus: EventBus, agents: list,
                 knowledge: KnowledgeEngine, logger: Logger, llm: LLMClient,
                 rate: float = 1.0, day_length: int = 24, auto_reset: bool = True):
        self.world = world
        self.bus = bus
        self.agents = agents
        self.knowledge = knowledge
        self.logger = logger
        self.llm = llm
        self.rate = rate
        self.day_length = day_length
        self._running = False
        self.scheduler = EventScheduler(bus)
        self.db = Database()
        self.day_summaries: List[Dict[str, Any]] = []
        self.current_day_events: List[Dict[str, Any]] = []
        self.current_day: int = 1
        self.on_day_summary: Optional[Callable] = None
        self.on_event: Optional[Callable] = None
        # 前一天状态，用于计算每日变化
        self.prev_agent_states: List[Dict[str, Any]] = []
        self.prev_knowledge_count: int = 0
        self.prev_total_gold: int = 0
        # 每日行为日志
        self.daily_agent_logs: Dict[str, List[str]] = {}
        # 数据库写入缓冲（每10个Tick写入一次）
        self._pending_snapshots: List[Tuple[int, int, Dict[str, Any]]] = []
        self._tick_since_last_db_write: int = 0
        self._db_write_interval: int = 10
        # 已处理事件去重集合（避免重复处理相同事件）
        self._processed_event_keys: set = set()
        # 自动重置
        if auto_reset:
            self.db.reset()
        # 加载历史摘要
        self._load_history()
    
    def _load_history(self):
        """加载历史每日摘要"""
        summaries = self.db.get_day_summaries()
        if summaries:
            self.day_summaries = summaries
            self.current_day = summaries[-1]["day"] + 1
            print(f"[OK] 已加载 {len(summaries)} 条历史每日摘要，当前第 {self.current_day} 天")
        # 初始化当天的agent行为日志
        self.daily_agent_logs = {a.identity.id: [] for a in self.agents}

    async def run(self):
        # 初始化前一天状态
        self._save_current_state()
        self._running = True
        try:
            while self._running:
                await self.step()
                await asyncio.sleep(self.rate)
        finally:
            # 确保退出时刷新所有缓冲数据到数据库
            self._flush_db_writes()

    def _save_current_state(self):
        """保存当前状态作为前一天的基准"""
        self.prev_agent_states = [a.to_dict() for a in self.agents]
        self.prev_knowledge_count = len(self.knowledge.claims)
        self.prev_total_gold = sum(a.state.gold for a in self.agents)
        # 初始化当天的agent行为日志
        self.daily_agent_logs = {a.identity.id: [] for a in self.agents}

    def _flush_db_writes(self):
        """将缓冲的数据库写入批量刷新到数据库"""
        if self._pending_snapshots:
            for tick, day, state in self._pending_snapshots:
                self.db.save_world_snapshot(tick, day, state)
            self._pending_snapshots.clear()

    async def step(self):
        tick = self.world.state.tick + 1
        hour = tick % 24

        self.world.advance(tick)
        self.bus.flush_scheduled(tick)

        # 缓冲世界快照，每10个Tick批量写入一次数据库
        self._pending_snapshots.append(
            (tick, self.current_day, self.world.state.__dict__.copy())
        )
        self._tick_since_last_db_write += 1
        if self._tick_since_last_db_write >= self._db_write_interval:
            self._flush_db_writes()
            self._tick_since_last_db_write = 0

        # 处理事件，避免重复处理，同时保存到数据库
        processed_events = set()
        for event in self.bus.all_events:
            event_key = f"{event.type.value}_{event.tick}_{event.location}"
            if event_key in processed_events:
                continue
            processed_events.add(event_key)
            # 保存事件到数据库
            self.db.save_event(tick, self.current_day, event.type.value, event.location, event.payload)
            self.current_day_events.append({
                "tick": tick, "type": event.type.value,
                "location": event.location, "payload": str(event.payload)[:100],
            })
            await self._process_event(event)
        self.bus.clear_events()

        # 优化循环，减少重复计算
        loc_map: Dict[str, list] = {}
        for a in self.agents:
            loc_map.setdefault(a.state.location, []).append(a.identity.id)
        for loc_id, loc_data in self.world.locations.items():
            loc_data["agents"] = loc_map.get(loc_id, [])

        # 批量处理Agent行动
        for agent in self.agents:
            evts = self.bus.get_events_at(agent.state.location)
            evt_strs = [f"{e.type.value} at {e.location}" for e in evts]
            here = loc_map.get(agent.state.location, [])
            agent.perceive(evt_strs)
            agent.think(hour)
            action = agent.decide(hour, here, evt_strs)
            # 记录行为日志
            self.daily_agent_logs[agent.identity.id].append(f"{hour}点: {action['desc']}")
            self.logger.log_decision(tick, agent.identity.id, action["desc"], action["type"],
                                     agent.top_goal().description if agent.top_goal() else "", 0.8, "rule")
            await self._handle_action(agent, action)
            if action["type"] in ("talk", "work", "trade", "move"):
                evt = {"tick": tick, "agent": agent.identity.name, "action": action["desc"], "location": agent.state.location}
                self.current_day_events.append(evt)
                if self.on_event:
                    await self.on_event(evt)

        if hour == 0 and tick > 1:
            summary = self._generate_day_summary(self.current_day)
            self.day_summaries.append(summary)
            # 保存每日摘要到数据库
            self.db.save_day_summary(summary)
            # 保存行为日志到数据库
            for agent in self.agents:
                self.db.save_agent_log(
                    day=self.current_day,
                    agent_id=agent.identity.id,
                    agent_name=agent.identity.name,
                    behaviors=self.daily_agent_logs.get(agent.identity.id, [])
                )
            self.current_day_events = []
            self.current_day += 1
            aids = [a.identity.id for a in self.agents]
            self.scheduler.generate_daily_schedule(self.current_day, aids)
            # 保存下一天的前置状态
            self._save_current_state()
            if self.on_day_summary:
                await self.on_day_summary(summary)
