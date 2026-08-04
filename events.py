"""事件系统模块"""
import random
from typing import Dict,List,Callable
from models import Event,EventType

class EventBus:
    def __init__(self):
        self._subscribers = {}
        self._event_log = []
        self._scheduled = []


    def publish(self, event):
        self._event_log.append(event)

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
        # 一天 20 小时（世界观：地球转速变慢），事件排布在清醒时段（清晨5点至傍晚16点）
        base = (day-1)*20
        # 清晨天气：与 world.advance 共用同一来源（避免双随机不一致）
        # 实际天气由 world._change_weather 在 tick%20==6 决定，此处仅调度播报事件
        weather = world.state.weather
        self.bus.schedule(Event(tick=base+6, type=EventType.WEATHER_CHANGE, location="square", payload={"weather": weather}), base+6)

        # 天气影响事件：根据天气影响工作效率
        impact = self._get_weather_impact(weather)
        self.bus.schedule(Event(tick=base+7, type=EventType.WEATHER_IMPACT, location="square", payload={"impact": impact, "weather": weather}), base+7)

        # 资源发现事件
        if random.random()<0.7:
            r = ["wood","stone","food","metal"]
            a = random.choice(agent_ids)
            self.bus.schedule(Event(tick=base+9, type=EventType.RESOURCE_FOUND, location="wilderness", payload={"resource": random.choice(r), "amount": random.randint(1,3), "agent_id": a}), base+9)

        # 社交相遇事件
        if len(agent_ids)>=2:
            a1,a2 = random.sample(agent_ids,2)
            self.bus.schedule(Event(tick=base+11, type=EventType.SOCIAL_ENCOUNTER, location="square", payload={"agents":[a1,a2]}), base+11)
            # 社交关系变化
            relation_change = random.choice([-0.2, -0.1, 0.1, 0.2])
            self.bus.schedule(Event(tick=base+11, type=EventType.SOCIAL_RELATION_CHANGE, location="square", payload={"agent1": a1, "agent2": a2, "change": relation_change}), base+11)

        # 物品制作事件
        if random.random()<0.5:
            items = ["tool","furniture","weapon"]
            a = random.choice(agent_ids)
            self.bus.schedule(Event(tick=base+12, type=EventType.ITEM_CRAFTED, location="workshop", payload={"item": random.choice(items), "agent_id": a}), base+12)

        # 传闻传播事件
        if random.random()<0.4:
            claims = ["夜晚有奇怪的声音","物资悄悄不见了","森林里有新的发现","老井闹鬼了","有新的商人要来"]
            f,t = random.sample(agent_ids,2)
            self.bus.schedule(Event(tick=base+14, type=EventType.RUMOR_SPREAD, location="square", payload={"claim": random.choice(claims), "from": f, "to": t}), base+14)

        # 节日事件（10%概率）
        if random.random() < 0.1:
            self.bus.schedule(Event(tick=base+15, type=EventType.FESTIVAL, location="square", payload={"name": "丰收节", "description": "全镇庆祝丰收，所有人心情变好"}), base+15)

        # 灾害事件（5%概率）
        if random.random() < 0.05:
            disaster = random.choice(["storm", "flood", "drought"])
            self.bus.schedule(Event(tick=base+16, type=EventType.DISASTER, location="wilderness", payload={"type": disaster, "impact": "资源减少，Agent体力下降"}), base+16)

        # === 补充事件（此前定义了处理但从未调度，让小镇更"活"）===
        # 商人来访（8%）：广场居民心情变好、获得金币
        if random.random() < 0.08:
            self.bus.schedule(Event(tick=base+13, type=EventType.MERCHANT_ARRIVAL, location="square", payload={"name": "路过的行商"}), base+13)
        # 动物袭击（5%）：荒野居民受惊
        if random.random() < 0.05:
            self.bus.schedule(Event(tick=base+12, type=EventType.ANIMAL_ATTACK, location="wilderness", payload={"type": "野狼"}), base+12)
        # 神秘陌生人（5%）：带来传闻，可能引发后续谣言链
        if random.random() < 0.05:
            self.bus.schedule(Event(tick=base+14, type=EventType.MYSTERIOUS_STRANGER, location="square", payload={}), base+14)
        # 小镇集会（4%）：广场居民互相好感上升
        if random.random() < 0.04:
            self.bus.schedule(Event(tick=base+15, type=EventType.TOWN_MEETING, location="square", payload={"topic": "商讨镇务"}), base+15)
        # 金色发现（3%）：某位居民发现稀有矿石
        if random.random() < 0.03:
            self.bus.schedule(Event(tick=base+16, type=EventType.GOLDEN_DISCOVERY, location="mine", payload={"agent_id": random.choice(agent_ids)}), base+16)
    
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
    
    
