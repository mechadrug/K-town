"""K-town 每日目标薄层。

设计依据：docs/product/gameplay-design-v3.md §5
- 每天生成 3 个目标，全部来自"真实可执行动作"池
- 进度挂在动作执行上实时追踪（tick._handle_action 挂钩）
- 完成后立即发放金币奖励，并写入日报
- 不搞技能树/声望/排行榜 —— 薄层，不喧宾夺主
"""

import random
from typing import Dict, List, Any, Optional


# 目标模板池：type 与 tick._handle_action 的动作挂钩
GOAL_POOL: List[Dict[str, Any]] = [
    {"type": "work", "target": 2, "desc": "工作 2 次", "reward": 15, "icon": "🛠️"},
    {"type": "talk", "target": 2, "desc": "与 2 位居民交谈", "reward": 15, "icon": "💬"},
    {"type": "move", "target": 3, "desc": "走访 3 个不同地点", "reward": 10, "icon": "🚶"},
    {"type": "investigate", "target": 1, "desc": "调查 1 次周围环境", "reward": 20, "icon": "🔍"},
    {"type": "gather", "target": 2, "desc": "采集或劳作 2 次", "reward": 15, "icon": "🌿"},
    {"type": "earn", "target": 20, "desc": "赚取 20 金币", "reward": 10, "icon": "🪙"},
    {"type": "knowledge", "target": 1, "desc": "传播 1 条知识", "reward": 20, "icon": "📚"},
    {"type": "rest", "target": 1, "desc": "休息恢复 1 次", "reward": 5, "icon": "🛏️"},
]

# 动作类型 → 目标类型
_ACTION_TO_TYPE: Dict[str, str] = {
    "work": "work", "craft_tool": "work", "craft_furniture": "work",
    "gather_food": "gather", "gather_material": "gather",
    "talk": "talk", "move": "move", "investigate": "investigate",
    "rest": "rest", "sleep": "rest", "add_claim": "knowledge",
}


class DailyGoal:
    def __init__(self, goal_type: str, desc: str, target: int, reward: int, icon: str):
        self.type = goal_type
        self.desc = desc
        self.target = target
        self.reward = reward
        self.icon = icon
        self.progress = 0
        self.completed = False

    def to_dict(self) -> Dict[str, Any]:
        pct = round(self.progress / self.target * 100) if self.target else 0
        return {
            "id": f"goal_{self.type}",
            "title": self.desc,
            "description": self.desc,
            "category": "daily",
            "status": "completed" if self.completed else "active",
            "progress": self.progress,
            "target": self.target,
            "progress_pct": min(100, pct),
            "reward_gold": self.reward,
            "reward_text": f"{self.reward} 金币",
            "icon": self.icon,
        }


class QuestEngine:
    def __init__(self):
        self.daily_goals: List[DailyGoal] = []
        self.completed_history: List[str] = []  # 历史完成记录（用于 total_completed）
        self.current_day = 1

    def generate_daily_goals(self, day: int, count: int = 3) -> None:
        """新的一天，从动作池随机生成 count 个目标"""
        self.current_day = day
        self.daily_goals = []
        pool = GOAL_POOL[:]
        random.shuffle(pool)
        for g in pool[:count]:
            self.daily_goals.append(DailyGoal(g["type"], g["desc"], g["target"], g["reward"], g["icon"]))

    def update_progress(self, player, action_type: str = "", gold_earned: int = 0) -> int:
        """根据玩家一次动作更新目标进度。返回本次发放的奖励金币（0 表示无）。"""
        goal_type = _ACTION_TO_TYPE.get(action_type, "")
        rewards = 0
        for g in self.daily_goals:
            if g.completed:
                continue
            if goal_type == g.type:
                if g.type == "earn":
                    g.progress += max(0, gold_earned)
                else:
                    g.progress += 1
            if g.progress >= g.target:
                g.completed = True
                rewards += g.reward
                self.completed_history.append(f"第{self.current_day}天 · {g.desc}")
        if rewards > 0:
            player.state.gold += rewards
        return rewards

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_quests": [g.to_dict() for g in self.daily_goals if not g.completed],
            "completed_quests": [g.to_dict() for g in self.daily_goals if g.completed],
            "achievements": [],
            "total_completed": len(self.completed_history),
            "total_quests": len(self.daily_goals),
        }
