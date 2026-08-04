"""知识引擎模块 v2.0"""
import random,time,uuid
from typing import Dict,List,Optional,Any
from models import KnowledgeClaim,ClaimSource,ClaimScope

class KnowledgeEngine:
    def __init__(self):
        self.claims = {}  # 知识ID -> 知识对象
        self.agent_claims = {}  # Agent ID -> 知识ID列表
        self.subject_index = {}  # 主题 -> 知识ID列表
        self.location_index = {}  # 位置 -> 知识ID列表
        self.version_history = {}  # 知识ID -> 历史版本列表

    def observe(self, agent_id, subject, claim_text, location, confidence=0.6):
        """观察创建新知识，自动检测冲突"""
        conflicting = self._find_conflicting_claims(subject, claim_text)
        c = KnowledgeClaim(
            id=f"claim_{uuid.uuid4().hex[:8]}",
            subject=subject,
            claim=claim_text,
            source=ClaimSource.OBSERVATION,
            confidence=confidence,
            scope=ClaimScope.PRIVATE,
            created_by=agent_id,
            location=location
        )
        self.claims[c.id] = c
        self.agent_claims.setdefault(agent_id, []).append(c.id)
        self._update_index(c)
        if conflicting:
            for conflict_id in conflicting:
                self.dispute(c.id, conflict_id)
        return c

    def observe_with_action(self, agent_id, subject, claim_text, location,
                            confidence=0.6, action_type="", action_target="",
                            emotional_valence=0.0):
        """创建带有行为影响的新知识"""
        c = KnowledgeClaim(
            id=f"claim_{uuid.uuid4().hex[:8]}",
            subject=subject,
            claim=claim_text,
            source=ClaimSource.OBSERVATION,
            confidence=confidence,
            scope=ClaimScope.PRIVATE,
            created_by=agent_id,
            location=location,
            actionable=bool(action_type),
            action_type=action_type,
            action_target=action_target,
            emotional_valence=emotional_valence
        )
        self.claims[c.id] = c
        self.agent_claims.setdefault(agent_id, []).append(c.id)
        self._update_index(c)
        return c

    def get_actionable_knowledge(self, agent_id: str) -> List[KnowledgeClaim]:
        """获取Agent持有的所有可行动知识，按置信度排序"""
        claims = self.agent_knowledge(agent_id)
        actionable = [c for c in claims if c.actionable and c.confidence > 0.4]
        return sorted(actionable, key=lambda c: c.confidence, reverse=True)

    def derive_action_from_claim(self, claim: KnowledgeClaim) -> Optional[Dict[str, Any]]:
        """从知识推导出具体行动建议"""
        if claim.action_type == "avoid_location":
            return {
                "type": "avoid",
                "target": claim.action_target,
                "reason": claim.claim,
                "priority": int(claim.confidence * abs(claim.emotional_valence) * 10)
            }
        elif claim.action_type == "seek_resource":
            return {
                "type": "seek",
                "target": claim.action_target,
                "reason": claim.claim,
                "priority": int(claim.confidence * 8)
            }
        elif claim.action_type == "trust_agent":
            return {
                "type": "befriend",
                "target": claim.action_target,
                "reason": claim.claim,
                "priority": int(claim.confidence * 6)
            }
        elif claim.action_type == "explore":
            return {
                "type": "investigate",
                "target": claim.action_target,
                "reason": claim.claim,
                "priority": int(claim.confidence * 7)
            }
        elif claim.action_type == "danger_warning":
            return {
                "type": "warn_others",
                "target": claim.action_target,
                "reason": claim.claim,
                "priority": int(claim.confidence * 9)
            }
        return None

    def derive_actions_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """为Agent推导所有知识驱动的行动建议"""
        actionable = self.get_actionable_knowledge(agent_id)
        actions = []
        for claim in actionable:
            action = self.derive_action_from_claim(claim)
            if action:
                action["knowledge_id"] = claim.id
                action["knowledge_confidence"] = claim.confidence
                actions.append(action)
        return sorted(actions, key=lambda a: a.get("priority", 0), reverse=True)

    def propagate(self, claim_id, from_agent, to_agent, tie_strength=0.8):
        """传播知识，置信度会衰减"""
        orig = self.claims.get(claim_id)
        if not orig:
            return None
        p = KnowledgeClaim(
            id=f"claim_{uuid.uuid4().hex[:8]}",
            subject=orig.subject,
            claim=orig.claim,
            source=ClaimSource.CONVERSATION,
            confidence=max(0.1, orig.confidence * tie_strength),
            scope=ClaimScope.PRIVATE,
            created_by=to_agent,
            location=orig.location,
            actionable=orig.actionable,
            action_type=orig.action_type,
            action_target=orig.action_target,
            emotional_valence=orig.emotional_valence * 0.9  # 情感衰减
        )
        self.claims[p.id] = p
        self.agent_claims.setdefault(to_agent, []).append(p.id)
        self._update_index(p)
        return p

    def dispute(self, claim_id, counter_id):
        """质疑知识，互相标记为冲突"""
        c1 = self.claims.get(claim_id)
        c2 = self.claims.get(counter_id)
        if not c1 or not c2:
            return False
        if counter_id not in c1.contradicted_by:
            c1.contradicted_by.append(counter_id)
        if claim_id not in c2.contradicted_by:
            c2.contradicted_by.append(claim_id)
        c1.confidence = max(0.1, c1.confidence - 0.1)
        c2.confidence = max(0.1, c2.confidence - 0.1)
        return True

    def solidify(self, claim_id):
        """固化知识，变为公共知识"""
        c = self.claims.get(claim_id)
        if not c:
            return False
        c.solidified = True
        c.confidence = min(1.0, c.confidence + 0.1)
        c.scope = ClaimScope.PUBLIC
        return True

    def auto_solidify(self):
        """自动固化置信度超过0.9的知识"""
        solidified = []
        for claim in self.claims.values():
            if not claim.solidified and claim.confidence >= 0.9:
                self.solidify(claim.id)
                solidified.append(claim.id)
        return solidified

    def rumor_spread(self, claim_id, from_agent, to_agents):
        """传闻传播，置信度大幅衰减，30%概率变形"""
        orig = self.claims.get(claim_id)
        if not orig:
            return []
        results = []
        for to in to_agents:
            varied = f"听说{orig.claim}" if random.random() < 0.3 else orig.claim
            r = KnowledgeClaim(
                id=f"claim_rumor_{uuid.uuid4().hex[:8]}",
                subject=orig.subject,
                claim=varied,
                source=ClaimSource.RUMOR,
                confidence=orig.confidence * 0.6,
                scope=ClaimScope.GROUP,
                created_by=to,
                location=orig.location,
                actionable=orig.actionable,
                action_type=orig.action_type,
                action_target=orig.action_target,
                emotional_valence=orig.emotional_valence * 0.7
            )
            self.claims[r.id] = r
            self.agent_claims.setdefault(to, []).append(r.id)
            self._update_index(r)
            results.append(r)
        return results

    def update_claim(self, claim_id, new_claim_text, new_confidence=None):
        """更新知识，保留历史版本"""
        c = self.claims.get(claim_id)
        if not c:
            return False
        if claim_id not in self.version_history:
            self.version_history[claim_id] = []
        self.version_history[claim_id].append({
            "claim": c.claim,
            "confidence": c.confidence,
            "version": c.version,
            "updated_at": time.time()
        })
        c.claim = new_claim_text
        c.version += 1
        if new_confidence is not None:
            c.confidence = min(1.0, max(0.1, new_confidence))
        return True

    def agent_knowledge(self, agent_id):
        """获取Agent的所有知识"""
        return [self.claims[cid] for cid in self.agent_claims.get(agent_id, []) if cid in self.claims]

    def get_public_knowledge(self):
        """获取所有公共知识"""
        return [c for c in self.claims.values() if c.scope == ClaimScope.PUBLIC]

    def get_solidified_knowledge(self):
        """获取所有已固化的知识"""
        return [c for c in self.claims.values() if c.solidified]

    def search_by_subject(self, subject):
        """按主题搜索知识"""
        claim_ids = self.subject_index.get(subject, [])
        return [self.claims[cid] for cid in claim_ids if cid in self.claims]

    def search_by_location(self, location):
        """按位置搜索知识"""
        claim_ids = self.location_index.get(location, [])
        return [self.claims[cid] for cid in claim_ids if cid in self.claims]

    def search_by_agent(self, agent_id):
        """按创建者搜索知识"""
        return self.agent_knowledge(agent_id)

    def get_conflicting_claims(self, claim_id):
        """获取与指定知识冲突的所有知识"""
        c = self.claims.get(claim_id)
        if not c:
            return []
        return [self.claims[cid] for cid in c.contradicted_by if cid in self.claims]

    def get_version_history(self, claim_id):
        """获取知识的历史版本"""
        return self.version_history.get(claim_id, [])

    def _find_conflicting_claims(self, subject, claim_text):
        """查找与指定内容冲突的知识（相同主题但内容不同）"""
        conflicts = []
        claim_ids = self.subject_index.get(subject, [])
        for cid in claim_ids:
            c = self.claims.get(cid)
            if c and c.claim != claim_text:
                conflicts.append(cid)
        return conflicts

    def _update_index(self, claim):
        """更新索引"""
        if claim.subject not in self.subject_index:
            self.subject_index[claim.subject] = []
        if claim.id not in self.subject_index[claim.subject]:
            self.subject_index[claim.subject].append(claim.id)
        if claim.location not in self.location_index:
            self.location_index[claim.location] = []
        if claim.id not in self.location_index[claim.location]:
            self.location_index[claim.location].append(claim.id)

    def to_dict(self):
        """返回统计信息"""
        return {
            "total_claims": len(self.claims),
            "agent_claims": {k: len(v) for k, v in self.agent_claims.items()},
            "public_claims": len(self.get_public_knowledge()),
            "solidified_claims": len(self.get_solidified_knowledge())
        }
    
    def reset(self):
        """重置知识引擎"""
        self.claims = {}
        self.agent_claims = {}
        self.subject_index = {}
        self.location_index = {}
        self.version_history = {}
