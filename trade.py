"""
K-town 交易系统 — trade.py
负责市场定义、动态定价、买卖交易
"""
import time
import uuid
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 物品类别枚举
# ============================================================
class ItemCategory(str, Enum):
    """物品分类"""
    FOOD = "food"           # 食物
    MATERIAL = "material"   # 材料
    TOOL = "tool"           # 工具
    MEDICINE = "medicine"   # 药品
    ORE = "ore"             # 矿石
    LUXURY = "luxury"       # 奢侈品


# ============================================================
# 物品定义
# ============================================================
@dataclass
class ItemDefinition:
    """
    物品定义（静态数据）
    
    - id: 唯一标识
    - name: 物品名称
    - category: 物品类别
    - base_price: 基础价格（供需平衡点）
    - weight: 交易权重（影响价格波动幅度）
    - description: 物品描述
    """
    id: str
    name: str
    category: ItemCategory
    base_price: int
    weight: float = 1.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "base_price": self.base_price,
            "description": self.description,
        }


# ============================================================
# 市场条目（每种物品的当前市场状态）
# ============================================================
@dataclass
class MarketEntry:
    """
    市场条目：记录每种物品的当前供需和价格
    
    - item_id: 物品 ID
    - current_price: 当前价格
    - supply: 供应量（正数表示充足）
    - demand: 需求量（正数表示紧缺）
    - traded_volume: 累计交易量（用于趋势计算）
    - last_update: 上次更新时间
    """
    item_id: str
    current_price: int
    supply: int = 0
    demand: int = 0
    traded_volume: int = 0
    last_update: float = field(default_factory=time.time)

    @property
    def price_trend(self) -> float:
        """价格趋势：正数表示涨价，负数表示跌价"""
        if self.supply == 0 and self.demand == 0:
            return 0.0
        return (self.demand - self.supply) / max(1, self.supply + self.demand)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "current_price": self.current_price,
            "supply": self.supply,
            "demand": self.demand,
            "traded_volume": self.traded_volume,
            "price_trend": round(self.price_trend, 3),
        }


# ============================================================
# 交易记录
# ============================================================
@dataclass
class Transaction:
    """单笔交易记录"""
    id: str = field(default_factory=lambda: f"tx_{uuid.uuid4().hex[:8]}")
    buyer: str = ""          # 买方 ID
    seller: str = ""         # 卖方 ID
    item_id: str = ""        # 物品 ID
    quantity: int = 1        # 数量
    unit_price: int = 0      # 单价
    total_price: int = 0     # 总价
    timestamp: float = field(default_factory=time.time)
    is_agent_trade: bool = False  # 是否为 Agent 之间的交易

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "buyer": self.buyer,
            "seller": self.seller,
            "item_id": self.item_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "timestamp": self.timestamp,
            "is_agent_trade": self.is_agent_trade,
        }


# ============================================================
# 玩家/Agent 库存
# ============================================================
class Inventory:
    """
    库存管理：支持 Agent 和玩家
    
    使用字典存储 {item_id: quantity}
    """

    def __init__(self, gold: int = 100):
        self.gold: int = gold
        self.items: Dict[str, int] = {}  # item_id -> quantity

    def add_item(self, item_id: str, quantity: int = 1):
        """添加物品"""
        self.items[item_id] = self.items.get(item_id, 0) + quantity

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """移除物品，成功返回 True"""
        current = self.items.get(item_id, 0)
        if current < quantity:
            return False
        self.items[item_id] = current - quantity
        if self.items[item_id] <= 0:
            del self.items[item_id]
        return True

    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        """检查是否拥有足够物品"""
        return self.items.get(item_id, 0) >= quantity

    def add_gold(self, amount: int):
        """增加金币"""
        self.gold = max(0, self.gold + amount)

    def can_afford(self, amount: int) -> bool:
        """检查是否负担得起"""
        return self.gold >= amount

    def to_dict(self) -> Dict[str, Any]:
        return {"gold": self.gold, "items": dict(self.items)}


