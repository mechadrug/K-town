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
    WEATHER_CHANGE="weather_change";RESOURCE_FOUND="resource_found";SOCIAL_ENCOUNTER="social_encounter";ITEM_CRAFTED="item_crafted";RUMOR_SPREAD="rumor_spread";PLAYER_ACTION="player_action";TRADE="trade";PRICE_CHANGE="price_change";WEATHER_IMPACT="weather_impact";SOCIAL_RELATION_CHANGE="social_relation_change";KNOWLEDGE_CONFLICT="knowledge_conflict";AGENT_GOAL_COMPLETE="agent_goal_complete";FESTIVAL="festival";DISASTER="disaster";MERCHANT_ARRIVAL="merchant_arrival";SKILL_SHARE="skill_share";TOWN_MEETING="town_meeting";MYSTERIOUS_STRANGER="mysterious_stranger";HARVEST_FESTIVAL="harvest_festival";ANIMAL_ATTACK="animal_attack";GOLDEN_DISCOVERY="golden_discovery";BUILDING_UPGRADE="building_upgrade"

@dataclass
class KnowledgeClaim:
    id:str;subject:str;claim:str;source:ClaimSource;confidence:float;scope:ClaimScope;created_by:str;location:str
    created_at:float=field(default_factory=time.time);contradicted_by:List[str]=field(default_factory=list);solidified:bool=False;version:int=1

@dataclass
class AgentTask:
    description:str;location:str;started_at:float=field(default_factory=time.time)

@dataclass
class AgentState:
    energy:float=100.0;mood:Mood=Mood.NEUTRAL;gold:int=0;location:str="";current_task:Optional[AgentTask]=None;inventory:List[str]=field(default_factory=list);social_ties:Dict[str,float]=field(default_factory=dict);food:int=5;hunger:float=0;ap:int=12;ap_max:int=12

@dataclass
class AgentIdentity:
    id:str;name:str;role:Role;traits:List[str]=field(default_factory=list);skills:Dict[str,int]=field(default_factory=dict)
    personality: Dict[str, float] = field(default_factory=lambda: {"extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5, "stability": 0.5})

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
class PlayerAction:
    tick:int;action_type:str;payload:Dict[str,Any];result:str;timestamp:float=field(default_factory=time.time)

@dataclass
class TradeOffer:
    from_agent:str;to_agent:str;item:str;price:int;status:str="pending";created_at:float=field(default_factory=time.time)

@dataclass
class WorldState:
    tick:int=0;weather:str="clear";locations:Dict[str,dict]=field(default_factory=dict);trade_offers:List[TradeOffer]=field(default_factory=list)
