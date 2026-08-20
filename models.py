from dataclasses import dataclass,field
from enum import Enum
from typing import Optional,Dict,List,Any
import time

class Role(str,Enum):
    ELDER="elder";BLACKSMITH="blacksmith";CARPENTER="carpenter";FORAGER="forager";SCOUT="scout";MERCHANT="merchant";TEACHER="teacher";FARMER="farmer";STORYTELLER="storyteller";HEALER="healer";MINER="miner";PLAYER="player"

class Mood(str,Enum):
    HAPPY="happy";NEUTRAL="neutral";ANXIOUS="anxious";ANGRY="angry";SAD="sad"

class ClaimSource(str,Enum):
    OBSERVATION="observation";CONVERSATION="conversation"

class ClaimScope(str,Enum):
    PRIVATE="private";PUBLIC="public"

# 仅保留：被 events.py 调度且被 tick._process_event 处理的事件类型
class EventType(str,Enum):
    WEATHER_CHANGE="weather_change";RESOURCE_FOUND="resource_found";SOCIAL_ENCOUNTER="social_encounter";ITEM_CRAFTED="item_crafted";RUMOR_SPREAD="rumor_spread";WEATHER_IMPACT="weather_impact";SOCIAL_RELATION_CHANGE="social_relation_change";FESTIVAL="festival";DISASTER="disaster";MERCHANT_ARRIVAL="merchant_arrival";TOWN_MEETING="town_meeting";MYSTERIOUS_STRANGER="mysterious_stranger";ANIMAL_ATTACK="animal_attack";GOLDEN_DISCOVERY="golden_discovery"

@dataclass
class KnowledgeClaim:
    id:str;subject:str;claim:str;source:ClaimSource;confidence:float;scope:ClaimScope;created_by:str;location:str
    actionable:bool=False          # 是否影响行为
    action_type:str=""             # 影响的行动类型
    action_target:str=""           # 行动目标（地点/资源/Agent ID）
    emotional_valence:float=0.0    # 情感趋向: -1.0(恐惧) ~ 1.0(期待)
    created_at:float=field(default_factory=time.time);contradicted_by:List[str]=field(default_factory=list);solidified:bool=False;version:int=1

@dataclass
class AgentTask:
    description:str;location:str;started_at:float=field(default_factory=time.time)

@dataclass
class AgentState:
    energy:float=100.0;mood:Mood=Mood.NEUTRAL;gold:int=0;location:str="";current_task:Optional[AgentTask]=None;inventory:List[str]=field(default_factory=list);social_ties:Dict[str,float]=field(default_factory=dict);food:int=5;hunger:float=0;ap:int=12;ap_max:int=12
    night_ap:int=0  # 十三时：独立的夜间行动力（每13天+1，仅夜晚可用）
    faction_id:str=""
    # 情绪系统 v2（gameplay-design-v4 §3）：4 维情绪 + 习惯概率表
    # emotions: 愉悦/焦虑/愤怒/悲伤，各 0-100，主导情绪驱动 mood（UI 表情层）
    emotions:Dict[str,float]=field(default_factory=lambda: {"joy":50.0,"anxiety":50.0,"anger":50.0,"sadness":50.0})
    # habit_bias: {"情境": {"行为": 出现概率增量}} —— 情绪记忆→习惯（近似 RL），随性格演化
    habit_bias:Dict[str,Dict[str,float]]=field(default_factory=dict)
    # 习惯固化计数：{"情境_行为": 次数}，达阈值触发性格演化
    habit_counts:Dict[str,int]=field(default_factory=dict)

@dataclass
class AgentIdentity:
    id:str;name:str;role:Role;traits:List[str]=field(default_factory=list);skills:Dict[str,int]=field(default_factory=dict)
    personality: Dict[str, float] = field(default_factory=lambda: {"extraversion": 0.5, "conscientiousness": 0.5, "openness": 0.5, "agreeableness": 0.5, "stability": 0.5})

@dataclass
class Goal:
    id:str;description:str;base_priority:float=5.0;urgency:float=0.5;completed:bool=False

@dataclass
class Event:
    tick:int;type:EventType;location:str;payload:Dict[str,Any]=field(default_factory=dict)

@dataclass
class PlayerAction:
    tick:int;action_type:str;payload:Dict[str,Any];result:str

@dataclass
class TradeOffer:
    from_agent:str;to_agent:str;item:str;price:int;status:str="pending"

@dataclass
class WorldState:
    tick:int=0;weather:str="clear";trade_offers:List[TradeOffer]=field(default_factory=list)
    location_levels:Dict[str,int]=field(default_factory=lambda: {"square":1,"workshop":1,"wilderness":1,"school":1,"mine":1})
