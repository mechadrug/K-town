import random,time,uuid
from typing import Dict,List,Optional
from .models import KnowledgeClaim,ClaimSource,ClaimScope

class KnowledgeEngine:
    def __init__(self):
        self.claims = {}
        self.agent_claims = {}

    def observe(self, agent_id, subject, claim_text, location):
        c=KnowledgeClaim(id=f"claim_{uuid.uuid4().hex[:8]}",subject=subject,claim=claim_text,source=ClaimSource.OBSERVATION,confidence=0.8,scope=ClaimScope.PRIVATE,created_by=agent_id,location=location)
        self.claims[c.id]=c
        self.agent_claims.setdefault(agent_id,[]).append(c.id)
        return c

    def propagate(self, claim_id, from_agent, to_agent, tie_strength=0.8):
        orig=self.claims.get(claim_id)
        if not orig: return None
        p=KnowledgeClaim(id=f"claim_{uuid.uuid4().hex[:8]}",subject=orig.subject,claim=orig.claim,source=ClaimSource.CONVERSATION,confidence=max(0.1,orig.confidence*tie_strength),scope=ClaimScope.PRIVATE,created_by=to_agent,location=orig.location)
        self.claims[p.id]=p
        self.agent_claims.setdefault(to_agent,[]).append(p.id)
        return p

    def dispute(self, claim_id, counter_id):
        c1,c2=self.claims.get(claim_id),self.claims.get(counter_id)
        if not c1 or not c2: return False
        if counter_id not in c1.contradicted_by: c1.contradicted_by.append(counter_id)
        if claim_id not in c2.contradicted_by: c2.contradicted_by.append(claim_id)
        return True

    def solidify(self, claim_id):
        c=self.claims.get(claim_id)
        if not c: return False
        c.solidified=True
        c.confidence=min(1.0,c.confidence+0.1)
        return True

    def rumor_spread(self, claim_id, from_agent, to_agents):
        orig=self.claims.get(claim_id)
        if not orig: return []
        results=[]
        for to in to_agents:
            varied=f"I heard that {orig.claim}" if random.random()<0.3 else orig.claim
            r=KnowledgeClaim(id=f"claim_rumor_{uuid.uuid4().hex[:8]}",subject=orig.subject,claim=varied,source=ClaimSource.RUMOR,confidence=orig.confidence*0.7,scope=ClaimScope.GROUP,created_by=to,location=orig.location)
            self.claims[r.id]=r
            self.agent_claims.setdefault(to,[]).append(r.id)
            results.append(r)
        return results

    def agent_knowledge(self, agent_id):
        return [self.claims[cid] for cid in self.agent_claims.get(agent_id,[]) if cid in self.claims]

    def to_dict(self):
        return {"total_claims":len(self.claims),"agent_claims":{k:len(v) for k,v in self.agent_claims.items()}}
