"""Tick loop engine."""
import asyncio
import random
from typing import List, Dict, Any, Callable, Optional, Tuple
from world import World
from events import EventBus, EventScheduler
from knowledge import KnowledgeEngine
from logger import Logger
from llm import LLMClient
from models import EventType, Mood, Mood
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
        # LLM调用追踪（每天限制次数）
        self._llm_calls_today = 0
        self._llm_daily_limit = 10
        self._llm_cache = {}  # 缓存相同输入的结果
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
            # 保存事件到数据库
            self.current_day_events.append({
                "tick": tick, "type": event.type.value,
                "location": event.location, "payload": str(event.payload)[:100],
            })
            await self._process_event(event)
            # 自动固化高置信度知识
            self.knowledge.auto_solidify()
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
            # 情绪传染：周围Agent的心情影响自己
            nearby_moods = []
            for other in self.agents:
                if other.identity.id != agent.identity.id and other.state.location == agent.state.location:
                    nearby_moods.append(other.state.mood)
            if nearby_moods:
                happy_count = sum(1 for m in nearby_moods if m == Mood.HAPPY)
                sad_count = sum(1 for m in nearby_moods if m in (Mood.SAD, Mood.ANGRY))
                stability = agent.identity.personality.get('stability', 0.5)
                # 稳定性低→更容易被传染
                contagion_resist = stability * 0.5
                if happy_count > len(nearby_moods) / 2 and random.random() < (0.3 - contagion_resist):
                    agent.state.mood = Mood.HAPPY
                elif sad_count > len(nearby_moods) / 2 and random.random() < (0.25 - contagion_resist):
                    if agent.state.mood == Mood.HAPPY:
                        agent.state.mood = Mood.NEUTRAL
                    elif agent.state.mood == Mood.NEUTRAL:
                        agent.state.mood = Mood.ANXIOUS
            # LLM辅助决策检测（仅在关键场景调用）
            llm_action = await self._try_llm_decision(agent, hour, here, evt_strs)
            if llm_action:
                action = llm_action
                self.logger.log_decision(tick, agent.identity.id, action['desc'], action['type'],
                                     agent.top_goal().description if agent.top_goal() else '', 0.9, 'llm')
            else:
                action = agent.decide(hour, here, evt_strs)
                self.logger.log_decision(tick, agent.identity.id, action['desc'], action['type'],
                                     agent.top_goal().description if agent.top_goal() else '', 0.8, 'rule')
            self.daily_agent_logs[agent.identity.id].append(f"{hour}点: {action['desc']}")
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
            self._llm_calls_today = 0
            self.current_day += 1
            # 关系衰减：每天好感度向0回归5%（需要持续维护关系）
            for agent in self.agents:
                for other_id in agent.state.social_ties:
                    tie = agent.state.social_ties[other_id]
                    # 衰减量 = 当前值的5%，最小衰减0.1
                    decay = max(0.1, abs(tie) * 0.05)
                    if tie > 0:
                        agent.state.social_ties[other_id] = max(0, tie - decay)
                    elif tie < 0:
                        agent.state.social_ties[other_id] = min(0, tie + decay)
            aids = [a.identity.id for a in self.agents]
            self.scheduler.generate_daily_schedule(self.current_day, aids, self.world)
            # 保存下一天的前置状态
            self._save_current_state()
            if self.on_day_summary:
                await self.on_day_summary(summary)


    async def _try_llm_decision(self, agent, hour, agents_here, events) -> Optional[Dict[str, Any]]:
        """尝试LLM辅助决策，仅在关键场景调用"""
        # 检查每日限制
        if self._llm_calls_today >= self._llm_daily_limit:
            return None
        
        # 检测是否需要LLM介入
        scenario = None
        context = {}
        
        # 场景1：情绪危机（体力低+心情差）
        if agent.state.energy < 25 and agent.state.mood in (Mood.SAD, Mood.ANGRY):
            scenario = "emotional_crisis"
            context = {
                "energy": agent.state.energy,
                "mood": agent.state.mood.value,
                "personality": agent.identity.personality,
                "location": agent.state.location
            }
        
        # 场景2：知识冲突
        elif agent.knowledge:
            conflicting = [k for k in agent.knowledge if k.contradicted_by]
            if conflicting:
                scenario = "knowledge_conflict"
                context = {
                    "conflicting_knowledge": [{"claim": k.claim, "conflicts": k.contradicted_by} for k in conflicting[:2]],
                    "personality": agent.identity.personality
                }
        
        # 场景3：社交困境（朋友需要帮忙但自己很累）
        elif agent.state.energy < 35 and agents_here:
            best_friend = None
            best_tie = 30
            for other_id in agents_here:
                tie = agent.state.social_ties.get(other_id, 0)
                if tie > best_tie:
                    best_tie = tie
                    best_friend = other_id
            if best_friend:
                scenario = "social_dilemma"
                context = {
                    "energy": agent.state.energy,
                    "friend": best_friend,
                    "tie_strength": best_tie,
                    "location": agent.state.location
                }
        
        if not scenario:
            return None
        
        # 检查缓存
        cache_key = f"{agent.identity.id}_{scenario}_{agent.state.energy}_{hour}"
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        # 生成prompt
        prompt = self._generate_llm_prompt(agent, scenario, context)
        
        # 调用LLM
        try:
            response = await self.llm.call(prompt, system="你是K-town小镇的居民。根据你的状态和性格，决定你接下来做什么。用一句话描述你的行动。")
            self._llm_calls_today += 1
            
            # 解析响应
            action = self._parse_llm_response(agent, response)
            if action:
                self._llm_cache[cache_key] = action
                return action
        except Exception:
            pass
        
        return None
    
    def _generate_llm_prompt(self, agent, scenario, context) -> str:
        """为不同场景生成LLM prompt"""
        n = agent.identity.name
        role = agent._get_role_cn(agent.identity.role.value)
        p = agent.identity.personality
        
        if scenario == "emotional_crisis":
            return (
                f"你是{n}，一个{role}。"
                f"你现在的体力只有{int(context['energy'])}点，心情{context['mood']}。"
                f"你的性格：外向{p['extraversion']:.1f}、尽责{p['conscientiousness']:.1f}、开放{p['openness']:.1f}、宜人{p['agreeableness']:.1f}、稳定{p['stability']:.1f}。"
                f"你目前在{context['location']}。请用一句话描述你会做什么来改善现状。"
            )
        elif scenario == "knowledge_conflict":
            conflicts = context["conflicting_knowledge"]
            conflict_text = "；".join([f"你知道{c['claim']}，但有人质疑它" for c in conflicts])
            return (
                f"你是{n}，一个{role}。{conflict_text}。"
                f"你的性格：开放{p['openness']:.1f}、宜人{p['agreeableness']:.1f}。"
                f"你会如何处理这个知识冲突？用一句话描述。"
            )
        elif scenario == "social_dilemma":
            return (
                f"你是{n}，一个{role}。你的好朋友{context['friend']}需要帮助。"
                f"但你现在的体力只有{int(context['energy'])}点，感觉很累。"
                f"你们的好感度是{context['tie_strength']:.1f}。"
                f"你会怎么做？用一句话描述。"
            )
        return ""
    
    def _parse_llm_response(self, agent, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的行动描述"""
        if not response:
            return None
        
        response = response.strip()
        if len(response) > 100:
            response = response[:100]
        
        # 判断行动类型
        action_type = "observe"
        if "休息" in response or "睡" in response:
            action_type = "rest"
        elif "聊天" in response or "说话" in response or "告诉" in response:
            action_type = "talk"
        elif "工作" in response or "做" in response or "制作" in response:
            action_type = "work"
        elif "去" in response or "走" in response or "移动" in response:
            action_type = "move"
        elif "调查" in response or "探索" in response or "看" in response:
            action_type = "investigate"
        
        return {
            "type": action_type,
            "desc": response,
            "target": ""
        }



    async def _execute_trade(self, agent, trade: Dict[str, Any]):
        """执行交易"""
        action = trade.get("action")
        resource = trade.get("resource")
        price = trade.get("price", 5)
        
        if action == "buy":
            if agent.state.gold >= price:
                agent.state.gold -= price
                if resource == "food":
                    agent.state.food += 1
                else:
                    agent.state.inventory.append(resource)
                self.world.record_demand(resource)
                self.daily_agent_logs[agent.identity.id].append(f"以{price}金币购买了{resource}")
        elif action == "sell":
            if resource == "food" and agent.state.food > 0:
                agent.state.food -= 1
                agent.state.gold += price
                self.world.record_supply(resource)
                self.daily_agent_logs[agent.identity.id].append(f"以{price}金币卖出了{resource}")
            elif resource in agent.state.inventory:
                agent.state.inventory.remove(resource)
                agent.state.gold += price
                self.world.record_supply(resource)
                self.daily_agent_logs[agent.identity.id].append(f"以{price}金币卖出了{resource}")


    def _generate_day_summary(self, day: int) -> Dict[str, Any]:
        """生成中文每日叙事摘要"""
        weather_name = self.world.get_weather_name()
        current_total_gold = sum(a.state.gold for a in self.agents)
        gold_change = current_total_gold - self.prev_total_gold
        knowledge_change = len(self.knowledge.claims) - self.prev_knowledge_count
        avg_energy = sum(a.state.energy for a in self.agents) / max(1, len(self.agents))
        happy_count = sum(1 for a in self.agents if a.state.mood.value == "happy")
        anxious_count = sum(1 for a in self.agents if a.state.mood.value in ("anxious", "sad", "angry"))

        # 生成每个居民的叙事描述
        agent_summaries = []
        prev_state_map = {a["id"]: a for a in self.prev_agent_states}
        location_agents: Dict[str, List[str]] = {}
        for agent in self.agents:
            loc = agent.state.location
            location_agents.setdefault(loc, []).append(agent.identity.name)

        for agent in self.agents:
            prev = prev_state_map.get(agent.identity.id, {})
            energy_change = round(agent.state.energy - prev.get("energy", 100), 1)
            gold_change_agent = agent.state.gold - prev.get("gold", 0)
            behavior_log = self.daily_agent_logs.get(agent.identity.id, [])

            # 统计行为类型
            work_count = sum(1 for b in behavior_log if "工作" in b or "锻造" in b or "采集" in b or "耕种" in b or "挖掘" in b or "制作" in b or "救治" in b)
            talk_count = sum(1 for b in behavior_log if "聊天" in b or "讲" in b or "教" in b)
            move_count = sum(1 for b in behavior_log if "前往" in b or "移动" in b)
            rest_count = sum(1 for b in behavior_log if "休息" in b or "睡觉" in b)
            trade_count = sum(1 for b in behavior_log if "交易" in b or "摆摊" in b)

            # 心情描述
            mood_map = {
                "happy": "心情愉快", "neutral": "心情平静",
                "anxious": "有些焦虑", "angry": "非常生气", "sad": "心情低落"
            }
            mood_desc = mood_map.get(agent.state.mood.value, "心情未知")

            # 生成叙事描述
            narrative_parts = []
            if work_count > 0:
                role_work_desc = {
                    "blacksmith": f"在工坊勤劳地锻造了{work_count}次工具",
                    "carpenter": f"在工坊精心制作了{work_count}次木工家具",
                    "forager": f"前往荒野采集了{work_count}次食物和草药",
                    "farmer": f"在田地里耕种了{work_count}次庄稼",
                    "scout": f"探索了{work_count}次未知区域",
                    "healer": f"在学校救治了{work_count}次病人",
                    "miner": f"在矿洞挖掘了{work_count}次矿石",
                    "merchant": f"在广场摆摊交易了{trade_count}次" if trade_count > 0 else "在广场打理生意",
                    "elder": f"给年轻人们分享了{work_count}次古老的知识",
                    "teacher": f"教导了{work_count}次孩子们读书写字",
                    "storyteller": f"讲述了{work_count}次有趣的冒险故事",
                    "player": "在小镇里四处探索"
                }
                narrative_parts.append(role_work_desc.get(agent.identity.role.value, f"完成了{work_count}次工作"))
            if talk_count > 0:
                narrative_parts.append(f"和镇民们交谈了{talk_count}次")
            if move_count > 0:
                narrative_parts.append(f"在小镇中往返了{move_count}次")
            if rest_count > 0:
                narrative_parts.append(f"休息了{rest_count}次恢复体力")

            if not narrative_parts:
                narrative_parts.append("今天比较悠闲，在附近散步观察")

            # 变化描述
            changes = []
            if energy_change > 5:
                changes.append("精神饱满")
            elif energy_change < -10:
                changes.append("显得有些疲惫")
            elif energy_change < -5:
                changes.append("体力有所下降")

            if gold_change_agent > 10:
                changes.append(f"收入了{gold_change_agent}金币，小有积蓄")
            elif gold_change_agent > 0:
                changes.append(f"赚了{gold_change_agent}金币")
            elif gold_change_agent < -5:
                changes.append(f"花费了{abs(gold_change_agent)}金币")

            change_text = "，".join(changes) if changes else "状态平稳"

            # 组合叙事
            narrative = f"{agent.identity.name}（{agent._get_role_cn(agent.identity.role.value)}）"
            narrative += "，".join(narrative_parts) + "。"
            narrative += f"目前{mood_desc}，{change_text}。"
            narrative += f"当前位于{agent._get_location_cn(agent.state.location)}，体力{round(agent.state.energy,1)}点，持有{agent.state.gold}金币。"

            agent_summaries.append({
                "id": agent.identity.id,
                "name": agent.identity.name,
                "role": agent.identity.role.value,
                "role_cn": agent._get_role_cn(agent.identity.role.value),
                "location": agent.state.location,
                "location_cn": agent._get_location_cn(agent.state.location),
                "energy": round(agent.state.energy, 1),
                "energy_change": energy_change,
                "mood": agent.state.mood.value,
                "mood_desc": mood_desc,
                "gold": agent.state.gold,
                "gold_change": gold_change_agent,
                "knowledge_count": len(agent.knowledge),
                "narrative": narrative,
                "goal": agent.top_goal().description if agent.top_goal() else "暂无目标"
            })

        # 重大事件摘要
        important_events = []
        for evt in self.current_day_events:
            t = evt.get("type", "")
            if t == EventType.WEATHER_CHANGE.value:
                important_events.append(f"天气变为{self.world.get_weather_name(evt.get('payload', ''))}")
            elif t == EventType.RESOURCE_FOUND.value:
                important_events.append(f"在{self._get_location_cn(evt.get('location', ''))}发现了新资源")
            elif t == EventType.ITEM_CRAFTED.value:
                important_events.append(f"有人制作了新的{evt.get('payload', '物品')}")
            elif t == EventType.FESTIVAL.value:
                important_events.append("全镇举办了节日庆典")
            elif t == EventType.DISASTER.value:
                important_events.append(f"发生了{evt.get('type', '灾害')}，居民们受到了影响")
            elif t == EventType.RUMOR_SPREAD.value:
                important_events.append("镇上有新的传闻在流传")
            elif t == EventType.SOCIAL_RELATION_CHANGE.value:
                important_events.append("一些居民之间的关系发生了变化")

        # 整体叙事摘要
        overall = f"第{day}天过去了，{weather_name}的天空下，小镇迎来了新的变化。"
        overall += f"镇上的{len(self.agents)}位居民"
        if happy_count >= len(self.agents) * 0.6:
            overall += "大多心情愉快，整个小镇洋溢着欢乐的气氛。"
        elif anxious_count >= len(self.agents) * 0.4:
            overall += "中有不少人显得焦虑，似乎有什么事情困扰着大家。"
        else:
            overall += "各司其职，过着平静的生活。"

        overall += f"今天平均体力为{round(avg_energy,1)}点。"
        if knowledge_change > 0:
            overall += f"知识库新增了{knowledge_change}条知识，小镇的文化更加丰富了。"
        if gold_change > 0:
            overall += f"全镇金币总量增加了{gold_change}，经济有所增长。"
        elif gold_change < -10:
            overall += f"全镇金币总量减少了{abs(gold_change)}，需要更加节约。"

        if important_events:
            overall += f"今天发生的重大事件：{'；'.join(important_events[:5])}。"

        # 地点动态
        location_dynamics = []
        for loc_id, agents_here in location_agents.items():
            if len(agents_here) >= 3:
                location_dynamics.append(f"{self._get_location_cn(loc_id)}非常热闹，有{len(agents_here)}位居民聚集")
            elif len(agents_here) == 0:
                location_dynamics.append(f"{self._get_location_cn(loc_id)}空无一人")
        if location_dynamics:
            overall += " " + "，".join(location_dynamics) + "。"

        return {
            "day": day,
            "weather": self.world.state.weather,
            "weather_name": weather_name,
            "overall_summary": overall,
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
        elif event.type == EventType.WEATHER_IMPACT:
            impact = event.payload.get("impact", 0)
            for a in self.agents:
                if a.state.location == event.location:
                    # 天气影响工作效率：降低体力消耗
                    a.state.energy = max(0, a.state.energy + impact * 10)
        elif event.type == EventType.SOCIAL_RELATION_CHANGE:
            agent1 = event.payload.get("agent1", "")
            agent2 = event.payload.get("agent2", "")
            change = event.payload.get("change", 0)
            for a in self.agents:
                if a.identity.id == agent1:
                    a.state.social_ties[agent2] = a.state.social_ties.get(agent2, 0) + change
                elif a.identity.id == agent2:
                    a.state.social_ties[agent1] = a.state.social_ties.get(agent1, 0) + change
        elif event.type == EventType.PRICE_CHANGE:
            # 价格变化，影响交易
            pass
        elif event.type == EventType.KNOWLEDGE_CONFLICT:
            claim1 = event.payload.get("claim1", "")
            claim2 = event.payload.get("claim2", "")
            self.knowledge.dispute(claim1, claim2)
        elif event.type == EventType.AGENT_GOAL_COMPLETE:
            agent_id = event.payload.get("agent_id", "")
            goal = event.payload.get("goal", "")
            for a in self.agents:
                if a.identity.id == agent_id:
                    # 完成目标，心情变好
                    a.state.mood = Mood.HAPPY
                    a.state.gold += 20
                    break
        elif event.type == EventType.FESTIVAL:
            # 节日：所有人心情变好（外向的人更开心，内向的人反应平淡）
            for a in self.agents:
                extraversion = a.identity.personality.get('extraversion', 0.5)
                agreeableness = a.identity.personality.get('agreeableness', 0.5)
                # 外向+宜人性高→非常开心
                if extraversion > 0.6 and agreeableness > 0.5:
                    a.state.mood = Mood.HAPPY
                    a.state.energy = min(100, a.state.energy + 15)
                else:
                    a.state.mood = Mood.NEUTRAL if a.state.mood != Mood.HAPPY else Mood.HAPPY
                    a.state.energy = min(100, a.state.energy + 5)
                a.state.energy = min(100, a.state.energy + 10)
        elif event.type == EventType.DISASTER:
            # 灾害：根据人格不同反应不同
            disaster_type = event.payload.get('type', 'unknown')
            for a in self.agents:
                stability = a.identity.personality.get('stability', 0.5)
                openness = a.identity.personality.get('openness', 0.5)
                # 稳定性低→反应更强烈（更害怕）
                energy_loss = 10 + int((1 - stability) * 10)
                gold_loss = 3 + int((1 - stability) * 5)
                a.state.energy = max(0, a.state.energy - energy_loss)
                a.state.gold = max(0, a.state.gold - gold_loss)
                # 稳定性低→更容易变焦虑/悲伤
                if stability < 0.4:
                    a.state.mood = Mood.ANXIOUS
                elif stability > 0.7:
                    a.state.mood = Mood.NEUTRAL
            # 减少荒野资源
            if event.location in self.world.resources:
                for r in self.world.resources[event.location]:
                    self.world.resources[event.location][r] = max(0, self.world.resources[event.location][r] - 10)
                for r in self.world.resources[event.location]:
                    self.world.resources[event.location][r] = max(0, self.world.resources[event.location][r] - 10)
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
        loc_cn = agent._get_location_cn(agent.state.location)
        if t == "move" and tgt:
            self.world.remove_agent_from_location(agent.identity.id, agent.state.location)
            agent.state.location = tgt
            self.world.add_agent_to_location(agent.identity.id, tgt)
            agent.state.energy -= 5
            self.daily_agent_logs[agent.identity.id].append(f"移动到了{self._get_location_cn(tgt)}")
        elif t == "work":
            agent.state.energy -= 8
            role = agent.identity.role.value
            work_knowledge = {
                "blacksmith": ("锻造", f"在工坊锻造了优质的工具"),
                "carpenter": ("木工", f"在工坊制作了精美的木家具"),
                "forager": ("采集", f"在森林里采集了新鲜的食材和草药"),
                "farmer": ("农耕", f"在田地里辛勤耕种，期待丰收"),
                "scout": ("探索", f"探索了荒野的未知区域，绘制了新地图"),
                "healer": ("医疗", f"在学校救治了病人，配制药剂"),
                "miner": ("采矿", f"在矿洞深处挖掘出珍贵的矿石"),
                "merchant": ("商业", f"在广场打理生意，了解市场行情"),
                "elder": ("知识", f"给年轻人们讲述了古老的传说和智慧"),
                "teacher": ("教育", f"教导孩子们读书写字，传播知识"),
                "storyteller": ("故事", f"给大家讲述精彩的冒险故事"),
            }
            if role in work_knowledge:
                subject, desc = work_knowledge[role]
                self.knowledge.observe(agent.identity.id, subject, desc, agent.state.location)
            if role in ["blacksmith", "carpenter"]:
                agent.state.gold += 5
                agent.state.inventory.append("tool")
            elif role in ["forager", "farmer"]:
                agent.state.gold += 3
                agent.state.inventory.append("food")
            elif role == "scout":
                agent.state.gold += 4
            elif role == "healer":
                agent.state.gold += 4
            elif role == "miner":
                agent.state.gold += 5
            else:
                agent.state.gold += 2
            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}工作")
        elif t == "rest":
            agent.state.energy = min(100, agent.state.energy + 10)
            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}休息恢复体力")
        elif t == "sleep":
            agent.state.energy = min(100, agent.state.energy + 20)
            self.daily_agent_logs[agent.identity.id].append("睡觉休息")
        elif t == "talk":
            agent.state.energy -= 2
            agent.state.gold += 1
            # 社交时传播知识
            claims = self.knowledge.agent_knowledge(agent.identity.id)
            if claims and len(claims) > 0:
                top = max(claims, key=lambda c: c.confidence)
                if top.confidence > 0.5:
                    self.knowledge.propagate(top.id, agent.identity.id, 'nearby_agents', 0.7)
            # 社交时增加与在场Agent的好感度
            for other in self.agents:
                if other.identity.id == agent.identity.id:
                    continue
                if other.state.location == agent.state.location:
                    # 宜人性高→更容易增加好感
                    agreeableness = agent.identity.personality.get('agreeableness', 0.5)
                    extraversion = agent.identity.personality.get('extraversion', 0.5)
                    tie_change = 0.5 + agreeableness * 0.5 + extraversion * 0.3
                    current_tie = agent.state.social_ties.get(other.identity.id, 0)
                    agent.state.social_ties[other.identity.id] = current_tie + tie_change
                    # 双向关系也增加（但少一些）
                    other_tie = other.state.social_ties.get(agent.identity.id, 0)
                    other.state.social_ties[agent.identity.id] = other_tie + tie_change * 0.7
            self.daily_agent_logs[agent.identity.id].append(f'和{loc_cn}的人聊天')
        elif t == "trade":
            if agent.identity.role.value == "merchant":
                agent.state.gold += 8
            else:
                agent.state.gold += 2
            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}进行交易")
        elif t == "investigate":
            agent.state.energy -= 3
            self.knowledge.observe(agent.identity.id, "investigate", f"在{loc_cn}调查了周围的情况", agent.state.location)
            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}调查周围环境")
        elif t == "observe":
            agent.state.energy -= 1
            self.daily_agent_logs[agent.identity.id].append(f"在{loc_cn}观察四周")
        agent.state.energy = max(0, min(100, agent.state.energy))

    def stop(self):
        self._running = False
        self.db.close()
    def stop(self):
        self._running = False
        self.db.close()
