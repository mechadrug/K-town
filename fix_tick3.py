with open("tick.py", "r", encoding="utf-8") as f:
    content = f.read()

old_method = """    async def _process_event(self, event):
        if event.type == EventType.WEATHER_CHANGE:
            w = event.payload.get("weather", "unknown")
            for a in self.agents:
                if a.state.location == event.location:
                    c = self.knowledge.observe(a.identity.id, "weather", f"今天天气是{w}", a.state.location)
                    self.logger.log_knowledge(0, c.id, a.identity.id, "create", "", c.claim)
        elif event.type == EventType.RESOURCE_FOUND:
            r = event.payload.get("resource", "unknown")
            aid = event.payload.get("agent_id", "")
            if aid: self.knowledge.observe(aid, "resource", f"在{event.location}发现了{r}", event.location)
        elif event.type == EventType.SOCIAL_ENCOUNTER:
            aids = event.payload.get("agents", [])
            for aid in aids:
                self.knowledge.observe(aid, "social", f"在{event.location}遇到了其他人", event.location)
            if len(aids) >= 2:
                claims_a = self.knowledge.agent_knowledge(aids[0])
                if claims_a:
                    top = max(claims_a, key=lambda c: c.confidence)
                    self.knowledge.propagate(top.id, aids[0], aids[1], 0.8)
        elif event.type == EventType.ITEM_CRAFTED:
            item = event.payload.get("item", "unknown")
            aid = event.payload.get("agent_id", "")
            if aid: self.knowledge.observe(aid, "craft", f"制作了{item}", event.location)
        elif event.type == EventType.RUMOR_SPREAD:
            claim = event.payload.get("claim", "")
            f = event.payload.get("from", "")
            t = event.payload.get("to", "")
            if f and t and claim:
                self.knowledge.observe(f, "rumor", claim, event.location)
                self.knowledge.observe(t, "rumor", f"听说{claim}", event.location)"""

new_method = """    async def _process_event(self, event):
        if event.type == EventType.WEATHER_CHANGE:
            w = event.payload.get("weather", "unknown")
            for a in self.agents:
                if a.state.location == event.location:
                    c = self.knowledge.observe(a.identity.id, "weather", f"今天天气是{w}", a.state.location)
                    self.logger.log_knowledge(0, c.id, a.identity.id, "create", "", c.claim)
        elif event.type == EventType.RESOURCE_FOUND:
            r = event.payload.get("resource", "unknown")
            aid = event.payload.get("agent_id", "")
            if aid: self.knowledge.observe(aid, "resource", f"在{event.location}发现了{r}", event.location)
        elif event.type == EventType.SOCIAL_ENCOUNTER:
            aids = event.payload.get("agents", [])
            for aid in aids:
                self.knowledge.observe(aid, "social", f"在{event.location}遇到了其他人", event.location)
            if len(aids) >= 2:
                claims_a = self.knowledge.agent_knowledge(aids[0])
                if claims_a:
                    top = max(claims_a, key=lambda c: c.confidence)
                    self.knowledge.propagate(top.id, aids[0], aids[1], 0.8)
        elif event.type == EventType.ITEM_CRAFTED:
            item = event.payload.get("item", "unknown")
            aid = event.payload.get("agent_id", "")
            if aid: self.knowledge.observe(aid, "craft", f"制作了{item}", event.location)
        elif event.type == EventType.WEATHER_IMPACT:
            impact = event.payload.get("impact", 0)
            for a in self.agents:
                if a.state.location == event.location:
                    a.state.energy = max(0, a.state.energy + impact * 10)
        elif event.type == EventType.SOCIAL_RELATION_CHANGE:
            agent1 = event.payload.get("agent1", "")
            agent2 = event.payload.get("agent2", "")
            change = event.payload.get("change", 0)
            for a in self.agents:
                if a.identity.id == agent1:
                    a.state.social_ties[agent2] = a.state.social_ties.get(agent2, 0) + change
                elif a.identity.id == agent2:
                    a.state.social_ties[agent1] = a.state.social_ties.get(agent1, 0) + change
        elif event.type == EventType.PRICE_CHANGE:
            pass
        elif event.type == EventType.KNOWLEDGE_CONFLICT:
            claim1 = event.payload.get("claim1", "")
            claim2 = event.payload.get("claim2", "")
            self.knowledge.dispute(claim1, claim2)
        elif event.type == EventType.AGENT_GOAL_COMPLETE:
            agent_id = event.payload.get("agent_id", "")
            for a in self.agents:
                if a.identity.id == agent_id:
                    a.state.mood = Mood.HAPPY
                    a.state.gold += 20
                    break
        elif event.type == EventType.FESTIVAL:
            for a in self.agents:
                a.state.mood = Mood.HAPPY
                a.state.energy = min(100, a.state.energy + 10)
        elif event.type == EventType.DISASTER:
            for a in self.agents:
                a.state.energy = max(0, a.state.energy - 15)
                a.state.gold = max(0, a.state.gold - 5)
            if event.location in self.world.resources:
                for r in self.world.resources[event.location]:
                    self.world.resources[event.location][r] = max(0, self.world.resources[event.location][r] - 10)
        elif event.type == EventType.RUMOR_SPREAD:
            claim = event.payload.get("claim", "")
            f = event.payload.get("from", "")
            t = event.payload.get("to", "")
            if f and t and claim:
                self.knowledge.observe(f, "rumor", claim, event.location)
                self.knowledge.observe(t, "rumor", f"听说{claim}", event.location)"""

content = content.replace(old_method, new_method)

with open("tick.py", "w", encoding="utf-8") as f:
    f.write(content)
print("修复完成")
