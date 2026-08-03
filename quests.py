"""Quest and Achievement system for K-town."""
import time
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Quest:
    id: str
    title: str
    description: str
    category: str
    status: str = "active"
    progress: int = 0
    target: int = 1
    reward_gold: int = 0
    reward_text: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "progress": self.progress,
            "target": self.target,
            "reward_gold": self.reward_gold,
            "reward_text": self.reward_text,
            "progress_pct": min(100, round(self.progress / max(1, self.target) * 100))
        }


@dataclass
class Achievement:
    id: str
    title: str
    description: str
    icon: str
    unlocked: bool = False
    unlocked_at: Optional[float] = None

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "unlocked": self.unlocked
        }


class QuestEngine:
    def __init__(self):
        self.quests: Dict[str, Quest] = {}
        self.achievements: Dict[str, Achievement] = {}
        self._init_quests()
        self._init_achievements()

    def _init_quests(self):
        tutorial_quests = [
            Quest("q_hello", "Meet Grandmother Mae", "Say hello to Elder Mae at the square", "tutorial", target=1, reward_gold=10, reward_text="10 gold and Mae's blessing"),
            Quest("q_explore", "Town Wanderer", "Visit 3 different locations", "tutorial", target=3, reward_gold=15, reward_text="15 gold for exploring"),
            Quest("q_first_work", "Self-reliant", "Complete 3 work actions", "tutorial", target=3, reward_gold=20, reward_text="20 gold for hard work"),
            Quest("q_social", "Make Friends", "Talk to 3 different residents", "tutorial", target=3, reward_gold=15, reward_text="15 gold for socializing"),
            Quest("q_knowledge", "Knowledge Keeper", "Create 2 knowledge claims", "tutorial", target=2, reward_gold=25, reward_text="25 gold for sharing knowledge"),
        ]
        main_quests = [
            Quest("q_economy", "Economic Pillar", "Earn 100 gold total", "main", target=100, reward_gold=50, reward_text="Economic contributor"),
            Quest("q_well_connected", "Social Butterfly", "Befriend 5 residents", "main", target=5, reward_gold=50, reward_text="Everyone considers you a friend"),
            Quest("q_explorer", "Pioneer Explorer", "Explore the wilderness 5 times", "main", target=5, reward_gold=40, reward_text="Discover the secrets around town"),
            Quest("q_master", "Town Leader", "Complete all main quests", "main", target=4, reward_gold=200, reward_text="Became the town leader"),
        ]
        daily_quests = [
            Quest("q_daily_work", "Hardworking Day", "Complete 5 work actions today", "daily", target=5, reward_gold=10, reward_text="Hard work pays off"),
            Quest("q_daily_social", "Social Day", "Talk to 2 residents today", "daily", target=2, reward_gold=8, reward_text="Building connections"),
            Quest("q_daily_explore", "Curiosity", "Visit all locations today", "daily", target=5, reward_gold=12, reward_text="Well-traveled"),
        ]
        for q in tutorial_quests + main_quests + daily_quests:
            self.quests[q.id] = q

    def _init_achievements(self):
        achievements = [
            Achievement("a_first_step", "First Step", "Complete your first tutorial quest", "flag"),
            Achievement("a_worker", "Worker", "Work 20 times total", "gear"),
            Achievement("a_social_butterfly", "Social Butterfly", "Talk to all residents", "smile"),
            Achievement("a_rich", "Small Fortune", "Earn 500 gold total", "coins"),
            Achievement("a_scholar", "Scholar", "Create 10 knowledge claims", "book"),
            Achievement("a_explorer", "Explorer", "Explore wilderness 10 times", "compass"),
            Achievement("a_survivor", "Survivor", "Survive a disaster event", "shield"),
            Achievement("a_friend", "Good Friend", "Reach max friendship with any resident", "heart"),
        ]
        for a in achievements:
            self.achievements[a.id] = a

    def update_progress(self, quest_id: str, amount: int = 1):
        q = self.quests.get(quest_id)
        if not q or q.status != "active":
            return
        q.progress = min(q.target, q.progress + amount)
        if q.progress >= q.target:
            q.status = "completed"
            q.completed_at = time.time()

    def check_event(self, event_type: str, data: Dict[str, Any] = None):
        data = data or {}
        if event_type == "player_move":
            visited = data.get("visited_locations", [])
            q = self.quests.get("q_explore")
            if q and q.status == "active":
                q.progress = min(q.target, len(visited))
                if q.progress >= q.target:
                    q.status = "completed"
                    q.completed_at = time.time()
        elif event_type == "player_work":
            self.update_progress("q_first_work")
            self.update_progress("q_daily_work")
        elif event_type == "player_talk":
            talked = data.get("talked_agents", [])
            q = self.quests.get("q_social")
            if q and q.status == "active":
                q.progress = min(q.target, len(talked))
                if q.progress >= q.target:
                    q.status = "completed"
                    q.completed_at = time.time()
            self.update_progress("q_daily_social")
        elif event_type == "player_claim":
            self.update_progress("q_knowledge")
        elif event_type == "player_gold":
            total = data.get("total_gold", 0)
            q = self.quests.get("q_economy")
            if q and q.status == "active":
                q.progress = min(q.target, total)
                if q.progress >= q.target:
                    q.status = "completed"
                    q.completed_at = time.time()
        elif event_type == "player_explore":
            self.update_progress("q_explorer")
            self.update_progress("q_daily_explore")

    def get_active_quests(self) -> List[Dict]:
        return [q.to_dict() for q in self.quests.values() if q.status == "active"]

    def get_completed_quests(self) -> List[Dict]:
        return [q.to_dict() for q in self.quests.values() if q.status == "completed"]

    def get_all_achievements(self) -> List[Dict]:
        return [a.to_dict() for a in self.achievements.values()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_quests": self.get_active_quests(),
            "completed_quests": self.get_completed_quests(),
            "achievements": self.get_all_achievements(),
            "total_completed": sum(1 for q in self.quests.values() if q.status == "completed"),
            "total_quests": len(self.quests)
        }

    def reset(self):
        self.quests.clear()
        self.achievements.clear()
        self._init_quests()
        self._init_achievements()
