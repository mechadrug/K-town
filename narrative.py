"""叙事引擎 v2.0 — 事件因果链"""
import random
import time
from typing import Dict,List,Any,Optional
from models import EventType

class StoryArc:
    """故事弧：跨天叙事"""
    
    def __init__(self, arc_id: str, template: str, participants: List[str]):
        self.arc_id = arc_id
        self.template = template
        self.participants = participants
        self.stage = 0
        self.max_stages = 4
        self.tension = 0  # 0-10 张力值
        self.events: List[Dict[str, Any]] = []
        self.created_at = time.time()
        self.completed = False
    
    def advance(self, tick: int) -> Optional[Dict[str, Any]]:
        """推进故事弧到下一阶段"""
        if self.stage >= self.max_stages:
            self.completed = True
            return None
        
        self.stage += 1
        self.tension = min(10, self.stage * 2.5)
        
        stage_templates = self._get_stage_templates()
        if self.stage <= len(stage_templates):
            event = {
                "arc_id": self.arc_id,
                "stage": self.stage,
                "type": stage_templates[self.stage - 1]["type"],
                "location": stage_templates[self.stage - 1].get("location", "square"),
                "payload": {
                    "description": stage_templates[self.stage - 1].get("desc", ""),
                    "participants": self.participants,
                    "tension": self.tension,
                    "arc_template": self.template
                }
            }
            self.events.append(event)
            return event
        return None
    
    def _get_stage_templates(self) -> List[Dict[str, Any]]:
        """获取当前模板的阶段定义"""
        templates = {
            "resource_crisis": [
                {"type": "resource_depleted", "location": "wilderness", "desc": "资源开始减少，镇民们感到不安"},
                {"type": "price_change", "location": "square", "desc": "商人提高了物价，引发不满"},
                {"type": "town_meeting", "location": "square", "desc": "镇民集会讨论对策"},
                {"type": "resolution", "location": "square", "desc": "小镇找到了解决方案，恢复了平静"}
            ],
            "mystery": [
                {"type": "strange_event", "location": "wilderness", "desc": "荒野传出了奇怪的声音"},
                {"type": "investigation", "location": "wilderness", "desc": "侦察兵前去调查"},
                {"type": "discovery", "location": "wilderness", "desc": "发现了令人震惊的真相"},
                {"type": "revelation", "location": "square", "desc": "真相揭晓，小镇震惊"}
            ],
            "conflict": [
                {"type": "argument", "location": "square", "desc": "两个镇民发生了争执"},
                {"type": "faction_form", "location": "square", "desc": "镇民们开始选边站队"},
                {"type": "confrontation", "location": "square", "desc": "矛盾升级，气氛紧张"},
                {"type": "reconciliation", "location": "square", "desc": "在长者调解下，双方和解"}
            ]
        }
        return templates.get(self.template, templates["mystery"])


class NarrativeEngine:
    """叙事引擎：管理故事弧和事件因果链"""
    
    def __init__(self):
        self.active_arcs: Dict[str, StoryArc] = {}
        self.completed_arcs: List[StoryArc] = []
        self.narrative_summary: List[str] = []
        self.arc_counter = 0
    
    def tick(self, tick: int, agents, world, event_bus) -> List[Dict[str, Any]]:
        """每个Tick检查是否需要生成新故事弧或推进现有弧"""
        events = []
        
        # 检查触发条件
        new_arc = self._check_triggers(tick, agents, world)
        if new_arc:
            self.active_arcs[new_arc.arc_id] = new_arc
            events.append({
                "type": "story_arc_start",
                "payload": {"arc_id": new_arc.arc_id, "template": new_arc.template}
            })
        
        # 推进现有故事弧（每12个tick推进一次）
        if tick % 12 == 0:
            for arc_id, arc in list(self.active_arcs.items()):
                event = arc.advance(tick)
                if event:
                    events.append(event)
                    self.narrative_summary.append(
                        f"[Day {tick//24+1}] {event['payload']['description']}"
                    )
                if arc.completed:
                    self.completed_arcs.append(arc)
                    del self.active_arcs[arc_id]
        
        return events
    
    def _check_triggers(self, tick, agents, world) -> Optional[StoryArc]:
        """检查叙事触发条件"""
        if self.active_arcs:
            return None  # 已有活跃弧时不触发新弧
        
        # 每3-5天检查一次
        if tick % 24 != 12:
            return None
        
        day = tick // 24
        
        # 触发1：资源危机
        total_food = sum(a.state.food for a in agents if a.identity.role.value != "player")
        if total_food < 10 and day > 2:
            participants = [a.identity.id for a in agents if a.identity.role.value in ["forager", "farmer", "merchant"]]
            if len(participants) >= 2:
                self.arc_counter += 1
                return StoryArc(f"arc_{self.arc_counter}", "resource_crisis", participants)
        
        # 触发2：神秘事件（侦察兵相关）
        scouts = [a for a in agents if a.identity.role.value == "scout"]
        if scouts and random.random() < 0.3:
            participants = [scouts[0].identity.id]
            # 找朋友加入
            for other_id, tie in scouts[0].state.social_ties.items():
                if tie > 5:
                    participants.append(other_id)
                    break
            self.arc_counter += 1
            return StoryArc(f"arc_{self.arc_counter}", "mystery", participants)
        
        # 触发3：冲突（关系恶劣的Agent）
        if day > 3:
            for a in agents:
                for other_id, tie in a.state.social_ties.items():
                    if tie < -15 and random.random() < 0.2:
                        self.arc_counter += 1
                        return StoryArc(f"arc_{self.arc_counter}", "conflict", [a.identity.id, other_id])
        
        return None
    
    def get_daily_summary(self, day: int) -> str:
        """生成当日叙事摘要"""
        today_events = [s for s in self.narrative_summary if f"[Day {day}]" in s]
        if today_events:
            return "\\n".join(today_events[-3:])
        return ""
