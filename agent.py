"""Agent 模块 v2.0 — 知识驱动决策 + 经济闭环"""
import random,time,uuid
from typing import List,Optional,Dict,Any
from models import AgentIdentity,AgentState,Goal,Mood,Role
from emotions import dominant_emotion, emotion_drift, emotion_to_decision_bias

class Agent:
    def __init__(self, identity:AgentIdentity, location="square"):
        self.identity = identity
        self.state = AgentState(location=location)
        self.diary = []
        self.goals = []

    def perceive(self, events):
        # 感知事件（当前不持久化短期记忆，知识由 KnowledgeEngine 承载）
        pass

    def think(self, hour):
        # 情绪系统 v2（gameplay-design-v4 §3）：生理状态映射到 4 维情绪，再驱动 Mood
        stability = self.identity.personality.get("stability", 0.5)
        emo = self.state.emotions
        is_player = self.identity.role == Role.PLAYER

        # 生理 → 情绪偏移（体力低→悲伤/愤怒；饥饿→焦虑/悲伤）
        # 玩家情绪只由自身行动反馈驱动（_handle_action），不被 NPC 生理逻辑拖拽
        if not is_player:
            if self.state.energy < 20:
                emo["sadness"] = min(100, emo.get("sadness", 50) + 6)
            elif self.state.energy < 50:
                if stability > 0.7:
                    emo["anxiety"] = min(100, emo.get("anxiety", 50) + 2)
                else:
                    emo["anxiety"] = min(100, emo.get("anxiety", 50) + 5)
            elif self.state.energy > 80:
                emo["joy"] = min(100, emo.get("joy", 50) + 3)

            if self.state.hunger > 60:
                emo["anxiety"] = min(100, emo.get("anxiety", 50) + 6)
                emo["sadness"] = min(100, emo.get("sadness", 50) + 5)
            elif self.state.hunger > 30:
                emo["anxiety"] = min(100, emo.get("anxiety", 50) + 2)

        self.state.energy = max(0, self.state.energy-1)
        if hour>=17 or hour<5:
            self.state.energy = min(100, self.state.energy+15)

        # 食物消耗（晚上结算）
        if hour == 19:
            food_need = random.randint(1, 3)
            if self.state.food >= food_need:
                self.state.food -= food_need
                self.state.hunger = max(0, self.state.hunger - 30)
                emo["joy"] = min(100, emo.get("joy", 50) + 2)  # 吃饱了→愉悦
            else:
                # 食物不足 -> 饥饿度上升，体力和心情下降
                self.state.hunger = min(100, self.state.hunger + 40)
                self.state.energy = max(0, self.state.energy - 10)
                emo["anxiety"] = min(100, emo.get("anxiety", 50) + 8)
                emo["sadness"] = min(100, emo.get("sadness", 50) + 6)

        # 食物购买（金币回收机制）—— 价格响应：食物越贵买越少
        if hour == 0 and self.state.hunger > 30 and self.state.food < 3 and self.state.gold > 10:
            base_cost = 5
            max_buy = min(3, self.state.gold // base_cost)
            if max_buy > 0:
                if base_cost > 8 and max_buy > 1:
                    max_buy = max(1, max_buy - 1)
                self.state.gold -= max_buy * base_cost
                self.state.food += max_buy

        # 情绪向基线回归（稳定高者情绪更平稳）
        emotion_drift(self)

        # 由 4 维情绪的主导者同步 Mood（UI 表情/光环层）
        self.state.mood = dominant_emotion(self.state.emotions)

    def decide(self, hour, agents_here, events, knowledge_engine=None, world=None):
        """
        5层优先级决策系统：
        1. 生理需求（体力/饥饿）
        2. 知识驱动（危险/机会）
        3. 目标驱动
        4. 社交驱动
        5. 默认行为
        """
        n = self.identity.name
        p = self.identity.personality
        emo = self.state.emotions

        # 情绪 → 决策渗透（gameplay-design-v4 §3.3）：焦虑→避险、愉悦→社交、愤怒→冲突/效率、悲伤→独处
        emo_bias = emotion_to_decision_bias(self)
        anxiety = emo.get("anxiety", 50)
        joy = emo.get("joy", 50)
        anger = emo.get("anger", 50)
        sadness = emo.get("sadness", 50)

        # === Layer 1: 生理需求（最高优先级）===
        conscientiousness = p.get("conscientiousness", 0.5)
        rest_threshold = 20 - int(conscientiousness * 10)
        # 悲伤→更早休息（行动力下降）；愤怒→勉强支撑
        if sadness >= 60:
            rest_threshold = min(40, rest_threshold + 15)
        elif anger >= 60:
            rest_threshold = max(10, rest_threshold - 5)

        if self.state.energy < rest_threshold:
            return {"type":"rest","desc": f"{n}体力不支，正在休息","target":""}
        
        # 夜晚睡觉（情绪调制：愉悦+开放→夜游；焦虑→更早入睡）
        openness = p.get("openness", 0.5)
        if hour>=17 or hour<5:
            night_curiosity = openness + (joy - 50) / 100 * 0.3
            if night_curiosity > 0.7 and hour < 19 and self.state.energy > 40:
                return {"type":"investigate","desc": f"{n}趁着夜色外出探索","target":""}
            return {"type":"sleep","desc": f"{n}正在睡觉","target":""}

        # === Layer 1.5: 生活节奏（傍晚广场聚集/社交，让小镇有每日空间节律）===
        if 14 <= hour < 17:
            if self.state.location != "square":
                if random.random() < 0.4 + p.get("extraversion", 0.5) * 0.3:
                    return {"type":"move","desc": f"{n}收工了，去广场转转","target":"square"}
            else:
                if random.random() < 0.6:
                    others = [o for o in agents_here if o.identity.id != self.identity.id]
                    if others:
                        return {"type":"talk","desc": f"{n}在广场和邻居们聊起一天的见闻","target":random.choice(others).identity.id}
                    return {"type":"observe","desc": f"{n}在广场悠闲地散步","target":""}

        # === Layer 2: 知识驱动决策 ===
        if knowledge_engine:
            knowledge_actions = knowledge_engine.derive_actions_for_agent(self.identity.id)
            if knowledge_actions:
                top_action = knowledge_actions[0]
                action_type = top_action.get("type", "")
                
                if action_type == "avoid":
                    # 避免某个地点 -> 选择其他地点
                    avoid_target = top_action.get("target", "")
                    if self.state.location == avoid_target:
                        # 需要离开
                        other_locs = ["square", "workshop", "wilderness", "school", "mine"]
                        safe_locs = [l for l in other_locs if l != avoid_target]
                        if safe_locs:
                            new_loc = random.choice(safe_locs)
                            return {"type":"move","desc": f"{n}因为'{top_action.get('reason', '')}'离开当前位置","target":new_loc}
                
                elif action_type == "seek":
                    # 寻找资源 -> 前往资源所在地点
                    target = top_action.get("target", "")
                    if target in ["square", "workshop", "wilderness", "school", "mine"]:
                        return {"type":"move","desc": f"{n}去寻找{target}的资源","target":target}
                
                elif action_type == "befriend":
                    # 信任某人 -> 如果此人在场则社交
                    target_agent = top_action.get("target", "")
                    for a in agents_here:
                        if a.identity.id == target_agent:
                            return {"type":"talk","desc": f"{n}主动与{a.identity.name}交谈","target":target_agent}
                
                elif action_type == "investigate":
                    # 探索 -> 移动到新地点
                    target = top_action.get("target", "")
                    if target in ["square", "workshop", "wilderness", "school", "mine"]:
                        return {"type":"move","desc": f"{n}决定去探索{target}","target":target}

        # === Layer 3: 目标驱动 ===
        active_goals = [g for g in self.goals if not g.completed]
        if active_goals:
            top_goal = max(active_goals, key=lambda g: g.base_priority * g.urgency)
            # 根据目标类型决定行为
            goal_action = self._goal_to_action(top_goal, hour)
            if goal_action:
                goal_action["desc"] = f"{n}为了「{top_goal.description}」{goal_action['desc']}"
                return goal_action
        
        # === Layer 4: 社交驱动（关系后果化：好友聚集、宿敌回避 + 情绪调制）===
        extraversion = p.get("extraversion", 0.5)
        agreeableness = p.get("agreeableness", 0.5)
        stability = p.get("stability", 0.5)

        # 外向性高 + 宜人性高 -> 更可能社交；愉悦高→更想社交，悲伤高→独处
        social_prob = 0.3 + extraversion * 0.3 + agreeableness * 0.2
        social_prob += emo_bias.get("talk", 0)
        if sadness >= 60:
            social_prob -= 0.25

        if agents_here and len(agents_here) > 1:
            others = [o for o in agents_here if o.identity.id != self.identity.id]
            # 宿敌在场：情绪不稳定者或愤怒者倾向离开回避
            rivals = [o for o in others if self.state.social_ties.get(o.identity.id, 0) < -15]
            if rivals and (stability < 0.5 or anger >= 60) and random.random() < 0.4:
                safe = [l for l in ("square", "workshop", "wilderness", "school", "mine") if l != self.state.location]
                return {"type": "move", "desc": f"{n}看到讨厌的人在场，转身离开了", "target": random.choice(safe)}
            # 好友在场：优先与关系最好的人交谈（悲伤者可能反而避开）
            friends = [o for o in others if self.state.social_ties.get(o.identity.id, 0) > 10]
            if friends and sadness < 60 and random.random() < 0.6:
                target = max(friends, key=lambda o: self.state.social_ties.get(o.identity.id, 0))
                return {"type": "talk", "desc": f"{n}主动去找{target.identity.name}聊天", "target": target.identity.id}
            # 随机社交（愤怒者更可能冲突而非闲聊）
            if random.random() < social_prob * 0.5:
                other = random.choice(others)
                if anger >= 60 and random.random() < 0.3:
                    return {"type": "conflict", "desc": f"{n}因愤怒与{other.identity.name}发生争执", "target": other.identity.id}
                return {"type": "talk", "desc": f"{n}和{other.identity.name}闲聊几句", "target": other.identity.id}
        
        # === Layer 5: 默认行为（工作地点）===
        work_slot = self._get_work_slot(hour)
        if work_slot and self.state.location == work_slot['loc']:
            work_prob = 0.6 + conscientiousness * 0.3
            # 愤怒→更拼命工作（效率↑）；悲伤→无心工作（效率↓）
            work_prob += emo_bias.get("work", 0)
            if sadness >= 60:
                work_prob -= 0.2
            # 食物经济闭环：食物贵 → 采集/农耕更卖力（供给回升 → 价格回落）
            if work_slot['role'] in ('forager', 'farmer') and world:
                food_price = world.get_price('food')
                if food_price >= 7:
                    work_prob += 0.2
                elif food_price <= 4:
                    work_prob -= 0.1
            if random.random() < work_prob:
                return self._role(work_slot)
        
        # 去工作地点
        if work_slot:
            return {"type":"move","desc": f"{n}前往{work_slot['name']}","target":work_slot['loc']}
        
        # 默认在广场社交
        if self.state.location != "square":
            return {"type":"move","desc": f"{n}去广场逛逛","target":"square"}
        
        return {"type":"observe","desc": f"{n}在广场观察四周","target":""}

    def _goal_to_action(self, goal, hour):
        """将目标转化为具体行动"""
        desc = goal.description.lower()
        role = self.identity.role
        
        if role in [Role.FORAGER, Role.FARMER] or 'gather' in desc or 'food' in desc:
            return {"type": "gather_food", "desc": "去采集食物", "target": "wilderness"}
        elif role in [Role.BLACKSMITH, Role.CARPENTER] or 'craft' in desc or 'tool' in desc:
            return {"type": "work", "desc": "去工坊工作", "target": "workshop"}
        elif role == Role.SCOUT or 'explore' in desc or 'discover' in desc:
            return {"type": "investigate", "desc": "去荒野探索", "target": "wilderness"}
        elif role in [Role.ELDER, Role.TEACHER] or 'teach' in desc or 'knowledge' in desc:
            return {"type": "talk", "desc": "去传播知识", "target": "square"}
        elif role == Role.STORYTELLER or 'story' in desc or 'collect' in desc:
            return {"type": "talk", "desc": "去收集故事", "target": "square"}
        elif role == Role.MINER or 'ore' in desc or 'mine' in desc:
            return {"type": "work", "desc": "去矿洞采矿", "target": "mine"}
        elif role == Role.HEALER or 'heal' in desc or 'patient' in desc:
            return {"type": "work", "desc": "去学校救治", "target": "school"}
        elif role == Role.MERCHANT or 'gold' in desc or 'earn' in desc:
            return {"type": "trade", "desc": "去广场做生意", "target": "square"}
        else:
            return {"type": "observe", "desc": "在广场观察", "target": "square"}

    def _role(self, work_slot=None):
        """根据角色生成工作行动"""
        n = self.identity.name
        role = self.identity.role
        
        role_actions = {
            Role.ELDER: lambda: {"type":"talk","desc": f"{n}在广场向年轻人讲述古老的传说","target":""},
            Role.BLACKSMITH: lambda: {"type":"craft_tool","desc": f"{n}在工坊锻造工具","target":""},
            Role.CARPENTER: lambda: {"type":"craft_furniture","desc": f"{n}在工坊制作家具","target":""},
            Role.FORAGER: lambda: {"type":"gather_food","desc": f"{n}在荒野采集食物","target":""},
            Role.SCOUT: lambda: {"type":"investigate","desc": f"{n}探索周边区域","target":""},
            Role.MERCHANT: lambda: {"type":"trade","desc": f"{n}在广场打理生意","target":""},
            Role.TEACHER: lambda: {"type":"talk","desc": f"{n}在学校教导镇民知识","target":""},
            Role.FARMER: lambda: {"type":"gather_food","desc": f"{n}在田野辛勤劳作","target":""},
            Role.STORYTELLER: lambda: {"type":"talk","desc": f"{n}在广场讲述冒险故事","target":""},
            Role.HEALER: lambda: {"type":"rest","desc": f"{n}在学校配制药剂","target":""},
            Role.MINER: lambda: {"type":"gather_material","desc": f"{n}在矿洞深处采集矿石","target":""},
            Role.PLAYER: lambda: {"type":"observe","desc": f"{n}观察着小镇的生活","target":""},
        }
        return role_actions.get(role, lambda: {"type":"rest","desc": f"{n}正在休息","target":""})()

    def _get_work_slot(self, hour):
        """获取当前的工作时间段和地点"""
        role = self.identity.role
        
        if role in [Role.ELDER, Role.MERCHANT, Role.TEACHER, Role.STORYTELLER, Role.PLAYER]:
            if 6 <= hour < 14:
                return {"loc": "square", "name": "广场", "role": role.value}
        elif role in [Role.BLACKSMITH, Role.CARPENTER]:
            if 6 <= hour < 14:
                return {"loc": "workshop", "name": "工坊", "role": role.value}
        elif role in [Role.FORAGER, Role.FARMER]:
            if 6 <= hour < 14:
                return {"loc": "wilderness", "name": "荒野", "role": role.value}
        elif role == Role.SCOUT:
            if 6 <= hour < 14:
                return {"loc": "wilderness", "name": "荒野", "role": role.value}
        elif role == Role.HEALER:
            if 6 <= hour < 14:
                return {"loc": "school", "name": "学校", "role": role.value}
        elif role == Role.MINER:
            if 6 <= hour < 14:
                return {"loc": "mine", "name": "矿洞", "role": role.value}
        return None

    def add_goal(self, description, priority=5, urgency=0.5):
        g = Goal(id=str(uuid.uuid4())[:8], description=description, base_priority=priority, urgency=urgency)
        self.goals.append(g)

    def top_goal(self):
        active = [g for g in self.goals if not g.completed]
        if not active:
            return None
        return max(active, key=lambda g: g.base_priority * g.urgency)

    def to_dict(self):
        return {
            "id": self.identity.id,
            "name": self.identity.name,
            "role": self.identity.role.value,
            "role_cn": self.get_role_cn(self.identity.role.value),
            "location": self.state.location,
            "location_cn": self.get_location_cn(self.state.location),
            "energy": self.state.energy,
            "mood": self.state.mood.value,
            "emotions": self.state.emotions,
            "habits": {k: dict(v) for k, v in self.state.habit_bias.items()},
            "gold": self.state.gold,
            "food": self.state.food,
            "hunger": self.state.hunger,
            "action_points": self.state.ap,
            "max_ap": self.state.ap_max,
            "night_ap": self.state.night_ap,
            "social_ties": self.state.social_ties,
            "current_task": self.state.current_task.description if self.state.current_task else None,
            "traits": self.identity.traits,
            "skills": self.identity.skills,
            "personality": self.identity.personality,
            "faction_id": self.state.faction_id,
            "goals": [{"description": g.description, "completed": g.completed} for g in self.goals],
            "diary": self.diary[-10:] if self.diary else []
        }

    def get_role_cn(self, role: str) -> str:
        role_map = {
            "elder": "长者", "blacksmith": "铁匠", "carpenter": "木匠",
            "forager": "采集者", "scout": "侦察兵", "merchant": "商人",
            "teacher": "教师", "farmer": "农民", "storyteller": "讲故事的人",
            "healer": "医生", "miner": "矿工", "player": "旅行者"
        }
        return role_map.get(role, role)

    def get_location_cn(self, location: str) -> str:
        """获取地点中文名（与 world.locations 唯一来源对齐）"""
        loc_map = {
            "square": "广场", "workshop": "工坊", "wilderness": "荒野",
            "school": "学校", "mine": "矿洞",
        }
        return loc_map.get(location, location)

    def write_diary(self, day: int, behaviors: list, gold_before: int = 0):
        """由 tick 在日结时调用：根据当天行为日志写一条日记（档案"最近日记"可见）"""
        if not behaviors:
            self.diary.append(f"第{day}天：在小镇里平静地度过了一天。")
            return
        if len(behaviors) <= 2:
            summary = "；".join(behaviors)
        else:
            summary = f"{behaviors[0]}；……；{behaviors[-1]}"
        gold_delta = self.state.gold - gold_before
        if gold_delta > 0:
            summary += f"（赚了{gold_delta}金币）"
        elif gold_delta < 0:
            summary += f"（花了{abs(gold_delta)}金币）"
        self.diary.append(f"第{day}天：{summary}")
        if len(self.diary) > 20:
            self.diary = self.diary[-20:]

def populate_agents():
    agents = []
    agent_data = [
        # id, name, role, traits, location, gold, personality
        ("agent_elder", "梅奶奶", Role.ELDER, ["wise", "social", "patient"], "square", 30,
         {"extraversion": 0.6, "conscientiousness": 0.7, "openness": 0.5, "agreeableness": 0.9, "stability": 0.8}),
        ("agent_blacksmith", "铁匠托林", Role.BLACKSMITH, ["diligent", "proud", "honest"], "workshop", 50,
         {"extraversion": 0.4, "conscientiousness": 0.9, "openness": 0.3, "agreeableness": 0.5, "stability": 0.7}),
        ("agent_carpenter", "木匠莉娜", Role.CARPENTER, ["creative", "precise", "quiet"], "workshop", 40,
         {"extraversion": 0.3, "conscientiousness": 0.8, "openness": 0.6, "agreeableness": 0.7, "stability": 0.6}),
        ("agent_forager", "采集者费尔南", Role.FORAGER, ["observant", "resourceful", "independent"], "wilderness", 15,
         {"extraversion": 0.3, "conscientiousness": 0.6, "openness": 0.7, "agreeableness": 0.4, "stability": 0.5}),
        ("agent_scout", "侦察兵罗文", Role.SCOUT, ["curious", "brave", "restless"], "wilderness", 20,
         {"extraversion": 0.5, "conscientiousness": 0.4, "openness": 0.9, "agreeableness": 0.5, "stability": 0.3}),
        ("agent_merchant", "商人维斯珀", Role.MERCHANT, ["social", "shrewd", "charming"], "square", 100,
         {"extraversion": 0.8, "conscientiousness": 0.6, "openness": 0.7, "agreeableness": 0.4, "stability": 0.6}),
        ("agent_teacher", "教师奥尔登", Role.TEACHER, ["social", "patient", "knowledgeable"], "square", 35,
         {"extraversion": 0.6, "conscientiousness": 0.7, "openness": 0.6, "agreeableness": 0.8, "stability": 0.7}),
        ("agent_farmer", "农民克莱", Role.FARMER, ["patient", "diligent", "quiet"], "wilderness", 25,
         {"extraversion": 0.3, "conscientiousness": 0.8, "openness": 0.3, "agreeableness": 0.6, "stability": 0.8}),
        ("agent_storyteller", "讲故事的人艾莉丝", Role.STORYTELLER, ["social", "creative", "charismatic"], "square", 20,
         {"extraversion": 0.9, "conscientiousness": 0.4, "openness": 0.8, "agreeableness": 0.7, "stability": 0.4}),
        ("agent_player", "旅行者", Role.PLAYER, ["adaptable", "curious"], "square", 10,
         {"extraversion": 0.6, "conscientiousness": 0.5, "openness": 0.7, "agreeableness": 0.6, "stability": 0.5}),
        ("agent_healer", "医生希尔达", Role.HEALER, ["careful", "gentle", "knowledgeable"], "school", 45,
         {"extraversion": 0.5, "conscientiousness": 0.8, "openness": 0.5, "agreeableness": 0.9, "stability": 0.7}),
        ("agent_miner", "矿工戈尔", Role.MINER, ["brave", "diligent", "quiet"], "mine", 55,
         {"extraversion": 0.2, "conscientiousness": 0.9, "openness": 0.2, "agreeableness": 0.5, "stability": 0.6}),
    ]
    for aid, name, role, traits, loc, gold, personality in agent_data:
        a = Agent(AgentIdentity(id=aid, name=name, role=role, traits=traits, personality=personality), location=loc)
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
        "agent_player": ("探索小镇秘密", 6, 0.2),
        "agent_healer": ("救治更多病人", 9, 0.5),
        "agent_miner": ("采集稀有矿石", 8, 0.6)
    }
    for a in agents:
        if a.identity.id in goals_map:
            desc, pri, urg = goals_map[a.identity.id]
            a.add_goal(desc, pri, urg)
    
    return agents
