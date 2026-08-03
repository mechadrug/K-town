import time
from typing import Any
from collections import deque

class Logger:
    def __init__(self, max_size=1000):
        self.world_events = deque(maxlen=max_size)
        self.decisions = deque(maxlen=max_size)
        self.knowledge_logs = deque(maxlen=max_size)

    def log_world_event(self, tick, event_type, location, actors, payload):
        self.world_events.append({"tick":tick,"event_type":event_type,"location":location,"actors":actors,"payload":payload,"timestamp":time.time()})

    def log_decision(self, tick, agent_id, action, reason, goal, confidence, method):
        self.decisions.append({"tick":tick,"agent_id":agent_id,"action":action,"reason":reason,"goal":goal,"confidence":confidence,"method":method})

    def log_knowledge(self, tick, claim_id, agent_id, operation, before="", after=""):
        self.knowledge_logs.append({"tick":tick,"claim_id":claim_id,"agent_id":agent_id,"operation":operation,"before":before,"after":after})

    def query_world_events(self, n=50):
        return list(self.world_events)[-n:]

    def query_decisions(self, n=50):
        return list(self.decisions)[-n:]

    def query_knowledge(self, n=50):
        return list(self.knowledge_logs)[-n:]
