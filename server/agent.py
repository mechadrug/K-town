import random,time,uuid
from typing import List,Optional
from .models import AgentIdentity,AgentState,Goal,MemoryEntry,Mood,Role,KnowledgeClaim,ClaimSource

class Agent:
    def __init__(self, identity:AgentIdentity, location="square"):
        self.identity = identity
        self.state = AgentState(location=location)
        self.memory_short = []
        self.memory_long = []
        self.diary = []
        self.goals = []
        self.knowledge = []

    def perceive(self, events):
        self.memory_short.extend(events)
        if len(self.memory_short)>20:
            self.memory_short = self.memory_short[-20:]

    def think(self, hour):
        if len(self.memory_short)>10:
            for m in self.memory_short[-5:]:
                self.memory_long.append(MemoryEntry(summary=m,importance=7.0,location=self.state.location))
            self.memory_short = self.memory_short[:-5]
        if self.state.energy<20: self.state.mood=Mood.SAD
        elif self.state.energy<50: self.state.mood=Mood.ANXIOUS
        elif self.state.energy>80: self.state.mood=Mood.HAPPY
        self.state.energy = max(0, self.state.energy-1)
        if hour>=21 or hour<6:
            self.state.energy = min(100, self.state.energy+15)

    def decide(self, hour, agents_here, events):
        n = self.identity.name
        # 低体力优先休息
        if self.state.energy<20: return {"type":"rest","desc": f"{n}体力不支，正在休息","target":""}
        # 晚上睡觉
        if hour>=21 or hour<6: return {"type":"sleep","desc": f"{n}正在睡觉","target":""}
        # 获取该角色的工作时间和地点
        work_slot = self._get_work_slot(hour)
        # 如果在工作地点，执行工作
        if work_slot and self.state.location == work_slot["loc"]:
            return self._role(work_slot)
        # 如果在广场且有多人，开心的话就社交
        if self.state.location == "square" and len(agents_here) > 1 and ("social" in self.identity.traits or self.state.mood == Mood.HAPPY):
            return {"type":"talk","desc": f"{n}和周围的人聊天","target":""}
        # 调查事件
        if events:
            return {"type":"investigate","desc": f"{n}去调查附近的事件","target":""}
        # 移动到工作地点
        if work_slot and self.state.location != work_slot["loc"]:
            return {"type":"move","desc": f"{n}前往{self._get_location_cn(work_slot['loc'])}","target":work_slot["loc"]}
        # 商人去广场交易
        if self.identity.role == Role.MERCHANT and self.state.location != "square":
            return {"type":"move","desc": f"{n}前往广场做生意","target":"square"}
        # 默认观察
        return {"type":"observe","desc": f"{n}在附近观察环境","target":""}

    def _get_work_slot(self, hour):
        """根据角色返回工作时间和地点"""
        # 广场工作时间：长者、教师、讲故事的人、商人
        if self.identity.role in [Role.ELDER, Role.TEACHER, Role.STORYTELLER, Role.MERCHANT]:
            slots = [(6,10,"square"),(12,14,"square"),(17,20,"square")]
        # 工坊工作时间：铁匠、木工
        elif self.identity.role in [Role.BLACKSMITH, Role.CARPENTER]:
            slots = [(8,12,"workshop"),(13,17,"workshop")]
        # 荒野工作时间：采集者、农民、侦察兵
        elif self.identity.role in [Role.FORAGER, Role.FARMER, Role.SCOUT]:
            slots = [(7,12,"wilderness"),(13,18,"wilderness")]
        else:
            slots = [(9,17,"square")]
        for start, end, loc in slots:
            if start <= hour < end:
                return {"loc": loc}
        return None

    def _role(self, slot):
        """根据角色返回工作描述"""
        n = self.identity.name
        role_actions = {
            Role.ELDER: ("talk", f"{n}在广场给年轻人分享古老的故事和知识"),
            Role.BLACKSMITH: ("work", f"{n}在工坊锻造工具，叮叮当当忙个不停"),
            Role.CARPENTER: ("work", f"{n}在工坊制作木工家具，手艺精湛"),
            Role.FORAGER: ("work", f"{n}在森林里采集食物和草药"),
            Role.SCOUT: ("work", f"{n}在荒野探索未知的区域，绘制地图"),
            Role.FARMER: ("work", f"{n}在田地里耕种庄稼，期待丰收"),
            Role.MERCHANT: ("trade", f"{n}在广场摆摊，和居民们交易商品"),
            Role.TEACHER: ("talk", f"{n}在广场教孩子们读书写字"),
            Role.STORYTELLER: ("talk", f"{n}在广场给大家讲有趣的冒险故事"),
            Role.PLAYER: ("observe", f"{n}在小镇里四处探索，发现新鲜事")
        }
        action_type, desc = role_actions.get(self.identity.role, ("work", f"{n}在工作"))
        return {"type": action_type, "desc": desc, "target": ""}
    
    def _get_location_cn(self, location: str) -> str:
        """获取地点中文名"""
        loc_map = {"square": "广场", "workshop": "工坊", "wilderness": "荒野"}
        return loc_map.get(location, location)

    def add_goal(self, desc, priority=5.0, urgency=0.5):
        self.goals.append(Goal(id=str(uuid.uuid4())[:8], description=desc, base_priority=priority, urgency=urgency))

    def top_goal(self):
        active = [g for g in self.goals if not g.completed]
        return max(active, key=lambda g: g.base_priority + g.urgency * 10) if active else None

    def to_dict(self):
        g = self.top_goal()
        return {
            "id": self.identity.id,
            "name": self.identity.name,
            "role": self.identity.role.value,
            "role_cn": self._get_role_cn(self.identity.role.value),
            "energy": round(self.state.energy, 1),
            "mood": self.state.mood.value,
            "gold": self.state.gold,
            "location": self.state.location,
            "location_cn": self._get_location_cn(self.state.location),
            "goal": g.description if g else "暂无目标",
            "knowledge_count": len(self.knowledge)
        }

    def _get_role_cn(self, role: str) -> str:
        """获取职业中文名"""
        role_map = {
            "elder": "长者",
            "blacksmith": "铁匠",
            "carpenter": "木匠",
            "forager": "采集者",
            "scout": "侦察兵",
            "merchant": "商人",
            "teacher": "教师",
            "farmer": "农民",
            "storyteller": "讲故事的人",
            "player": "旅行者"
        }
        return role_map.get(role, role)