# ============================================================
# 交易市场引擎
# ============================================================
class TradeMarket:
    """
    交易市场引擎
    
    核心功能：
    1. 物品定义管理
    2. 动态价格计算（基于供需）
    3. 买卖交易执行
    4. 交易记录存储
    5. Agent 交易行为模拟
    """

    # 价格波动参数
    MAX_PRICE_MULTIPLIER = 2.5   # 最高价格倍数
    MIN_PRICE_MULTIPLIER = 0.4   # 最低价格倍数
    PRICE_ELASTICITY = 0.3       # 价格弹性系数

    def __init__(self):
        self.items: Dict[str, ItemDefinition] = {}
        self.market: Dict[str, MarketEntry] = {}
        self.transactions: List[Transaction] = []
        self.inventories: Dict[str, Inventory] = {}  # entity_id -> Inventory
        self._init_items()

    # --------------------------------------------------------
    # 物品定义初始化
    # --------------------------------------------------------
    def _init_items(self):
        """初始化所有可交易物品"""
        item_defs = [
            # === 食物 ===
            ItemDefinition("bread", "面包", ItemCategory.FOOD, 5, weight=1.0,
                           description="基本的果腹之物"),
            ItemDefinition("apple", "苹果", ItemCategory.FOOD, 3, weight=0.8,
                           description="新鲜水果，补充体力"),
            ItemDefinition("meat", "烤肉", ItemCategory.FOOD, 12, weight=1.2,
                           description="丰盛的肉食"),
            ItemDefinition("fish", "鲜鱼", ItemCategory.FOOD, 8, weight=1.0,
                           description="河边的新鲜渔获"),

            # === 材料 ===
            ItemDefinition("wood", "木材", ItemCategory.MATERIAL, 4, weight=0.7,
                           description="基础建材"),
            ItemDefinition("stone", "石头", ItemCategory.MATERIAL, 3, weight=0.6,
                           description="坚固的石材"),
            ItemDefinition("leather", "皮革", ItemCategory.MATERIAL, 10, weight=1.0,
                           description="制作防具的材料"),
            ItemDefinition("herbs", "草药", ItemCategory.MATERIAL, 7, weight=0.9,
                           description="药用的野生植物"),

            # === 工具 ===
            ItemDefinition("hammer", "铁锤", ItemCategory.TOOL, 25, weight=1.5,
                           description="工匠的基础工具"),
            ItemDefinition("axe", "斧头", ItemCategory.TOOL, 20, weight=1.3,
                           description="伐木必备"),
            ItemDefinition("pickaxe", "镐子", ItemCategory.TOOL, 22, weight=1.4,
                           description="采矿工具"),
            ItemDefinition("fishing_rod", "钓竿", ItemCategory.TOOL, 15, weight=1.0,
                           description="河边垂钓的好帮手"),

            # === 药品 ===
            ItemDefinition("potion_hp", "生命药水", ItemCategory.MEDICINE, 30, weight=2.0,
                           description="恢复生命值"),
            ItemDefinition("potion_energy", "精力药水", ItemCategory.MEDICINE, 25, weight=1.8,
                           description="恢复精力"),
            ItemDefinition("bandage", "绷带", ItemCategory.MEDICINE, 10, weight=1.0,
                           description="止血治伤"),

            # === 矿石 ===
            ItemDefinition("iron_ore", "铁矿石", ItemCategory.ORE, 18, weight=1.2,
                           description="锻造武器的原料"),
            ItemDefinition("copper_ore", "铜矿石", ItemCategory.ORE, 14, weight=1.0,
                           description="常见的金属矿"),
            ItemDefinition("gold_ore", "金矿石", ItemCategory.ORE, 50, weight=2.5,
                           description="贵重的金矿"),

            # === 奢侈品 ===
            ItemDefinition("silk", "丝绸", ItemCategory.LUXURY, 60, weight=2.0,
                           description="华丽的织物"),
            ItemDefinition("jewel", "宝石", ItemCategory.LUXURY, 100, weight=3.0,
                           description="璀璨的珍宝"),
        ]
        for item in item_defs:
            self.items[item.id] = item
            self.market[item.id] = MarketEntry(
                item_id=item.id,
                current_price=item.base_price,
            )

    # --------------------------------------------------------
    # 库存管理
    # --------------------------------------------------------
    def register_entity(self, entity_id: str, gold: int = 100,
                        items: Optional[Dict[str, int]] = None):
        """
        注册交易实体（玩家或 Agent）
        
        - entity_id: 实体 ID
        - gold: 初始金币
        - items: 初始物品字典 {item_id: quantity}
        """
        inv = Inventory(gold=gold)
        if items:
            for item_id, qty in items.items():
                inv.add_item(item_id, qty)
        self.inventories[entity_id] = inv

    def get_inventory(self, entity_id: str) -> Optional[Inventory]:
        """获取指定实体的库存"""
        return self.inventories.get(entity_id)

    # --------------------------------------------------------
    # 动态定价
    # --------------------------------------------------------
    def update_price(self, item_id: str):
        """
        根据供需更新物品价格
        
        算法：
        - 计算供需差 (demand - supply)
        - 应用弹性系数和权重调整波动幅度
        - 限制在 [base * MIN, base * MAX] 范围内
        """
        item = self.items.get(item_id)
        entry = self.market.get(item_id)
        if not item or not entry:
            return

        # 供需差比率
        total = entry.supply + entry.demand
        if total == 0:
            # 无交易时价格缓慢回归基础价
            diff = item.base_price - entry.current_price
            entry.current_price += int(diff * 0.1)
        else:
            # 需求 > 供给 → 涨价，反之跌价
            ratio = (entry.demand - entry.supply) / total
            adjustment = int(
                entry.current_price
                * ratio
                * self.PRICE_ELASTICITY
                * item.weight
            )
            entry.current_price += adjustment

        # 价格边界限制
        min_price = max(1, int(item.base_price * self.MIN_PRICE_MULTIPLIER))
        max_price = int(item.base_price * self.MAX_PRICE_MULTIPLIER)
        entry.current_price = max(min_price, min(max_price, entry.current_price))
        entry.last_update = time.time()

    def adjust_supply(self, item_id: str, amount: int):
        """调整供应量"""
        entry = self.market.get(item_id)
        if entry:
            entry.supply = max(0, entry.supply + amount)
            self.update_price(item_id)

    def adjust_demand(self, item_id: str, amount: int):
        """调整需求量"""
        entry = self.market.get(item_id)
        if entry:
            entry.demand = max(0, entry.demand + amount)
            self.update_price(item_id)

    def get_price(self, item_id: str) -> int:
        """获取物品当前价格"""
        entry = self.market.get(item_id)
        return entry.current_price if entry else 0

    def get_price_display(self, item_id: str) -> Dict[str, Any]:
        """获取价格显示信息（含趋势）"""
        item = self.items.get(item_id)
        entry = self.market.get(item_id)
        if not item or not entry:
            return {}
        trend = entry.price_trend
        return {
            "item_id": item_id,
            "name": item.name,
            "category": item.category.value,
            "current_price": entry.current_price,
            "base_price": item.base_price,
            "trend": "up" if trend > 0.05 else ("down" if trend < -0.05 else "stable"),
            "trend_value": round(trend, 3),
            "description": item.description,
        }

    # --------------------------------------------------------
    # 交易执行
    # --------------------------------------------------------
    def buy(self, buyer_id: str, seller_id: str, item_id: str,
            quantity: int = 1) -> Dict[str, Any]:
        """
        执行买入操作
        
        流程：
        1. 验证买卖双方库存存在
        2. 检查买方金币是否充足
        3. 检查卖方物品是否充足（NPC 默认无限量）
        4. 执行金币和物品转移
        5. 记录交易、更新市场供需
        
        返回交易结果字典
        """
        buyer_inv = self.inventories.get(buyer_id)
        seller_inv = self.inventories.get(seller_id)

        if not buyer_inv:
            return {"success": False, "error": "买方不存在"}

        item = self.items.get(item_id)
        if not item:
            return {"success": False, "error": "物品不存在"}

        # 计算价格
        unit_price = self.get_price(item_id)
        total_price = unit_price * quantity

        # 检查金币
        if not buyer_inv.can_afford(total_price):
            return {
                "success": False,
                "error": "金币不足",
                "required": total_price,
                "available": buyer_inv.gold,
            }

        # 执行交易
        buyer_inv.add_gold(-total_price)
        buyer_inv.add_item(item_id, quantity)

        if seller_inv:
            seller_inv.add_gold(total_price)
            seller_inv.remove_item(item_id, quantity)

        # 记录交易
        tx = Transaction(
            buyer=buyer_id,
            seller=seller_id,
            item_id=item_id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            is_agent_trade=seller_id.startswith("agent_"),
        )
        self.transactions.append(tx)

        # 更新市场：买方增加需求
        self.adjust_demand(item_id, quantity)

        return {
            "success": True,
            "transaction_id": tx.id,
            "item": item.name,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "buyer_gold_remaining": buyer_inv.gold,
        }

    def sell(self, seller_id: str, buyer_id: str, item_id: str,
             quantity: int = 1) -> Dict[str, Any]:
        """
        执行卖出操作
        
        与 buy 方向相反：卖方减少物品获得金币，买方（如市场）减少金币获得物品
        """
        seller_inv = self.inventories.get(seller_id)
        buyer_inv = self.inventories.get(buyer_id)

        if not seller_inv:
            return {"success": False, "error": "卖方不存在"}

        if not seller_inv.has_item(item_id, quantity):
            return {
                "success": False,
                "error": "物品不足",
                "required": quantity,
                "available": seller_inv.items.get(item_id, 0),
            }

        item = self.items.get(item_id)
        if not item:
            return {"success": False, "error": "物品不存在"}

        unit_price = self.get_price(item_id)
        total_price = unit_price * quantity

        # 买方（市场/NPC）支付能力检查
        if buyer_inv and not buyer_inv.can_afford(total_price):
            return {"success": False, "error": "买方金币不足"}

        # 执行交易
        seller_inv.remove_item(item_id, quantity)
        seller_inv.add_gold(total_price)

        if buyer_inv:
            buyer_inv.add_gold(-total_price)
            buyer_inv.add_item(item_id, quantity)

        # 记录
        tx = Transaction(
            buyer=buyer_id,
            seller=seller_id,
            item_id=item_id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            is_agent_trade=buyer_id.startswith("agent_"),
        )
        self.transactions.append(tx)

        # 市场：卖方增加供应
        self.adjust_supply(item_id, quantity)

        return {
            "success": True,
            "transaction_id": tx.id,
            "item": item.name,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "seller_gold_remaining": seller_inv.gold,
        }

    # --------------------------------------------------------
    # Agent 自动交易行为
    # --------------------------------------------------------
    def agent_auto_trade(self, agent_id: str) -> Optional[Transaction]:
        """
        Agent 自动交易逻辑（每 tick 调用）
        
        决策：
        1. 根据角色偏好选择物品
        2. 如果持有量 > 阈值，卖出多余
        3. 如果缺少必需品，买入补充
        
        返回执行的交易记录，或 None
        """
        inv = self.inventories.get(agent_id)
        if not inv:
            return None

        # Agent 角色购买偏好
        preferences = {
            "blacksmith": ["iron_ore", "copper_ore", "hammer"],
            "forager": ["herbs", "wood", "axe"],
            "healer": ["herbs", "bandage", "potion_hp"],
            "miner": ["pickaxe", "iron_ore", "gold_ore"],
            "farmer": ["bread", "fish", "meat"],
            "merchant": ["silk", "jewel", "leather"],
        }

        # 提取角色名
        role = agent_id.replace("agent_", "") if agent_id.startswith("agent_") else "default"
        preferred_items = preferences.get(role, ["bread", "wood"])

        # 随机选择一个偏好物品进行交易
        item_id = random.choice(preferred_items)
        action = random.choice(["buy", "sell"])

        if action == "buy" and inv.gold > self.get_price(item_id) * 2:
            result = self.buy(agent_id, "market", item_id, 1)
            if result.get("success"):
                return self.transactions[-1]
        elif action == "sell" and inv.has_item(item_id, 2):
            result = self.sell(agent_id, "market", item_id, 1)
            if result.get("success"):
                return self.transactions[-1]

        return None

    # --------------------------------------------------------
    # 查询接口
    # --------------------------------------------------------
    def get_all_items(self) -> List[Dict]:
        """获取所有物品及当前价格"""
        result = []
        for item_id in self.items:
            result.append(self.get_price_display(item_id))
        return result

    def get_items_by_category(self, category: ItemCategory) -> List[Dict]:
        """按类别获取物品"""
        result = []
        for item_id, item in self.items.items():
            if item.category == category:
                result.append(self.get_price_display(item_id))
        return result

    def get_market_summary(self) -> Dict[str, Any]:
        """获取市场总览"""
        return {
            "items": self.get_all_items(),
            "recent_transactions": [
                tx.to_dict() for tx in self.transactions[-10:]
            ],
            "total_transactions": len(self.transactions),
        }

    def get_transaction_history(self, entity_id: str = "",
                                limit: int = 20) -> List[Dict]:
        """获取交易历史（可按实体过滤）"""
        txs = self.transactions
        if entity_id:
            txs = [
                tx for tx in txs
                if tx.buyer == entity_id or tx.seller == entity_id
            ]
        return [tx.to_dict() for tx in txs[-limit:]]

    def to_dict(self) -> Dict[str, Any]:
        """序列化市场状态"""
        return {
            "items": self.get_all_items(),
            "inventories": {
                eid: inv.to_dict() for eid, inv in self.inventories.items()
            },
            "total_transactions": len(self.transactions),
        }