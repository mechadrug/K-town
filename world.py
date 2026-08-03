from .models import WorldState
from typing import Dict

class World:
    def __init__(self):
        self.state = WorldState()
        self.locations = {
            "square":{"id":"square","name":"Town Square","type":"square","agents":[]},
            "workshop":{"id":"workshop","name":"Workshop","type":"workshop","agents":[]},
            "wilderness":{"id":"wilderness","name":"Wilderness","type":"wilderness","agents":[]},
        }
        self.state.locations = self.locations
        self._weathers = ["clear","cloudy","rainy"]

    def advance(self, tick:int):
        self.state.tick = tick
        if tick % 24 == 6:
            self._change_weather()

    def _change_weather(self):
        self.state.weather = self._weathers[self.state.tick % 3]

    def add_agent_to_location(self, agent_id, location):
        if location in self.locations and agent_id not in self.locations[location]["agents"]:
            self.locations[location]["agents"].append(agent_id)

    def remove_agent_from_location(self, agent_id, location):
        if location in self.locations and agent_id in self.locations[location]["agents"]:
            self.locations[location]["agents"].remove(agent_id)

    def to_dict(self):
        return {"tick":self.state.tick,"weather":self.state.weather,
                "locations":{k:{**v,"agents":list(v["agents"])} for k,v in self.locations.items()}}
