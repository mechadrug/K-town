with open("tick.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "for a in self.agenelif event.type == EventType.RUMOR_SPREAD:",
    """for a in self.agents:
                a.state.energy = max(0, a.state.energy - 15)
                a.state.gold = max(0, a.state.gold - 5)
            # 减少荒野资源
            if event.location in self.world.resources:
                for r in self.world.resources[event.location]:
                    self.world.resources[event.location][r] = max(0, self.world.resources[event.location][r] - 10)
        elif event.type == EventType.RUMOR_SPREAD:"""
)

with open("tick.py", "w", encoding="utf-8") as f:
    f.write(content)
print("修复完成")
