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


def create_app(world,agents,bus,logger,knowledge,llm,tick_engine,ws_clients:Set[WebSocket]):
    app=FastAPI(title="K-town",version="0.1.0")
    base=os.path.dirname(os.path.abspath(__file__))

    @app.get("/")
    async def index():
        html_path=os.path.join(base,"templates","index.html")
        with open(html_path,"r",encoding="utf-8") as f:
            return HTMLResponse(f.read())

    @app.get("/api/state")
    async def get_state():
        return {"tick":world.state.tick,"weather":world.state.weather,"locations":world.to_dict()["locations"],"agents":[a.to_dict() for a in agents],"knowledge":knowledge.to_dict()}

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

    @app.get("/api/logs/decisions")
    async def get_decisions(n:int=50):
        return logger.query_decisions(n)

    @app.get("/api/logs/agents/{day}")
    async def get_agent_logs(day:int, agent_id:str = None):
        """获取指定日期的Agent行为日志"""
        return tick_engine.db.get_agent_logs(day, agent_id)

    @app.get("/api/snapshots/{day}")
    async def get_snapshot(day:int):
        """获取指定日期的世界状态快照"""
        snapshot = tick_engine.db.get_world_snapshot(day)
        if snapshot:
            return snapshot
        return JSONResponse({"error":"snapshot not found"},status_code=404)

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

