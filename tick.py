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

    def _generate_day_summary(self, day: int) -> Dict[str, Any]:
        """生成中文每日详细摘要"""
        # 计算整体变化
        current_total_gold = sum(a.state.gold for a in self.agents)
        gold_change = current_total_gold - self.prev_total_gold
        knowledge_change = len(self.knowledge.claims) - self.prev_knowledge_count
        avg_energy = sum(a.state.energy for a in self.agents) / len(self.agents)
        happy_count = sum(1 for a in self.agents if a.state.mood.value == "happy")
        
        # 生成每个agent的变化描述
        agent_summaries = []
        prev_state_map = {a["id"]: a for a in self.prev_agent_states}
        for agent in self.agents:
            prev = prev_state_map.get(agent.identity.id, {})
            energy_change = round(agent.state.energy - prev.get("energy", 100), 1)
            gold_change_agent = agent.state.gold - prev.get("gold", 0)
            knowledge_count = len(agent.knowledge)
            
            # 行为摘要
            behavior_log = self.daily_agent_logs.get(agent.identity.id, [])
            behavior_summary = "，".join(behavior_log[-5:]) if behavior_log else "今天没有活动记录"
            
            # 心情描述
            mood_desc = {
                "happy": "心情愉快",
                "neutral": "心情平静",
                "anxious": "有些焦虑",
                "angry": "非常生气",
                "sad": "心情低落"
            }.get(agent.state.mood.value, "心情未知")
            
            agent_summaries.append({
                "id": agent.identity.id,
                "name": agent.identity.name,
                "role": agent.identity.role.value,
                "role_cn": self._get_role_cn(agent.identity.role.value),
                "location": agent.state.location,
                "location_cn": self._get_location_cn(agent.state.location),
                "energy": round(agent.state.energy, 1),
                "energy_change": energy_change,
                "mood": agent.state.mood.value,
                "mood_desc": mood_desc,
                "gold": agent.state.gold,
                "gold_change": gold_change_agent,
                "knowledge_count": knowledge_count,
                "behavior_summary": behavior_summary,
                "goal": agent.top_goal().description if agent.top_goal() else "暂无目标"
            })
        
        # 重大事件摘要
        important_events = []
        for evt in self.current_day_events:
            if evt.get("type") in [EventType.WEATHER_CHANGE.value, EventType.RESOURCE_FOUND.value, EventType.ITEM_CRAFTED.value]:
                important_events.append(evt.get("payload", evt.get("action", "未知事件")))
        
        # 整体摘要
        overall_summary = f"第{day}天结束，天气{self.world.state.weather}。城镇共有{len(self.agents)}位居民，"
        overall_summary += f"平均体力{round(avg_energy,1)}点，其中有{happy_count}位居民心情愉快。"
        overall_summary += f"今天知识库新增{knowledge_change}条知识，城镇总金币变化{'+'+str(gold_change) if gold_change>=0 else gold_change}。"
        if important_events:
            overall_summary += f"今天发生的重大事件有：{'；'.join(important_events[:3])}。"
        
        return {
            "day": day,
            "weather": self.world.state.weather,
            "overall_summary": overall_summary,
            "agents": agent_summaries,
            "stats": {
                "total_gold": current_total_gold,
                "gold_change": gold_change,
                "total_knowledge": len(self.knowledge.claims),
                "knowledge_change": knowledge_change,
                "avg_energy": round(avg_energy, 1),
                "happy_count": happy_count,
                "events_count": len(self.current_day_events)
            }
        }
    
    def _get_role_cn(self, role: str) -> str:
        """获取职业中文名"""
        role_map = {
            "elder": "长者",
            "blacksmith": "铁匠",
            "carpenter": "木匠",
            "forager": "采集者",
            "scout": "侦察兵",
            "merchant": "商人",
            "teacher": "教师",
            "farmer": "农民",
            "storyteller": "讲故事的人",
            "healer": "医生",
            "miner": "矿工",
            "player": "旅行者"
        }
        return role_map.get(role, role)
    
    def _get_location_cn(self, location: str) -> str:
        """获取地点中文名"""
        loc_map = {
            "square": "广场",
            "workshop": "工坊",
            "wilderness": "荒野",
            "school": "学校",
            "mine": "矿洞"
        }
        return loc_map.get(location, location)

    async def _process_event(self, event):
        if event.type == EventType.WEATHER_CHANGE:
            w = event.payload.get("weather", "unknown")
            for a in self.agents:
                if a.state.location == event.location:
                    c = self.knowledge.observe(a.identity.id, "weather", f"今天天气是{w}", a.state.location)
                    self.logger.log_knowledge(0, c.id, a.identity.id, "create", "", c.claim)
        elif event.type == EventType.RESOURCE_FOUND:
            r = event.payload.get("resource", "unknown")
            aid = event.payload.get("agent_id", "")
            if aid: self.knowledge.observe(aid, "resource", f"在{event.location}发现了{r}", event.location)
        elif event.type == EventType.SOCIAL_ENCOUNTER:
            aids = event.payload.get("agents", [])
            for aid in aids:
                self.knowledge.observe(aid, "social", f"在{event.location}遇到了其他人", event.location)
            if len(aids) >= 2:
                claims_a = self.knowledge.agent_knowledge(aids[0])
                if claims_a:
                    top = max(claims_a, key=lambda c: c.confidence)
                    self.knowledge.propagate(top.id, aids[0], aids[1], 0.8)
        elif event.type == EventType.ITEM_CRAFTED:
            item = event.payload.get("item", "unknown")
            aid = event.payload.get("agent_id", "")
            if aid: self.knowledge.observe(aid, "craft", f"制作了{item}", event.location)
        elif event.type == EventType.RUMOR_SPREAD:
            claim = event.payload.get("claim", "")
            f = event.payload.get("from", "")
            t = event.payload.get("to", "")
            if f and t and claim:
                self.knowledge.observe(f, "rumor", claim, event.location)
                self.knowledge.observe(t, "rumor", f"听说{claim}", event.location)

    async def _handle_action(self, agent, action):
        t = action.get("type", "")
        tgt = action.get("target", "")
        if t == "move" and tgt:
            self.world.remove_agent_from_location(agent.identity.id, agent.state.location)
            agent.state.location = tgt
            self.world.add_agent_to_location(agent.identity.id, tgt)
            agent.state.energy -= 5
        elif t == "work":
            agent.state.energy -= 8
            # 不同职业工作产出不同
            role = agent.identity.role.value
            if role in ["blacksmith", "carpenter"]:
                # 铁匠和木匠产出工具，卖给商人
                agent.state.gold += 5
                agent.state.inventory.append("tool")
            elif role in ["forager", "farmer"]:
                # 采集者和农民产出食物
                agent.state.gold += 3
                agent.state.inventory.append("food")
            elif role == "scout":
                # 侦察兵探索获得金币
                agent.state.gold += 4
            elif role == "healer":
                # 医生治疗获得金币
                agent.state.gold += 4
            elif role == "miner":
                # 矿工采集矿石获得金币
                agent.state.gold += 5
            else:
                agent.state.gold += 2
        elif t == "rest":
            agent.state.energy = min(100, agent.state.energy + 10)
        elif t == "sleep":
            agent.state.energy = min(100, agent.state.energy + 20)
        elif t == "talk":
            agent.state.energy -= 2
            # 社交获得少量金币
            agent.state.gold += 1
        elif t == "trade":
            # 商人交易获得更多金币
            if agent.identity.role.value == "merchant":
                agent.state.gold += 8
            else:
                agent.state.gold += 2
        agent.state.energy = max(0, min(100, agent.state.energy))

    def stop(self):
        self._running = False
        self.db.close()
