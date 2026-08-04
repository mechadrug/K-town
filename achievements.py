"""
K-town 成就系统 — achievements.py
负责成就定义、条件检查、奖励发放
"""
import time
import uuid
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 成就类别枚举
# ============================================================
class AchievementCategory(str, Enum):
    """成就分类"""
    SOCIAL = "social"       # 社交类
    ECONOMY = "economy"     # 经济类
    KNOWLEDGE = "knowledge"  # 知识类
    EXPLORATION = "exploration"  # 探索类
    SPECIAL = "special"     # 特殊/隐藏成就


# ============================================================
# 成就数据模型
# ============================================================
@dataclass
class Achievement:
    """
    成就定义
    
    每个成就包含：
    - id: 唯一标识
    - title: 成就名称
    - description: 成就描述
    - icon: 图标（emoji 或 CSS class）
    - category: 成就类别
    - condition_func: 条件检查函数名（字符串，由 AchievementEngine 分发）
    - condition_target: 达成条件的目标数值
    - reward_gold: 奖励金币
    - reward_text: 奖励描述文本
    - hidden: 是否为隐藏成就
    """
    id: str
    title: str
    description: str
    icon: str
    category: AchievementCategory
    condition_func: str              # 条件函数名
    condition_target: int = 1        # 目标数值
    reward_gold: int = 0
    reward_text: str = ""
    hidden: bool = False

    # 运行时状态
    unlocked: bool = False
    unlocked_at: Optional[float] = None
    progress: int = 0                # 当前进度

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（隐藏未解锁的隐藏成就详情）"""
        base = {
            "id": self.id,
            "title": self.title if not self.hidden or self.unlocked else "???",
            "description": self.description if not self.hidden or self.unlocked else "隐藏成就",
            "icon": self.icon if not self.hidden or self.unlocked else "lock",
            "category": self.category.value,
            "unlocked": self.unlocked,
            "reward_gold": self.reward_gold,
            "reward_text": self.reward_text,
            "progress": self.progress,
            "target": self.condition_target,
            "progress_pct": min(100, round(self.progress / max(1, self.condition_target) * 100)),
        }
        if self.unlocked:
            base["unlocked_at"] = self.unlocked_at
        return base


# ============================================================
# 成就引擎
# ============================================================
class AchievementEngine:
    """
    成就引擎：管理所有成就定义、检查进度、发放奖励
    
    使用方式：
        engine = AchievementEngine()
        engine.register_player_state(player_state_dict)
        new_unlocks = engine.check_all()
    """

    def __init__(self):
        self.achievements: Dict[str, Achievement] = {}
        self.player_state: Dict[str, Any] = {}
        self._unlock_callbacks: List[Callable] = []
        self._init_achievements()

    # --------------------------------------------------------
    # 成就定义初始化
    # --------------------------------------------------------
    def _init_achievements(self):
        """初始化所有成就定义"""
        all_achievements = [
            # === 社交成就 ===
            Achievement(
                id="ach_friend_first",
                title="初识之友",
                description="交第一位朋友（友好度 > 50）",
                icon="handshake",
                category=AchievementCategory.SOCIAL,
                condition_func="check_friend_count",
                condition_target=1,
                reward_gold=10,
                reward_text="社交奖励 +10金币",
            ),
            Achievement(
                id="ach_friend_many",
                title="八面玲珑",
                description="同时拥有 5 个朋友",
                icon="people",
                category=AchievementCategory.SOCIAL,
                condition_func="check_friend_count",
                condition_target=5,
                reward_gold=50,
                reward_text="社交达人 +50金币",
            ),
            Achievement(
                id="ach_friend_all",
                title="民心所向",
                description="与所有 10 位居民成为朋友",
                icon="crown",
                category=AchievementCategory.SOCIAL,
                condition_func="check_friend_count",
                condition_target=10,
                reward_gold=200,
                reward_text="小镇传奇 +200金币",
            ),
            Achievement(
                id="ach_best_friend",
                title="莫逆之交",
                description="与任意居民达到最高友好度（> 90）",
                icon="heart",
                category=AchievementCategory.SOCIAL,
                condition_func="check_max_friendship",
                condition_target=90,
                reward_gold=80,
                reward_text="深厚友谊 +80金币",
            ),

            # === 经济成就 ===
            Achievement(
                id="ach_gold_100",
                title="小有积蓄",
                description="累计获得 100 金币",
                icon="coins",
                category=AchievementCategory.ECONOMY,
                condition_func="check_total_gold_earned",
                condition_target=100,
                reward_gold=20,
                reward_text="勤俭持家 +20金币",
            ),
            Achievement(
                id="ach_gold_500",
                title="富甲一方",
                description="累计获得 500 金币",
                icon="gem",
                category=AchievementCategory.ECONOMY,
                condition_func="check_total_gold_earned",
                condition_target=500,
                reward_gold=100,
                reward_text="商业巨贾 +100金币",
            ),
            Achievement(
                id="ach_gold_2000",
                title="点石成金",
                description="累计获得 2000 金币",
                icon="trophy",
                category=AchievementCategory.ECONOMY,
                condition_func="check_total_gold_earned",
                condition_target=2000,
                reward_gold=500,
                reward_text="财富传说 +500金币",
            ),
            Achievement(
                id="ach_first_trade",
                title="第一桶金",
                description="完成第一笔交易",
                icon="swap_horiz",
                category=AchievementCategory.ECONOMY,
                condition_func="check_trade_count",
                condition_target=1,
                reward_gold=5,
                reward_text="商业启蒙 +5金币",
            ),

            # === 知识成就 ===
            Achievement(
                id="ach_knowledge_5",
                title="初窥门径",
                description="收集 5 条知识",
                icon="menu_book",
                category=AchievementCategory.KNOWLEDGE,
                condition_func="check_knowledge_count",
                condition_target=5,
                reward_gold=15,
                reward_text="学海无涯 +15金币",
            ),
            Achievement(
                id="ach_knowledge_20",
                title="博闻强识",
                description="收集 20 条知识",
                icon="auto_stories",
                category=AchievementCategory.KNOWLEDGE,
                condition_func="check_knowledge_count",
                condition_target=20,
                reward_gold=60,
                reward_text="知识宝库 +60金币",
            ),
            Achievement(
                id="ach_knowledge_50",
                title="小镇智者",
                description="收集 50 条知识",
                icon="school",
                category=AchievementCategory.KNOWLEDGE,
                condition_func="check_knowledge_count",
                condition_target=50,
                reward_gold=150,
                reward_text="智者之巅 +150金币",
            ),

            # === 探索成就 ===
            Achievement(
                id="ach_visit_3",
                title="闲庭信步",
                description="到访 3 个不同地点",
                icon="directions_walk",
                category=AchievementCategory.EXPLORATION,
                condition_func="check_unique_locations",
                condition_target=3,
                reward_gold=15,
                reward_text="探索者 +15金币",
            ),
            Achievement(
                id="ach_visit_all",
                title="走遍小镇",
                description="到访所有地点",
                icon="map",
                category=AchievementCategory.EXPLORATION,
                condition_func="check_unique_locations",
                condition_target=5,
                reward_gold=60,
                reward_text="无所不知 +60金币",
            ),
            Achievement(
                id="ach_wilderness_10",
                title="荒野探险家",
                description="探索荒野 10 次",
                icon="terrain",
                category=AchievementCategory.EXPLORATION,
                condition_func="check_wilderness_count",
                condition_target=10,
                reward_gold=40,
                reward_text="探险精神 +40金币",
            ),

            # === 特殊成就 ===
            Achievement(
                id="ach_survive_disaster",
                title="劫后余生",
                description="在灾难事件中幸存",
                icon="shield",
                category=AchievementCategory.SPECIAL,
                condition_func="check_survived_disaster",
                condition_target=1,
                reward_gold=100,
                reward_text="生存大师 +100金币",
            ),
            Achievement(
                id="ach_first_day",
                title="新的开始",
                description="在小镇度过第一天",
                icon="wb_sunny",
                category=AchievementCategory.SPECIAL,
                condition_func="check_days_survived",
                condition_target=1,
                reward_gold=10,
                reward_text="开张大吉 +10金币",
            ),
            Achievement(
                id="ach_week_veteran",
                title="一周老居民",
                description="在小镇度过 7 天",
                icon="calendar_today",
                category=AchievementCategory.SPECIAL,
                condition_func="check_days_survived",
                condition_target=7,
                reward_gold=100,
                reward_text="老住户 +100金币",
                hidden=True,  # 隐藏成就
            ),
            Achievement(
                id="ach_quest_master",
                title="任务大师",
                description="完成 10 个任务",
                icon="assignment_turned_in",
                category=AchievementCategory.SPECIAL,
                condition_func="check_quests_completed",
                condition_target=10,
                reward_gold=120,
                reward_text="任务专家 +120金币",
            ),
        ]
        for a in all_achievements:
            self.achievements[a.id] = a

    # --------------------------------------------------------
    # 玩家状态注册
    # --------------------------------------------------------
    def register_player_state(self, state: Dict[str, Any]):
        """
        注册/更新玩家状态数据，用于成就条件判断
        
        state 字典应包含以下字段：
        - friend_count: int          朋友数量
        - max_friendship: float      最高友好度
        - total_gold_earned: int    累计获得金币
        - trade_count: int          交易次数
        - knowledge_count: int      知识条数
        - visited_locations: set    已访问地点集合
        - wilderness_count: int     荒野探索次数
        - survived_disaster: bool   是否从灾难中幸存
        - days_survived: int        存活天数
        - quests_completed: int     完成任务数
        """
        self.player_state.update(state)

    def on_unlock(self, callback: Callable):
        """注册成就解锁回调"""
        self._unlock_callbacks.append(callback)

    # --------------------------------------------------------
    # 条件检查函数
    # --------------------------------------------------------
    def check_friend_count(self) -> int:
        """返回当前朋友数量"""
        return self.player_state.get("friend_count", 0)

    def check_max_friendship(self) -> float:
        """返回最高友好度"""
        return self.player_state.get("max_friendship", 0.0)

    def check_total_gold_earned(self) -> int:
        """返回累计获得金币"""
        return self.player_state.get("total_gold_earned", 0)

    def check_trade_count(self) -> int:
        """返回交易次数"""
        return self.player_state.get("trade_count", 0)

    def check_knowledge_count(self) -> int:
        """返回知识条数"""
        return self.player_state.get("knowledge_count", 0)

    def check_unique_locations(self) -> int:
        """返回已访问的不同地点数量"""
        visited = self.player_state.get("visited_locations", set())
        return len(visited)

    def check_wilderness_count(self) -> int:
        """返回荒野探索次数"""
        return self.player_state.get("wilderness_count", 0)

    def check_survived_disaster(self) -> int:
        """返回是否从灾难中幸存（0/1）"""
        return 1 if self.player_state.get("survived_disaster", False) else 0

    def check_days_survived(self) -> int:
        """返回存活天数"""
        return self.player_state.get("days_survived", 0)

    def check_quests_completed(self) -> int:
        """返回完成任务数"""
        return self.player_state.get("quests_completed", 0)

    # --------------------------------------------------------
    # 核心逻辑：检查所有成就
    # --------------------------------------------------------
    def check_all(self) -> List[Achievement]:
        """
        检查所有成就条件，返回本次新解锁的成就列表
        
        流程：
        1. 遍历所有未解锁成就
        2. 调用对应条件函数获取当前值
        3. 更新进度
        4. 达到目标则解锁并发放奖励
        """
        newly_unlocked: List[Achievement] = []
        for ach in self.achievements.values():
            if ach.unlocked:
                continue
            # 获取条件函数
            condition_fn = getattr(self, ach.condition_func, None)
            if condition_fn is None:
                continue
            # 获取当前进度值
            current_value = condition_fn()
            # 更新进度
            ach.progress = current_value
            # 检查是否达成
            if current_value >= ach.condition_target:
                self._unlock(ach)
                newly_unlocked.append(ach)
        return newly_unlocked

    def _unlock(self, ach: Achievement):
        """解锁单个成就并触发回调"""
        ach.unlocked = True
        ach.unlocked_at = time.time()
        # 触发回调（如通知、奖励发放）
        for cb in self._unlock_callbacks:
            try:
                cb(ach)
            except Exception as e:
                print(f"[Achievement] 回调执行失败: {e}")

    # --------------------------------------------------------
    # 奖励发放
    # --------------------------------------------------------
    def grant_reward(self, ach: Achievement) -> Dict[str, Any]:
        """
        发放成就奖励
        
        返回奖励详情字典，调用方负责实际应用奖励到玩家账户
        """
        return {
            "achievement_id": ach.id,
            "gold": ach.reward_gold,
            "text": ach.reward_text,
            "unlocked_at": ach.unlocked_at,
        }

    # --------------------------------------------------------
    # 查询接口
    # --------------------------------------------------------
    def get_all(self) -> List[Dict]:
        """获取所有成就（序列化）"""
        return [a.to_dict() for a in self.achievements.values()]

    def get_unlocked(self) -> List[Dict]:
        """获取已解锁成就"""
        return [a.to_dict() for a in self.achievements.values() if a.unlocked]

    def get_locked(self) -> List[Dict]:
        """获取未解锁成就（含进度）"""
        return [a.to_dict() for a in self.achievements.values() if not a.unlocked]

    def get_by_category(self, category: AchievementCategory) -> List[Dict]:
        """按类别获取成就"""
        return [
            a.to_dict()
            for a in self.achievements.values()
            if a.category == category
        ]

    def get_progress_summary(self) -> Dict[str, Any]:
        """获取成就总览统计"""
        total = len(self.achievements)
        unlocked = sum(1 for a in self.achievements.values() if a.unlocked)
        return {
            "total": total,
            "unlocked": unlocked,
            "locked": total - unlocked,
            "completion_pct": round(unlocked / max(1, total) * 100, 1),
            "total_gold_earned": sum(
                a.reward_gold for a in self.achievements.values() if a.unlocked
            ),
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化整个引擎状态"""
        return {
            "achievements": self.get_all(),
            "summary": self.get_progress_summary(),
        }