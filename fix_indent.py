with open("tick.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "            await self._process_event(event)\n                    # 自动固化高置信度知识\n                    self.knowledge.auto_solidify()",
    "            await self._process_event(event)\n            # 自动固化高置信度知识\n            self.knowledge.auto_solidify()"
)

with open("tick.py", "w", encoding="utf-8") as f:
    f.write(content)
print("修复完成")
