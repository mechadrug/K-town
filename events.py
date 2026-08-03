"""事件系统模块"""
import random
from typing import Dict,List,Callable
from models import Event,EventType

class EventBus:
    def __init__(self):
        self._subscribers = {}
        self._event_log = []
        self._scheduled = []

    def subscribe(self, location, callback):
        self._subscribers.setdefault(location,[]).append(callback)

    def publish(self, event):
        self._event_log.append(event)
        for cb in self._subscribers.get(event.location,[]):
            try: cb(event)
            except: pass

    def schedule(self, event, at_tick):
        event.tick = at_tick
        self._scheduled.append(event)

    def flush_scheduled(self, current_tick):
        remaining = []
        for e in self._scheduled:
            if e.tick <= current_tick:
                self.publish(e)
            else:
                remaining.append(e)
        self._scheduled = remaining

    def get_events_at(self, location):
        return [e for e in self._event_log if e.location == location]

    def clear_events(self):
        self._event_log.clear()

    @property
    def all_events(self):
        return list(self._event_log)


class EventScheduler:
    def __init__(self, bus):
        self.bus = bus

    def generate_daily_schedule(self, day, agent_ids, world):
        base = (day-1)*24
        # 每天早上6点更新天气
        w = ["clear","cloudy","rainy","snowy","windy"]
        weights = [0.5, 0.2, 0.15, 0.1, 0.05]
        weather = random.choices(w, weights=weights, k=1)[0]
        self.bus.schedule(Event(tick=base+6, type=EventType.WEATHER_CHANGE, location="square", payload={"weather": weather}), base+6)
        
        # 天气影响事件：根据天气影响工作效率
        impact = self._get_weather_impact(weather)
        self.bus.schedule(Event(tick=base+7, type=EventType.WEATHER_IMPACT, location="square", payload={"impact": impact, "weather": weather}), base+7)
        
        # 资源发现事件
        if random.random()<0.7:
            r = ["wood","stone","food","metal"]
            a = random.choice(agent_ids)
            self.bus.schedule(Event(tick=base+10, type=EventType.RESOURCE_FOUND, location="wilderness", payload={"resource": random.choice(r), "amount": random.randint(1,3), "agent_id": a}), base+10)
        
        # 社交相遇事件
        if len(agent_ids)>=2:
            a1,a2 = random.sample(agent_ids,2)
            self.bus.schedule(Event(tick=base+12, type=EventType.SOCIAL_ENCOUNTER, location="square", payload={"agents":[a1,a2]}), base+12)
            # 社交关系变化
            relation_change = random.choice([-0.2, -0.1, 0.1, 0.2])
            self.bus.schedule(Event(tick=base+12, type=EventType.SOCIAL_RELATION_CHANGE, location="square", payload={"agent1": a1, "agent2": a2, "change": relation_change}), base+12)
        
        # 物品制作事件
        if random.random()<0.5:
            items = ["tool","furniture","weapon"]
            a = random.choice(agent_ids)
            self.bus.schedule(Event(tick=base+15, type=EventType.ITEM_CRAFTED, location="workshop", payload={"item": random.choice(items), "agent_id": a}), base+15)
        
        # 价格变化事件
        price_change = {
            "food": random.randint(-2, 2),
            "tool": random.randint(-3, 3),
            "material": random.randint(-1, 1)
        }
        self.bus.schedule(Event(tick=base+16, type=EventType.PRICE_CHANGE, location="square", payload={"price_changes": price_change}), base+16)
        
        # 传闻传播事件
        if random.random()<0.4:
            claims = ["strange sounds at night","missing supplies","new discovery in woods","the old well is haunted","a new merchant is coming"]
            f,t = random.sample(agent_ids,2)
            self.bus.schedule(Event(tick=base+18, type=EventType.RUMOR_SPREAD, location="square", payload={"claim": random.choice(claims), "from": f, "to": t}), base+18)
        
        # 节日事件（10%概率）
        if random.random() < 0.1:
            self.bus.schedule(Event(tick=base+19, type=EventType.FESTIVAL, location="square", payload={"name": "丰收节", "description": "全镇庆祝丰收，所有人心情变好"}), base+19)
        
        # 灾害事件（5%概率）
        if random.random() < 0.05:
            disaster = random.choice(["storm", "flood", "drought"])
            self.bus.schedule(Event(tick=base+20, type=EventType.DISASTER, location="wilderness", payload={"type": disaster, "impact": "资源减少，Agent体力下降"}), base+20)
    
    def _get_weather_impact(self, weather):
        """获取天气对工作的影响"""
        impact_map = {
            "clear": 0,
            "cloudy": -0.1,
            "rainy": -0.2,
            "snowy": -0.3,
            "windy": -0.15
        }
        return impact_map.get(weather, 0)
    
    def generate_knowledge_conflict_event(self, day, claim1_id, claim2_id, location):
        """生成知识冲突事件"""
        base = (day-1)*24
        self.bus.schedule(Event(tick=base+14, type=EventType.KNOWLEDGE_CONFLICT, location=location, payload={"claim1": claim1_id, "claim2": claim2_id}), base+14)
    
    def generate_goal_complete_event(self, day, agent_id, goal, location):
        """生成Agent完成目标事件"""
        base = (day-1)*24
        self.bus.schedule(Event(tick=base+17, type=EventType.AGENT_GOAL_COMPLETE, location=location, payload={"agent_id": agent_id, "goal": goal}), base+17)
