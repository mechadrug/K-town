import random,time,uuid
from typing import List,Optional
from .models import AgentIdentity,AgentState,Goal,MemoryEntry,Mood,Role,KnowledgeClaim,ClaimSource

class Agent:
    def __init__(self, identity:AgentIdentity, location="square"):
        self.identity = identity
        self.state = AgentState(location=location)
        self.memory_short = []
        self.memory_long = []
        self.diary = []
        self.goals = []
        self.knowledge = []

    def perceive(self, events):
        self.memory_short.extend(events)
        if len(self.memory_short)>20:
            self.memory_short = self.memory_short[-20:]

    def think(self, hour):
        if len(self.memory_short)>10:
            for m in self.memory_short[-5:]:
                self.memory_long.append(MemoryEntry(summary=m,importance=7.0,location=self.state.location))
            self.memory_short = self.memory_short[:-5]
        if self.state.energy<20: self.state.mood=Mood.SAD
        elif self.state.energy<50: self.state.mood=Mood.ANXIOUS
        elif self.state.energy>80: self.state.mood=Mood.HAPPY
        self.state.energy = max(0, self.state.energy-1)
        if hour>=21 or hour<6:
            self.state.energy = min(100, self.state.energy+15)

    def decide(self, hour, agents_here, events):
        n = self.identity.name
        if self.state.energy<20: return {"type":"rest","desc":f"{n} is too tired, resting","target":""}
        if hour>=21 or hour<6: return {"type":"sleep","desc":f"{n} is sleeping","target":""}
        slot = self._slot(hour)
        if slot and self.state.location==slot["loc"]:
            return self._role(slot)
        if len(agents_here)>1 and ("social" in self.identity.traits or self.state.mood==Mood.HAPPY):
            return {"type":"talk","desc":f"{n} starts a conversation","target":""}
        if events:
            return {"type":"investigate","desc":f"{n} investigates an event","target":""}
        if slot and self.state.location!=slot["loc"]:
            return {"type":"move","desc":f"{n} moves to {slot['loc']}","target":slot["loc"]}
        return {"type":"observe","desc":f"{n} observes surroundings","target":""}

    def _slot(self, hour):
        s=[(6,8,"square"),(8,12,"workshop"),(12,13,"square"),(13,17,"workshop"),(17,19,"square"),(19,21,"square"),(21,6,"square")]
        for a,b,l in s:
            if a<b:
                if a<=hour<b: return {"loc":l}
            else:
                if hour>=a or hour<b: return {"loc":l}
        return None

    def _role(self, slot):
        n=self.identity.name
        m={Role.ELDER:("observe",f"{n} shares knowledge"),Role.BLACKSMITH:("work",f"{n} forges tools"),Role.CARPENTER:("work",f"{n} crafts wood items"),Role.FORAGER:("work",f"{n} forages"),Role.SCOUT:("work",f"{n} scouts"),Role.FARMER:("work",f"{n} tends fields"),Role.MERCHANT:("trade",f"{n} trades goods"),Role.TEACHER:("talk",f"{n} teaches skills"),Role.STORYTELLER:("talk",f"{n} tells a story"),Role.PLAYER:("observe",f"{n} looks around")}
        t,d=m.get(self.identity.role,("work",f"{n} works"))
        return {"type":t,"desc":d,"target":""}

    def add_goal(self,desc,priority=5.0,urgency=0.5):
        self.goals.append(Goal(id=str(uuid.uuid4())[:8],description=desc,base_priority=priority,urgency=urgency))

    def top_goal(self):
        active=[g for g in self.goals if not g.completed]
        return max(active,key=lambda g:g.base_priority+g.urgency*10) if active else None

    def to_dict(self):
        g=self.top_goal()
        return {"id":self.identity.id,"name":self.identity.name,"role":self.identity.role.value,"energy":round(self.state.energy,1),"mood":self.state.mood.value,"gold":self.state.gold,"location":self.state.location,"goal":g.description if g else "","knowledge_count":len(self.knowledge)}

def populate_agents():
    agents=[]
    d=[("agent_elder","Grandmother Mae",Role.ELDER,["wise","social","patient"],"square",30),("agent_blacksmith","Forge Master Torin",Role.BLACKSMITH,["diligent","proud","honest"],"workshop",50),("agent_carpenter","Carpenter Lina",Role.CARPENTER,["creative","precise","quiet"],"workshop",40),("agent_forager","Forager Fern",Role.FORAGER,["observant","resourceful","independent"],"wilderness",15),("agent_scout","Scout Rowan",Role.SCOUT,["curious","brave","restless"],"wilderness",20),("agent_merchant","Merchant Vesper",Role.MERCHANT,["social","shrewd","charming"],"square",100),("agent_teacher","Teacher Alden",Role.TEACHER,["social","patient","knowledgeable"],"square",35),("agent_farmer","Farmer Clay",Role.FARMER,["patient","diligent","quiet"],"wilderness",25),("agent_storyteller","Storyteller Iris",Role.STORYTELLER,["social","creative","charismatic"],"square",20),("agent_player","Traveler",Role.PLAYER,["adaptable","curious"],"square",10)]
    for aid,name,role,traits,loc,gold in d:
        a=Agent(AgentIdentity(id=aid,name=name,role=role,traits=traits),location=loc)
        a.state.gold=gold
        agents.append(a)
    for a in agents:
        for b in agents:
            if a.identity.id!=b.identity.id:
                a.state.social_ties[b.identity.id]=0.0
    gm={"agent_elder":("preserve_knowledge",8,0.3),"agent_blacksmith":("craft_tools",9,0.5),"agent_carpenter":("build_furniture",8,0.4),"agent_forager":("gather_food",10,0.7),"agent_scout":("explore_wilderness",9,0.5),"agent_merchant":("trade_goods",9,0.6),"agent_teacher":("teach_skills",8,0.3),"agent_farmer":("grow_crops",10,0.6),"agent_storyteller":("collect_stories",7,0.3),"agent_player":("explore_town",6,0.2)}
    for a in agents:
        if a.identity.id in gm:
            desc,pri,urg=gm[a.identity.id]
            a.add_goal(desc,pri,urg)
    return agents
