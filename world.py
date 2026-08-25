from models import WorldState
from typing import Dict
import random

class World:
    def __init__(self):
        self.state = WorldState()
        self.locations = {
            "square": {"id": "square", "name": "广场", "type": "square", "agents": [], "description": "小镇的公共集会场所，用于交流、交易和公告发布"},
            "workshop": {"id": "workshop", "name": "工坊", "type": "workshop", "agents": [], "description": "制作工具、加工材料、技术研发的场所"},
            "wilderness": {"id": "wilderness", "name": "荒野", "type": "wilderness", "agents": [], "description": "采集资源、探索未知、发现新知识的区域"},
            "school": {"id": "school", "name": "学校", "type": "school", "agents": [], "description": "教学育人、治病救人的场所"},
            "mine": {"id": "mine", "name": "矿洞", "type": "mine", "agents": [], "description": "采集矿石、挖掘珍贵矿物的地下洞穴"},
        }
        self._weathers = ["clear", "cloudy", "rainy", "snowy", "windy"]
        self._weather_names = {
            "clear": "晴朗", "cloudy": "多云", "rainy": "下雨", "snowy": "下雪", "windy": "大风"
        }
        # 资源分布
        self.resources = {
            "square": {"food": 10, "materials": 5, "tools": 3},
            "workshop": {"food": 0, "materials": 20, "tools": 10},
            "wilderness": {"food": 50, "materials": 30, "tools": 0},
            "school": {"food": 5, "materials": 10, "tools": 2},
            "mine": {"food": 0, "materials": 50, "tools": 0}
        }
        # 价格系统：基础价格和当前价格
        self.base_prices = {"food": 5, "materials": 3, "tools": 15, "medicine": 10, "ore": 12}
        self.prices = {res: price for res, price in self.base_prices.items()}
        self.price_history = {res: [price] for res, price in self.base_prices.items()}
        # 供需追踪
        self.demand = {"food": 0, "materials": 0, "tools": 0, "medicine": 0, "ore": 0}
        self.supply = {"food": 0, "materials": 0, "tools": 0, "medicine": 0, "ore": 0}

    def advance(self, tick: int):
        self.state.tick = tick
        # 每天早上6点更新天气和价格（一天 20 小时）
        if tick % 20 == 6:
            # 首周压力线：第一天收到预报，第三天必然迎来暴雨；其余天气仍可变。
            self._change_weather(tick)
            self._update_prices()

    def _change_weather(self, tick=None):
        if tick is not None:
            day = tick // 20 + 1
            if self.state.rain_forecast_day and day >= self.state.rain_forecast_day:
                self.state.weather = "rainy"
                return
        weights = [0.5, 0.2, 0.15, 0.1, 0.05]
        self.state.weather = random.choices(self._weathers, weights=weights, k=1)[0]

    def set_workshop_roof(self, stage: int, day: int = 0) -> int:
        """设置工坊屋顶阶段，避免请求/前端各自维护一份状态。"""
        self.state.workshop_roof_stage = max(0, min(2, int(stage)))
        if day:
            self.state.workshop_roof_last_change_day = day
        return self.state.workshop_roof_stage

    def workshop_roof_status(self) -> dict:
        statuses = {
            0: {"id": "leaking", "label": "漏雨", "description": "西侧屋檐还在滴水，炉台不能久留。"},
            1: {"id": "temporary_cover", "label": "临时遮雨", "description": "旧布料挡住了大半雨水，但雨声和滴漏仍在。"},
            2: {"id": "repaired", "label": "正式修好", "description": "支架稳了，夜里工坊会亮起稳定的窗光。"},
        }
        return {**statuses.get(self.state.workshop_roof_stage, statuses[0]),
                "stage": self.state.workshop_roof_stage}

    def _update_prices(self):
        """根据供需关系更新价格"""
        for resource in self.prices:
            base = self.base_prices[resource]
            demand = self.demand.get(resource, 0)
            supply = self.supply.get(resource, 0)
            
            # 供需比→价格变动
            if supply > 0:
                ratio = demand / supply
            else:
                ratio = demand * 2  # 无供应时价格大幅上涨
            
            # 价格变动幅度（限制在基础价格的50%-200%）
            change_factor = max(0.5, min(2.0, ratio))
            new_price = max(1, round(base * change_factor))
            self.prices[resource] = new_price
            
            # 记录价格历史
            self.price_history[resource].append(new_price)
            if len(self.price_history[resource]) > 30:
                self.price_history[resource] = self.price_history[resource][-30:]
            
            # 重置供需计数
            self.demand[resource] = 0
            self.supply[resource] = 0

    def get_price(self, resource: str) -> int:
        """获取某资源的当前价格"""
        return self.prices.get(resource, self.base_prices.get(resource, 5))

    def record_demand(self, resource: str, amount: int = 1):
        """记录需求"""
        self.demand[resource] = self.demand.get(resource, 0) + amount

    def record_supply(self, resource: str, amount: int = 1):
        """记录供给"""
        self.supply[resource] = self.supply.get(resource, 0) + amount

    def get_weather_name(self, weather: str = None) -> str:
        if not weather:
            weather = self.state.weather
        return self._weather_names.get(weather, weather)

    def add_agent_to_location(self, agent_id, location):
        if location in self.locations and agent_id not in self.locations[location]["agents"]:
            self.locations[location]["agents"].append(agent_id)

    def remove_agent_from_location(self, agent_id, location):
        if location in self.locations and agent_id in self.locations[location]["agents"]:
            self.locations[location]["agents"].remove(agent_id)




    def to_dict(self):
        return {
            "tick": self.state.tick,
            "weather": self.state.weather,
            "weather_name": self.get_weather_name(),
            "locations": {k: {**v, "agents": list(v["agents"])} for k, v in self.locations.items()},
            "resources": self.resources,
            "prices": self.prices,
            "price_history": {k: v[-7:] for k, v in self.price_history.items()}
            ,"workshop_roof": self.workshop_roof_status()
            ,"rain_forecast": {
                "day": self.state.rain_forecast_day,
                "announced": self.state.rain_forecast_announced,
                "weather": "rainy",
            }
            ,"mine_rumor": {
                "status": self.state.mine_rumor_status,
                "confidence": self.state.mine_rumor_confidence,
            }
            ,"lantern_fair_preparedness": self.state.lantern_fair_preparedness,
            "campaign_markers": dict(self.state.campaign_markers),
        }
