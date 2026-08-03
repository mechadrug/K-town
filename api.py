"""FastAPI + WebSocket API layer."""
import json,asyncio,os
from typing import Set
from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from fastapi.responses import JSONResponse,HTMLResponse
from world import World
from events import EventBus
from knowledge import KnowledgeEngine
from logger import Logger
from llm import LLMClient
from agent import populate_agents


def create_app(world,agents,bus,logger,knowledge,llm,tick_engine,ws_clients:Set[WebSocket]):
    app=FastAPI(title="K-town",version="0.2.0")
    base=os.path.dirname(os.path.abspath(__file__))

    @app.get("/")
    async def index():
        html_path=os.path.join(base,"templates","index.html")
        with open(html_path,"r",encoding="utf-8") as f:
            return HTMLResponse(f.read())

    @app.get("/api/state")
    async def get_state():
        return {"tick":world.state.tick,"weather":world.state.weather,"weather_name":world.get_weather_name(),"locations":world.to_dict()["locations"],"agents":[a.to_dict() for a in agents],"knowledge":knowledge.to_dict()}

    @app.get("/api/knowledge")
    async def get_knowledge():
        """获取所有知识列表"""
        claims = list(knowledge.claims.values())
        return {"total": len(claims), "claims": [{"id": c.id, "subject": c.subject, "claim": c.claim, "source": c.source.value, "confidence": c.confidence, "scope": c.scope.value, "created_by": c.created_by, "location": c.location, "created_at": c.created_at, "solidified": c.solidified, "version": c.version, "contradicted_by": c.contradicted_by} for c in claims]}

    @app.get("/api/knowledge/public")
    async def get_public_knowledge():
        """获取所有公共知识"""
        claims = knowledge.get_public_knowledge()
        return {"total": len(claims), "claims": [{"id": c.id, "subject": c.subject, "claim": c.claim, "source": c.source.value, "confidence": c.confidence, "created_by": c.created_by, "location": c.location, "created_at": c.created_at, "solidified": c.solidified} for c in claims]}

    @app.get("/api/knowledge/solidified")
    async def get_solidified_knowledge():
        """获取所有已固化的知识"""
        claims = knowledge.get_solidified_knowledge()
        return {"total": len(claims), "claims": [{"id": c.id, "subject": c.subject, "claim": c.claim, "source": c.source.value, "confidence": c.confidence, "created_by": c.created_by, "location": c.location, "created_at": c.created_at} for c in claims]}

    @app.get("/api/knowledge/search")
    async def search_knowledge(subject: str = None, location: str = None, agent_id: str = None):
        """搜索知识"""
        if subject:
            claims = knowledge.search_by_subject(subject)
        elif location:
            claims = knowledge.search_by_location(location)
        elif agent_id:
            claims = knowledge.search_by_agent(agent_id)
        else:
            claims = list(knowledge.claims.values())
        return {"total": len(claims), "claims": [{"id": c.id, "subject": c.subject, "claim": c.claim, "source": c.source.value, "confidence": c.confidence, "created_by": c.created_by, "location": c.location} for c in claims]}

    @app.get("/api/knowledge/{claim_id}")
    async def get_claim(claim_id: str):
        """获取指定知识的详细信息"""
        claim = knowledge.claims.get(claim_id)
        if not claim:
            return JSONResponse({"error": "knowledge not found"}, status_code=404)
        return {
            "id": claim.id,
            "subject": claim.subject,
            "claim": claim.claim,
            "source": claim.source.value,
            "confidence": claim.confidence,
            "scope": claim.scope.value,
            "created_by": claim.created_by,
            "location": claim.location,
            "created_at": claim.created_at,
            "solidified": claim.solidified,
            "version": claim.version,
            "contradicted_by": claim.contradicted_by,
            "version_history": knowledge.get_version_history(claim_id),
            "conflicting_claims": [{"id": c.id, "claim": c.claim, "confidence": c.confidence} for c in knowledge.get_conflicting_claims(claim_id)]
        }

    @app.post("/api/knowledge/solidify/{claim_id}")
    async def solidify_claim(claim_id: str):
        """手动固化知识"""
        success = knowledge.solidify(claim_id)
        if success:
            return {"status": "ok", "message": "知识已固化"}
        return JSONResponse({"error": "固化失败"}, status_code=400)

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id:str):
        for a in agents:
            if a.identity.id==agent_id:
                r=a.to_dict()
                r["knowledge"]=[{"id":k.id,"subject":k.subject,"claim":k.claim,"confidence":k.confidence} for k in knowledge.agent_knowledge(agent_id)]
                return r
        return JSONResponse({"error":"not found"},status_code=404)

    @app.get("/api/timeline")
    async def get_timeline(day:int=0):
        events=logger.query_world_events(200)
        if day>0:
            base=(day-1)*24
            events=[e for e in events if base<=e["tick"]<base+24]
        return events

    @app.get("/api/days")
    async def get_days():
        # 合并内存和数据库的历史摘要
        db_summaries = tick_engine.db.get_day_summaries()
        # 过滤掉已经过期的，保留最新的30天
        all_summaries = db_summaries + tick_engine.day_summaries
        # 去重，按day排序
        seen_days = set()
        unique_summaries = []
        for s in sorted(all_summaries, key=lambda x: x["day"]):
            if s["day"] not in seen_days:
                seen_days.add(s["day"])
                unique_summaries.append(s)
        return unique_summaries[-30:]

    @app.get("/api/day/{day}")
    async def get_day(day:int):
        # 先查内存
        for s in tick_engine.day_summaries:
            if s["day"] == day:
                return s
        # 再查数据库
        db_summaries = tick_engine.db.get_day_summaries()
        for s in db_summaries:
            if s["day"] == day:
                return s
        return JSONResponse({"error":"day not found"},status_code=404)

    @app.get("/api/history/{day}")
    async def get_history(day:int):
        """获取指定日期的完整历史状态"""
        # 获取每日摘要
        summary = None
        for s in tick_engine.day_summaries:
            if s["day"] == day:
                summary = s
                break
        if not summary:
            db_summaries = tick_engine.db.get_day_summaries()
            for s in db_summaries:
                if s["day"] == day:
                    summary = s
                    break
        # 获取Agent日志
        agent_logs = tick_engine.db.get_agent_logs(day)
        # 获取世界快照
        snapshot = tick_engine.db.get_world_snapshot(day)
        # 获取事件时间线
        events = tick_engine.db.get_events(day)
        return {
            "summary": summary,
            "agent_logs": agent_logs,
            "snapshot": snapshot,
            "events": events
        }

    @app.get("/api/replay")
    async def get_replay(start_day:int=1, end_day:int=5):
        """获取指定时间范围的历史数据，用于回放"""
        if start_day < 1 or end_day < start_day:
            return JSONResponse({"error":"invalid day range"},status_code=400)
        days = []
        for day in range(start_day, end_day + 1):
            day_data = await get_history(day)
            days.append(day_data)
        return {"start_day": start_day, "end_day": end_day, "days": days}

    @app.get("/api/logs/decisions")
    async def get_decisions(n:int=50):
        return logger.query_decisions(n)

    @app.get("/api/logs/agents/{day}")
    async def get_agent_logs(day:int, agent_id:str = None):
        """获取指定日期的Agent行为日志"""
        return tick_engine.db.get_agent_logs(day, agent_id)

    @app.post("/api/player/action")
    async def player_action(action:dict):
        t=action.get("type","")
        aid=action.get("agent_id","agent_player")
        tgt=action.get("target","")
        if t=="move":
            for a in agents:
                if a.identity.id==aid:
                    world.remove_agent_from_location(a.identity.id,a.state.location)
                    a.state.location=tgt
                    world.add_agent_to_location(a.identity.id,tgt)
                    break
        elif t=="claim":
            subj=action.get("subject","observation")
            claim=action.get("claim","")
            for a in agents:
                if a.identity.id==aid:
                    knowledge.observe(aid,subj,claim,a.state.location)
                    break
        return {"status":"ok"}

    @app.post("/api/reset")
    async def reset_simulation():
        """重置模拟，清空所有数据"""
        # 清空数据库
        tick_engine.db.reset()
        # 清空内存数据
        tick_engine.day_summaries = []
        tick_engine.current_day = 1
        tick_engine.current_day_events = []
        # 重新初始化所有模块
        world.__init__()
        bus.__init__()
        knowledge.__init__()
        logger.__init__()
        agents.clear()
        new_agents = populate_agents()
        agents.extend(new_agents)
        for a in new_agents:
            world.add_agent_to_location(a.identity.id, a.state.location)
        # 重新生成第一天事件
        agent_ids = [a.identity.id for a in agents]
        tick_engine.scheduler.generate_daily_schedule(1, agent_ids)
        return {"status":"ok", "message":"模拟已重置"}

    @app.websocket("/ws")
    async def ws_endpoint(websocket:WebSocket):
        await websocket.accept()
        ws_clients.add(websocket)
        try:
            # 发送当前状态和历史摘要
            await websocket.send_json({
                "type": "state",
                "data": {
                    "tick": world.state.tick,
                    "weather": world.state.weather,
                    "weather_name": world.get_weather_name(),
                    "agents": [a.to_dict() for a in agents],
                    "locations": world.to_dict()["locations"],
                    "knowledge": knowledge.to_dict()
                }
            })
            # 发送历史每日摘要
            for summary in tick_engine.day_summaries[-10:]:
                await websocket.send_json({
                    "type": "day_summary",
                    "data": summary
                })
            while True:
                raw=await websocket.receive_text()
                try:
                    msg=json.loads(raw)
                    if msg.get("type")=="player_action":
                        await player_action(msg.get("action",{}))
                        await websocket.send_json({"type":"ack"})
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            ws_clients.discard(websocket)

    return app
