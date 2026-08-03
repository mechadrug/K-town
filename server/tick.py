import asyncio,random
from .world import World
from .events import EventBus,EventScheduler
from .knowledge import KnowledgeEngine
from .logger import Logger
from .llm import LLMClient
from .models import EventType

class TickEngine:
    def __init__(self,world,bus,agents,knowledge,logger,llm,rate=1.0,day_length=24):
        self.world=world;self.bus=bus;self.agents=agents;self.knowledge=knowledge
        self.logger=logger;self.llm=llm;self.rate=rate;self.day_length=day_length
        self._running=False
        self.scheduler=EventScheduler(bus)

    async def run(self):
        self._running=True
        while self._running:
            await self.step()
            await asyncio.sleep(self.rate)

    async def step(self):
        tick=self.world.state.tick+1
        hour=tick%24
        self.world.advance(tick)
        self.bus.flush_scheduled(tick)
        for event in self.bus.all_events:
            await self._process_event(event)
        self.bus.clear_events()
        loc_map={}
        for a in self.agents:
            loc_map.setdefault(a.state.location,[]).append(a.identity.id)
        for loc_id,loc_data in self.world.locations.items():
            loc_data["agents"]=loc_map.get(loc_id,[])
        for agent in self.agents:
            evts=self.bus.get_events_at(agent.state.location)
            evt_strs=[f"{e.type.value} at {e.location}" for e in evts]
            here=loc_map.get(agent.state.location,[])
            agent.perceive(evt_strs)
            agent.think(hour)
            action=agent.decide(hour,here,evt_strs)
            self.logger.log_decision(tick,agent.identity.id,action["desc"],action["type"],agent.top_goal().description if agent.top_goal() else "",0.8,"rule")
            await self._handle_action(agent,action)
        if hour==0 and tick>1:
            day=tick//24+1
            aids=[a.identity.id for a in self.agents]
            self.scheduler.generate_daily_schedule(day,aids)

    async def _process_event(self,event):
        if event.type==EventType.WEATHER_CHANGE:
            w=event.payload.get("weather","?")
            for a in self.agents:
                if a.state.location==event.location:
                    c=self.knowledge.observe(a.identity.id,"weather",f"Today weather is {w}",a.state.location)
                    self.logger.log_knowledge(0,c.id,a.identity.id,"create","",c.claim)
        elif event.type==EventType.RESOURCE_FOUND:
            r=event.payload.get("resource","?")
            aid=event.payload.get("agent_id","")
            if aid: self.knowledge.observe(aid,"resource",f"Found {r} in {event.location}",event.location)
        elif event.type==EventType.SOCIAL_ENCOUNTER:
            aids=event.payload.get("agents",[])
            for aid in aids:
                self.knowledge.observe(aid,"social",f"Met someone at {event.location}",event.location)
            if len(aids)>=2:
                claims=self.knowledge.agent_knowledge(aids[0])
                if claims:
                    top=max(claims,key=lambda c:c.confidence)
                    self.knowledge.propagate(top.id,aids[0],aids[1],0.8)
        elif event.type==EventType.ITEM_CRAFTED:
            item=event.payload.get("item","?")
            aid=event.payload.get("agent_id","")
            if aid: self.knowledge.observe(aid,"craft",f"Crafted {item}",event.location)
        elif event.type==EventType.RUMOR_SPREAD:
            claim=event.payload.get("claim","")
            f,t=event.payload.get("from",""),event.payload.get("to","")
            if f and t and claim:
                self.knowledge.observe(f,"rumor",claim,event.location)
                self.knowledge.observe(t,"rumor",f"Heard that {claim}",event.location)

    async def _handle_action(self,agent,action):
        t=action.get("type","")
        tgt=action.get("target","")
        if t=="move" and tgt:
            self.world.remove_agent_from_location(agent.identity.id,agent.state.location)
            agent.state.location=tgt
            self.world.add_agent_to_location(agent.identity.id,tgt)
            agent.state.energy-=5
        elif t=="work":
            agent.state.energy-=8;agent.state.gold+=2
        elif t=="rest":
            agent.state.energy=min(100,agent.state.energy+10)
        elif t=="sleep":
            agent.state.energy=min(100,agent.state.energy+20)
        elif t=="talk":
            agent.state.energy-=2
        agent.state.energy=max(0,min(100,agent.state.energy))

    def stop(self):
        self._running=False
