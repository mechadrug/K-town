import random,time,uuid
from typing import List,Optional,Dict,Any
from models import AgentIdentity,AgentState,Goal,MemoryEntry,Mood,Role,KnowledgeClaim,ClaimSource

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
        
        # 人格影响情绪稳定性
        stability = self.identity.personality.get("stability", 0.5)
        
        if self.state.energy<20: 
            self.state.mood=Mood.SAD
        elif self.state.energy<50:
            # 情绪稳定性高的Agent不容易焦虑
            if stability > 0.7:
                self.state.mood=Mood.NEUTRAL
            else:
                self.state.mood=Mood.ANXIOUS
        elif self.state.energy>80:
            self.state.mood=Mood.HAPPY
        
        # 情绪稳定性低→体力下降时更容易心情差
        if stability < 0.3 and self.state.energy < 40:
            if random.random() < 0.3:
                self.state.mood = Mood.ANGRY if random.random() < 0.5 else Mood.SAD
        
        self.state.energy = max(0, self.state.energy-1)
        if hour>=21 or hour<6:
            self.state.energy = min(100, self.state.energy+15)

        # 食物消耗（每天1-3单位，晚上结算）
        if hour == 21:
            food_need = random.randint(1, 3)
            if self.state.food >= food_need:
                self.state.food -= food_need
                self.state.hunger = max(0, self.state.hunger - 30)
            else:
                # 食物不足→饥饿度上升，体力和心情下降
                self.state.hunger = min(100, self.state.hunger + 40)
                self.state.energy = max(0, self.state.energy - 10)
                if self.state.hunger > 60:
                    self.state.mood = Mood.SAD

    def decide(self, hour, agents_here, events):
        n = self.identity.name
        p = self.identity.personality
        
        # 低体力优先休息（但尽责性高的人会坚持工作）
        conscientiousness = p.get("conscientiousness", 0.5)
        rest_threshold = 20 - int(conscientiousness * 10)  # 尽责性高→阈值更低（更晚休息）
        
        if self.state.energy < rest_threshold:
            return {"type":"rest","desc": f"{n}体力不支，正在休息","target":""}
        
        # 晚上睡觉（但开放性高的人可能熬夜探索）
        openness = p.get("openness", 0.5)
        if hour>=21 or hour<6:
            if openness > 0.7 and hour < 23 and self.state.energy > 40:
                return {"type":"investigate","desc": f"{n}趁着夜色外出探索","target":""}
            return {"type":"sleep","desc": f"{n}正在睡觉","target":""}
        
        # 获取该角色的工作时间和地点
        work_slot = self._get_work_slot(hour)
        
        # 如果在工作地点，执行工作
        # 尽责性高→更可能在工作时间工作
        if work_slot and self.state.location == work_slot['loc']:
            if random.random() < (0.6 + conscientiousness * 0.3):
                return self._role(work_slot)
        
        # 社交决策：外向性高+宜人性高→更可能社交
        extraversion = p.get("extraversion", 0.5)
        agreeableness = p.get("agreeableness", 0.5)
        
        if self.state.location == "square" and len(agents_here) > 1:
            social_chance = 0.3 + extraversion * 0.4 + agreeableness * 0.2
            if "social" in self.identity.traits:
                social_chance += 0.15
            if self.state.mood == Mood.HAPPY:
                social_chance += 0.1
            if random.random() < social_chance:
                return {"type":"talk","desc": f"{n}和周围的人聊天","target":""}

        # 关系驱动：有好朋友在→主动寻找互动
        best_friend = None
        best_tie = -999
        worst_enemy = None
        worst_tie = 999
        for other_id in agents_here:
            if other_id == self.identity.id:
                continue
            tie = self.state.social_ties.get(other_id, 0)
            if tie > best_tie:
                best_tie = tie
                best_friend = other_id
            if tie < worst_tie:
                worst_tie = tie
                worst_enemy = other_id

        # 好朋友在→优先互动（好感>30）
        if best_friend and best_tie > 30 and random.random() < 0.4:
            return {'type': 'talk', 'desc': f'{n}看到好朋友，开心地走过去打招呼', 'target': best_friend}

        # 讨厌的人在→可能回避（好感<-10）
        if worst_enemy and worst_tie < -10 and random.random() < 0.3:
            locations = ['square', 'workshop', 'wilderness', 'school', 'mine']
            if self.state.location in locations:
                locations.remove(self.state.location)
            target = random.choice(locations)
            return {'type': 'move', 'desc': f'{n}不想看到不喜欢的人，转身去了{self._get_location_cn(target)}', 'target': target}

        # 挚友在→分享知识（好感>50）
        if best_friend and best_tie > 50 and random.random() < 0.25:
            if self.knowledge:
                return {'type': 'talk', 'desc': f'{n}和挚友分享自己的知识', 'target': best_friend}

        # 知识驱动：评估持有知识对决策的影响
        knowledge_modifier = self._evaluate_knowledge_impact()

        # 危险知识→回避相关地点
        for loc, modifier in knowledge_modifier.items():
            if modifier < 0.8 and self.state.location == loc:
                # 这个地点有危险，考虑离开
                if random.random() < 0.3:
                    locations = ['square', 'workshop', 'wilderness', 'school', 'mine']
                    locations.remove(loc)
                    target = random.choice(locations)
                    return {'type': 'move', 'desc': f'{n}想起了一些不好的传闻，决定去{self._get_location_cn(target)}', 'target': target}
        
        # 调查事件（开放性高的人更喜欢调查）
        if events:
            investigate_chance = 0.2 + openness * 0.4
            if random.random() < investigate_chance:
                return {"type":"investigate","desc": f"{n}去调查附近的事件","target":""}
        
        # 移动到工作地点
        if work_slot and self.state.location != work_slot['loc']:
            # 尽责性高→更愿意去工作
            if random.random() < (0.5 + conscientiousness * 0.3):
                loc = work_slot["loc"]
                return {"type":"move","desc": f"{n}前往{self._get_location_cn(loc)}","target":loc}
        
        # 商人去广场交易
        if self.identity.role == Role.MERCHANT and self.state.location != "square":
            return {"type":"move","desc": f"{n}前往广场做生意","target":"square"}
        
        # 开放性高→可能随机探索
        if openness > 0.6 and random.random() < 0.2:
            locations = ["square", "workshop", "wilderness", "school", "mine"]
            if self.state.location in locations:
                locations.remove(self.state.location)
            target = random.choice(locations)
            return {"type":"move","desc": f"{n}想去{self._get_location_cn(target)}看看","target":target}
        
        # 默认观察
        return {"type":"observe","desc": f"{n}在附近观察环境","target":""}


    def _evaluate_knowledge_impact(self) -> Dict[str, float]:
        """评估持有知识对当前决策的影响，返回各地点的修正权重"""
        location_modifier = {}
        knowledge_text = " ".join([k.claim.lower() for k in self.knowledge])
        
        # 危险知识 → 减少去相关地点
        if "狼" in knowledge_text or "危险" in knowledge_text or "野兽" in knowledge_text:
            location_modifier["wilderness"] = location_modifier.get("wilderness", 1.0) * 0.5
        if "坍塌" in knowledge_text or "矿洞" in knowledge_text:
            location_modifier["mine"] = location_modifier.get("mine", 1.0) * 0.6
        if "森林" in knowledge_text and "危险" in knowledge_text:
            location_modifier["wilderness"] = location_modifier.get("wilderness", 1.0) * 0.7
        
        # 机会知识 → 增加去相关地点
        if "草药" in knowledge_text or "丰富" in knowledge_text:
            location_modifier["wilderness"] = location_modifier.get("wilderness", 1.0) * 1.3
        if "矿" in knowledge_text and "丰富" in knowledge_text:
            location_modifier["mine"] = location_modifier.get("mine", 1.0) * 1.3
        if "集市" in knowledge_text or "交易" in knowledge_text:
            location_modifier["square"] = location_modifier.get("square", 1.0) * 1.2
        
        return location_modifier
    
    def _get_knowledge_summary(self) -> str:
        """获取Agent的知识摘要，用于日志"""
        if not self.knowledge:
            return ""
        recent = sorted(self.knowledge, key=lambda k: k.confidence, reverse=True)[:3]
        return "；".join([k.claim for k in recent])



    def evaluate_trade(self, market_prices: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """评估是否需要进行交易，返回交易决策"""
        # 商人：低买高卖
        if self.identity.role == Role.MERCHANT:
            # 找最便宜的供应商
            best_deal = None
            best_profit = 0
            for resource, price in market_prices.items():
                base_price = 5  # 假设基础价格
                if price < base_price * 0.8:  # 价格低于基础价格80%→买入
                    profit = base_price - price
                    if profit > best_profit:
                        best_profit = profit
                        best_deal = {"action": "buy", "resource": resource, "price": price}
                elif self.state.inventory and resource in self.state.inventory:
                    # 有库存且价格高于基础价格→卖出
                    if price > base_price * 1.2:
                        profit = price - base_price
                        if profit > best_profit:
                            best_profit = profit
                            best_deal = {"action": "sell", "resource": resource, "price": price}
            return best_deal
        
        # 普通Agent：饥饿时买食物
        if self.state.hunger > 30 and self.state.food < 2:
            food_price = market_prices.get("food", 5)
            if self.state.gold >= food_price:
                return {"action": "buy", "resource": "food", "price": food_price}
        
        # 产出者：有富余产品时卖出
        if self.identity.role in (Role.FORAGER, Role.FARMER) and self.state.food > 5:
            food_price = market_prices.get("food", 5)
            if food_price > 4:  # 价格好时卖出
                return {"action": "sell", "resource": "food", "price": food_price}
        
        return None


    def _get_work_slot(self, hour):
        if self.identity.role in [Role.ELDER, Role.TEACHER, Role.STORYTELLER, Role.MERCHANT]:
            slots = [(6,10,"square"),(12,14,"square"),(17,20,"square")]
        elif self.identity.role in [Role.BLACKSMITH, Role.CARPENTER]:
            slots = [(8,12,"workshop"),(13,17,"workshop")]
        elif self.identity.role in [Role.FORAGER, Role.FARMER, Role.SCOUT]:
            slots = [(7,12,"wilderness"),(13,18,"wilderness")]
        elif self.identity.role == Role.HEALER:
            slots = [(8,12,"school"),(13,17,"school")]
        elif self.identity.role == Role.MINER:
            slots = [(6,12,"mine"),(13,16,"mine")]
        else:
            slots = [(9,17,"square")]
        for start, end, loc in slots:
            if start <= hour < end:
                return {"loc": loc}
        return None

    def _role(self, slot):
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
            Role.HEALER: ("work", f"{n}在学校救治病人，配制药剂"),
            Role.MINER: ("work", f"{n}在矿洞挖掘矿石，叮叮当当忙个不停"),
            Role.PLAYER: ("observe", f"{n}在小镇里四处探索，发现新鲜事")
        }
        action_type, desc = role_actions.get(self.identity.role, ("work", f"{n}在工作"))
        return {"type": action_type, "desc": desc, "target": ""}
    
    def _get_location_cn(self, location: str) -> str:
        loc_map = {"square": "广场", "workshop": "工坊", "wilderness": "荒野", "school": "学校", "mine": "矿洞"}
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
            "knowledge_count": len(self.knowledge),
            "food": self.state.food,
            "hunger": round(self.state.hunger, 1),
            "personality": self.identity.personality,
            "social_ties": {k: round(v, 1) for k, v in self.state.social_ties.items()},
            "ap": self.state.ap,
            "ap_max": self.state.ap_max
        }

    def _get_role_cn(self, role: str) -> str:
        role_map = {
            "elder": "长者", "blacksmith": "铁匠", "carpenter": "木匠",
            "forager": "采集者", "scout": "侦察兵", "merchant": "商人",
            "teacher": "教师", "farmer": "农民", "storyteller": "讲故事的人",
            "healer": "医生", "miner": "矿工", "player": "旅行者"
        }
        return role_map.get(role, role)

def populate_agents():
    agents = []
    agent_data = [
        # id, name, role, traits, location, gold, personality
        # personality: extraversion, conscientiousness, openness, agreeableness, stability
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
