with open('tick.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 添加auto_reset参数
content = content.replace(
    'def __init__(self, world: World, bus: EventBus, agents: list,\n                 knowledge: KnowledgeEngine, logger: Logger, llm: LLMClient,\n                 rate: float = 1.0, day_length: int = 24):',
    'def __init__(self, world: World, bus: EventBus, agents: list,\n                 knowledge: KnowledgeEngine, logger: Logger, llm: LLMClient,\n                 rate: float = 1.0, day_length: int = 24, auto_reset: bool = True):'
)

# 添加自动重置逻辑
content = content.replace(
    '        # 加载历史摘要\n        self._load_history()',
    '        # 自动重置\n        if auto_reset:\n            self.db.reset()\n        # 加载历史摘要\n        self._load_history()'
)

# 添加事件持久化
content = content.replace(
    '            self.current_day_events.append({\n                "tick": tick, "type": event.type.value,\n                "location": event.location, "payload": str(event.payload)[:100],\n            })\n            await self._process_event(event)',
    '            # 保存事件到数据库\n            self.db.save_event(tick, self.current_day, event.type.value, event.location, event.payload)\n            self.current_day_events.append({\n                "tick": tick, "type": event.type.value,\n                "location": event.location, "payload": str(event.payload)[:100],\n            })\n            await self._process_event(event)'
)

with open('tick.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('修改完成')
