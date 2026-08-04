"""小镇进化系统 v2.0"""
import time
from typing import Dict,List,Any

class TownEvolution:
    """小镇时代进化系统"""
    
    ERAS = [
        {"name": "宁静村庄", "min_days": 0, "description": "小镇刚刚建立，一切都很平静"},
        {"name": "贸易驿站", "min_days": 3, "description": "商人到来，贸易开始繁荣"},
        {"name": "学识小镇", "min_days": 7, "description": "学校建立，知识开始传播"},
        {"name": "派系之都", "min_days": 14, "description": "派系形成，政治开始复杂化"},
        {"name": "繁荣小镇", "min_days": 21, "description": "小镇达到空前的繁荣"}
    ]
    
    def __init__(self):
        self.current_era = self.ERAS[0]["name"]
        self.era_history: List[Dict[str, Any]] = []
    
    def check_era(self, day: int, agents, factions: Dict) -> str:
        """检查是否满足时代晋升条件"""
        new_era = self.current_era
        
        for era in reversed(self.ERAS):
            if day >= era["min_days"]:
                # 额外条件检查
                if era["name"] == "贸易驿站":
                    merchants = [a for a in agents if a.identity.role.value == "merchant"]
                    if merchants and merchants[0].state.gold > 80:
                        new_era = era["name"]
                elif era["name"] == "学识小镇":
                    teachers = [a for a in agents if a.identity.role.value == "teacher"]
                    if teachers:
                        new_era = era["name"]
                elif era["name"] == "派系之都":
                    if len(factions) >= 2:
                        new_era = era["name"]
                elif era["name"] == "繁荣小镇":
                    total_gold = sum(a.state.gold for a in agents)
                    if total_gold > 500:
                        new_era = era["name"]
                else:
                    new_era = era["name"]
                break
        
        if new_era != self.current_era:
            self.era_history.append({
                "from": self.current_era,
                "to": new_era,
                "day": day,
                "timestamp": time.time()
            })
            self.current_era = new_era
        
        return self.current_era


class PlayerInfluence:
    """玩家影响力传播系统"""
    
    def __init__(self):
        self.reputation: int = 0  # 声望
        self.influence_score: float = 0  # 影响力分数
        self.unlocked_actions: List[str] = ["move", "talk", "work", "rest"]
    
    def calculate_influence(self, agents, player_actions_count: int) -> float:
        """计算玩家当前影响力"""
        # 基于：社交关系总和 + 完成任务数 + 知识贡献
        total_tie = 0
        for a in agents:
            if a.identity.role.value == "player":
                total_tie = sum(max(0, v) for v in a.state.social_ties.values())
                break
        
        self.influence_score = total_tie * 0.5 + player_actions_count * 0.3 + self.reputation * 2
        return self.influence_score
    
    def propagate_action(self, action_type: str, target: str, agents) -> List[Dict[str, Any]]:
        """玩家行为产生涟漪效应"""
        effects = []
        
        if action_type == "help" and target:
            # 帮助某人 -> 此人的朋友也对玩家好感+
            target_agent = None
            for a in agents:
                if a.identity.id == target:
                    target_agent = a
                    break
            
            if target_target:
                for other_id, tie in target_agent.state.social_ties.items():
                    if tie > 5 and other_id != "agent_player":
                        # 朋友传播
                        effects.append({
                            "type": "reputation_gain",
                            "target": other_id,
                            "amount": 2,
                            "reason": f"听说你帮助了{target_agent.identity.name}"
                        })
        
        return effects
    
    def check_unlocks(self) -> List[str]:
        """检查是否解锁新行动"""
        newly_unlocked = []
        
        if self.influence_score > 20 and "trade" not in self.unlocked_actions:
            self.unlocked_actions.append("trade")
            newly_unlocked.append("trade")
        
        if self.influence_score > 40 and "mentor" not in self.unlocked_actions:
            self.unlocked_actions.append("mentor")
            newly_unlocked.append("mentor")
        
        if self.reputation > 10 and "announce" not in self.unlocked_actions:
            self.unlocked_actions.append("announce")
            newly_unlocked.append("announce")
        
        return newly_unlocked
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reputation": self.reputation,
            "influence_score": round(self.influence_score, 1),
            "unlocked_actions": self.unlocked_actions
        }
