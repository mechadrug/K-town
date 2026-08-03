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

    def generate_daily_schedule(self, day, agent_ids):
        base = (day-1)*24
        w = ["clear","cloudy","rainy"]
        self.bus.schedule(Event(tick=base+6,type=EventType.WEATHER_CHANGE,location="square",payload={"weather":w[random.randint(0,2)]}),base+6)
        if random.random()<0.7:
            r = ["wood","stone","food","metal"]
            a = random.choice(agent_ids)
            self.bus.schedule(Event(tick=base+10,type=EventType.RESOURCE_FOUND,location="wilderness",payload={"resource":random.choice(r),"amount":random.randint(1,3),"agent_id":a}),base+10)
        if len(agent_ids)>=2:
            a1,a2 = random.sample(agent_ids,2)
            self.bus.schedule(Event(tick=base+12,type=EventType.SOCIAL_ENCOUNTER,location="square",payload={"agents":[a1,a2]}),base+12)
        if random.random()<0.5:
            items = ["tool","furniture","weapon"]
            a = random.choice(agent_ids)
            self.bus.schedule(Event(tick=base+15,type=EventType.ITEM_CRAFTED,location="workshop",payload={"item":random.choice(items),"agent_id":a}),base+15)
        if random.random()<0.4:
            claims = ["strange sounds at night","missing supplies","new discovery in woods"]
            f,t = random.sample(agent_ids,2)
            self.bus.schedule(Event(tick=base+18,type=EventType.RUMOR_SPREAD,location="square",payload={"claim":random.choice(claims),"from":f,"to":t}),base+18)