def populate_agents():
    agents = []
    agent_data = [
        ("agent_elder", "梅奶奶", Role.ELDER, ["wise", "social", "patient"], "square", 30),
        ("agent_blacksmith", "铁匠托林", Role.BLACKSMITH, ["diligent", "proud", "honest"], "workshop", 50),
        ("agent_carpenter", "木匠莉娜", Role.CARPENTER, ["creative", "precise", "quiet"], "workshop", 40),
        ("agent_forager", "采集者费尔南", Role.FORAGER, ["observant", "resourceful", "independent"], "wilderness", 15),
        ("agent_scout", "侦察兵罗文", Role.SCOUT, ["curious", "brave", "restless"], "wilderness", 20),
        ("agent_merchant", "商人维斯珀", Role.MERCHANT, ["social", "shrewd", "charming"], "square", 100),
        ("agent_teacher", "教师奥尔登", Role.TEACHER, ["social", "patient", "knowledgeable"], "square", 35),
        ("agent_farmer", "农民克莱", Role.FARMER, ["patient", "diligent", "quiet"], "wilderness", 25),
        ("agent_storyteller", "讲故事的人艾莉丝", Role.STORYTELLER, ["social", "creative", "charismatic"], "square", 20),
        ("agent_player", "旅行者", Role.PLAYER, ["adaptable", "curious"], "square", 10)
    ]
    for aid, name, role, traits, loc, gold in agent_data:
        a = Agent(AgentIdentity(id=aid, name=name, role=role, traits=traits), location=loc)
        a.state.gold = gold
        agents.append(a)
    # 初始化社交关系
    for a in agents:
        for b in agents:
            if a.identity.id != b.identity.id:
                a.state.social_ties[b.identity.id] = 0.0
    # 初始化目标
    goals_map = {
        "agent_elder": ("传承古老知识", 8, 0.3),
        "agent_blacksmith": ("锻造精良工具", 9, 0.5),
        "agent_carpenter": ("打造优质家具", 8, 0.4),
        "agent_forager": ("采集充足食物", 10, 0.7),
        "agent_scout": ("探索未知区域", 9, 0.5),
        "agent_merchant": ("赚取更多金币", 9, 0.6),
        "agent_teacher": ("教导镇民知识", 8, 0.3),
        "agent_farmer": ("种植丰收庄稼", 10, 0.6),
        "agent_storyteller": ("收集有趣故事", 7, 0.3),
        "agent_player": ("探索小镇秘密", 6, 0.2)
    }
    for a in agents:
        if a.identity.id in goals_map:
            desc, pri, urg = goals_map[a.identity.id]
            a.add_goal(desc, pri, urg)
    return agents
