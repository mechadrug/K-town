from models import WorldState
from typing import Dict

class World:
    def __init__(self):
        self.state = WorldState()
        self.locations = {
            "square": {"id": "square", "name": "广场", "type": "square", "agents": [], "description": "小镇的公共集会场所，用于交流、交易和公告发布"},
            "workshop": {"id": "workshop", "name": "工坊", "type": "workshop", "agents": [], "description": "制作工具、加工材料、技术研发的场所"},
            "wilderness": {"id": "wilderness", "name": "荒野", "type": "wilderness", "agents": [], "description": "采集资源、探索未知、发现新知识的区域"},
        }
        self.state.locations = self.locations
        self._weathers = ["clear", "cloudy", "rainy", "snowy", "windy"]
        self._weather_names = {
            "clear": "晴朗",
            "cloudy": "多云",
            "rainy": "下雨",
            "snowy": "下雪",
            "windy": "大风"
        }
        # 资源分布
        self.resources = {
            "square": {"food": 10, "materials": 5},
            "workshop": {"food": 0, "materials": 20},
            "wilderness": {"food": 50, "materials": 30}
        }

    def advance(self, tick: int):
        self.state.tick = tick
        # 每天早上6点更新天气
        if tick % 24 == 6:
            self._change_weather()

    def _change_weather(self):
        # 随机选择天气，晴朗概率更高
        import random
        weights = [0.5, 0.2, 0.15, 0.1, 0.05]
        self.state.weather = random.choices(self._weathers, weights=weights, k=1)[0]

    def get_weather_name(self, weather: str = None) -> str:
        """获取天气中文名"""
        if not weather:
            weather = self.state.weather
        return self._weather_names.get(weather, weather)

    def add_agent_to_location(self, agent_id, location):
        if location in self.locations and agent_id not in self.locations[location]["agents"]:
            self.locations[location]["agents"].append(agent_id)

    def remove_agent_from_location(self, agent_id, location):
        if location in self.locations and agent_id in self.locations[location]["agents"]:
            self.locations[location]["agents"].remove(agent_id)

    def get_resource(self, location: str, resource_type: str) -> int:
        """获取某个地点的资源数量"""
        return self.resources.get(location, {}).get(resource_type, 0)

    def consume_resource(self, location: str, resource_type: str, amount: int = 1) -> bool:
        """消耗资源，成功返回True，失败返回False"""
        if self.get_resource(location, resource_type) >= amount:
            self.resources[location][resource_type] -= amount
            return True
        return False

    def add_resource(self, location: str, resource_type: str, amount: int = 1):
        """添加资源"""
        if location not in self.resources:
            self.resources[location] = {}
        self.resources[location][resource_type] = self.resources[location].get(resource_type, 0) + amount

    def to_dict(self):
        return {
            "tick": self.state.tick,
            "weather": self.state.weather,
            "weather_name": self.get_weather_name(),
            "locations": {k: {**v, "agents": list(v["agents"])} for k, v in self.locations.items()},
            "resources": self.resources
        }
