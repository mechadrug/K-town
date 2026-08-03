from dataclasses import dataclass,field
from enum import Enum
from typing import Optional,Dict,List,Any
import time,uuid

class Role(str,Enum):
    ELDER="elder";BLACKSMITH="blacksmith";CARPENTER="carpenter";FORAGER="forager";SCOUT="scout";MERCHANT="merchant";TEACHER="teacher";FARMER="farmer";STORYTELLER="storyteller";HEALER="healer";MINER="miner";PLAYER="player"

class Mood(str,Enum):
    HAPPY="happy";NEUTRAL="neutral";ANXIOUS="anxious";ANGRY="angry";SAD="sad"

class ClaimSource(str,Enum):
    OBSERVATION="observation";CONVERSATION="conversation";REASONING="reasoning";RUMOR="rumor";PLAYER="player"

class ClaimScope(str,Enum):
    PRIVATE="private";GROUP="group";PUBLIC="public"

class EventType(str,Enum):
    WEATHER_CHANGE="weather_change";RESOURCE_FOUND="resource_found";SOCIAL_ENCOUNTER="social_encounter";ITEM_CRAFTED="item_crafted";RUMOR_SPREAD="rumor_spread"

@dataclass
class KnowledgeClaim:
    id:str;subject:str;claim:str;source:ClaimSource;confidence:float;scope:ClaimScope;created_by:str;location:str
    created_at:float=field(default_factory=time.time);contradicted_by:List[str]=field(default_factory=list);solidified:bool=False;version:int=1

@dataclass
class AgentTask:
    description:str;location:str;started_at:float=field(default_factory=time.time)

@dataclass
class AgentState:
    energy:float=100.0;mood:Mood=Mood.NEUTRAL;gold:int=0;location:str="";current_task:Optional[AgentTask]=None;inventory:List[str]=field(default_factory=list);social_ties:Dict[str,float]=field(default_factory=dict)

@dataclass
class AgentIdentity:
    id:str;name:str;role:Role;traits:List[str]=field(default_factory=list);skills:Dict[str,int]=field(default_factory=dict)

@dataclass
class Goal:
    id:str;description:str;base_priority:float=5.0;urgency:float=0.5;completed:bool=False

@dataclass
class MemoryEntry:
    id:str=field(default_factory=lambda:str(uuid.uuid4())[:8]);summary:str="";importance:float=5.0;location:str="";timestamp:float=field(default_factory=time.time);related_agents:List[str]=field(default_factory=list)

@dataclass
class Event:
    tick:int;type:EventType;location:str;payload:Dict[str,Any]=field(default_factory=dict);timestamp:float=field(default_factory=time.time)

@dataclass
class WorldState:
    tick:int=0;weather:str="clear";locations:Dict[str,dict]=field(default_factory=dict)

