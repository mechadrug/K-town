"""派系系统 v2.0 — 关系结构涌现"""
import random
from typing import Dict,List,Any,Set
from models import AgentState

class FactionSystem:
    """派系检测与管理"""
    
    FACTION_THRESHOLD = 10  # 关系值超过此值视为同派
    
    def __init__(self):
        self.factions: Dict[str, Dict[str, Any]] = {}
        self.next_faction_id = 1
    
    def detect_factions(self, agents) -> Dict[str, List[str]]:
        """基于关系值检测派系（简单聚类）"""
        # 构建邻接关系
        adjacency: Dict[str, Set[str]] = {}
        agent_ids = [a.identity.id for a in agents]
        
        for a in agents:
            adjacency[a.identity.id] = set()
            for other_id, tie in a.state.social_ties.items():
                if tie > self.FACTION_THRESHOLD and other_id in agent_ids:
                    adjacency[a.identity.id].add(other_id)
        
        # 简单连通分量检测
        visited = set()
        factions = {}
        faction_idx = 0
        
        for agent_id in agent_ids:
            if agent_id in visited:
                continue
            # BFS找连通分量
            component = set()
            queue = [agent_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            
            # 至少2人形成派系
            if len(component) >= 2:
                faction_id = f"faction_{faction_idx}"
                factions[faction_id] = list(component)
                faction_idx += 1
        
        return factions
    
    def update_faction_membership(self, agents):
        """更新所有Agent的派系归属"""
        detected = self.detect_factions(agents)
        
        # 存储派系信息
        self.factions = {}
        for f_id, members in detected.items():
            # 计算派系中心人物（关系总值最高）
            best_member = None
            best_score = -999
            for m in members:
                agent = next((a for a in agents if a.identity.id == m), None)
                if agent:
                    total_tie = sum(abs(v) for k, v in agent.state.social_ties.items() if k in members and k != m)
                    if total_tie > best_score:
                        best_score = total_tie
                        best_member = m
            
            self.factions[f_id] = {
                "members": members,
                "leader": best_member,
                "influence": len(members) * 10
            }
        
        # 更新 Agent 状态
        agent_faction_map = {}
        for f_id, info in self.factions.items():
            for m in info["members"]:
                agent_faction_map[m] = f_id
        
        for a in agents:
            a.state.faction_id = agent_faction_map.get(a.identity.id, "")
    
    def get_faction_influence(self, faction_id: str) -> int:
        """获取派系影响力"""
        if faction_id in self.factions:
            return self.factions[faction_id].get("influence", 0)
        return 0
    
    def get_shared_faction(self, agent1_id: str, agent2_id: str) -> str:
        """检查两个Agent是否在同一个派系"""
        for f_id, info in self.factions.items():
            members = info.get("members", [])
            if agent1_id in members and agent2_id in members:
                return f_id
        return ""

def apply_tie_decay(agents, decay_rate=0.02):
    """关系衰减：久不联系的关系自然下降"""
    for a in agents:
        for other_id in list(a.state.social_ties.keys()):
            tie = a.state.social_ties[other_id]
            if abs(tie) > 0.5:
                # 缓慢衰减
                if tie > 0:
                    a.state.social_ties[other_id] = max(0, tie - decay_rate)
                else:
                    a.state.social_ties[other_id] = min(0, tie + decay_rate)
