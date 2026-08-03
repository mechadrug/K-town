import re

# --- world.py ---
path = r"C:\Users\azi\Desktop\K-town-demo-v0.1.0\world.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add school and mine locations
content = content.replace(
    '"wilderness": {"id": "wilderness", "name": "荒野", "type": "wilderness", "agents": [], "description": "采集资源、探索未知、发现新知识的区域"},\n        }',
    '"wilderness": {"id": "wilderness", "name": "荒野", "type": "wilderness", "agents": [], "description": "采集资源、探索未知、发现新知识的区域"},\n            "school": {"id": "school", "name": "学校", "type": "school", "agents": [], "description": "教学育人、治病救人的场所"},\n            "mine": {"id": "mine", "name": "矿洞", "type": "mine", "agents": [], "description": "采集矿石、挖掘珍贵矿物的地下洞穴"},\n        }'
)

# Add resources for new locations
content = content.replace(
    '"wilderness": {"food": 50, "materials": 30}\n        }',
    '"wilderness": {"food": 50, "materials": 30},\n            "school": {"food": 5, "materials": 10},\n            "mine": {"food": 0, "materials": 50}\n        }'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("world.py done")

# --- agent.py ---
path = r"C:\Users\azi\Desktop\K-town-demo-v0.1.0\agent.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add healer and miner work slots in _get_work_slot
content = content.replace(
    'elif self.identity.role in [Role.FORAGER, Role.FARMER, Role.SCOUT]:\n            slots = [(7,12,"wilderness"),(13,18,"wilderness")]',
    'elif self.identity.role in [Role.FORAGER, Role.FARMER, Role.SCOUT]:\n            slots = [(7,12,"wilderness"),(13,18,"wilderness")]\n        # 学校工作时间：医生\n        elif self.identity.role == Role.HEALER:\n            slots = [(8,12,"school"),(13,17,"school")]\n        # 矿洞工作时间：矿工\n        elif self.identity.role == Role.MINER:\n            slots = [(6,12,"mine"),(13,16,"mine")]'
)

# 2. Add role actions in _role
content = content.replace(
    'Role.STORYTELLER: ("talk", f"{n}在广场给大家讲有趣的冒险故事"),\n            Role.PLAYER: ("observe", f"{n}在小镇里四处探索，发现新鲜事")',
    'Role.STORYTELLER: ("talk", f"{n}在广场给大家讲有趣的冒险故事"),\n            Role.HEALER: ("work", f"{n}在学校救治病人，配制药剂"),\n            Role.MINER: ("work", f"{n}在矿洞挖掘矿石，叮叮当当忙个不停"),\n            Role.PLAYER: ("observe", f"{n}在小镇里四处探索，发现新鲜事")'
)

# 3. Add to _get_location_cn
content = content.replace(
    'loc_map = {"square": "广场", "workshop": "工坊", "wilderness": "荒野"}',
    'loc_map = {"square": "广场", "workshop": "工坊", "wilderness": "荒野", "school": "学校", "mine": "矿洞"}'
)

# 4. Add to _get_role_cn
content = content.replace(
    '"storyteller": "讲故事的人",\n            "player": "旅行者"',
    '"storyteller": "讲故事的人",\n            "healer": "医生",\n            "miner": "矿工",\n            "player": "旅行者"'
)

# 5. Add new agents in populate_agents
content = content.replace(
    '("agent_player", "旅行者", Role.PLAYER, ["adaptable", "curious"], "square", 10)\n    ]',
    '("agent_player", "旅行者", Role.PLAYER, ["adaptable", "curious"], "square", 10),\n        ("agent_healer", "医生希尔达", Role.HEALER, ["careful", "gentle", "knowledgeable"], "school", 45),\n        ("agent_miner", "矿工戈尔", Role.MINER, ["brave", "dilient", "quiet"], "mine", 55)\n    ]'
)

# 6. Add goals for new agents
content = content.replace(
    '"agent_player": ("探索小镇秘密", 6, 0.2)\n    }',
    '"agent_player": ("探索小镇秘密", 6, 0.2),\n        "agent_healer": ("救治更多病人", 9, 0.5),\n        "agent_miner": ("采集稀有矿石", 8, 0.6)\n    }'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("agent.py done")

# --- config.yaml ---
path = r"C:\Users\azi\Desktop\K-town-demo-v0.1.0\config.yaml"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("locations: 3", "locations: 5")
content = content.replace("agents: 10", "agents: 12")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("config.yaml done")
