"""FastAPI + WebSocket API layer."""
import json,asyncio,os
from typing import Set
from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from fastapi.responses import JSONResponse,HTMLResponse
from fastapi.staticfiles import StaticFiles
from .world import World
from .events import EventBus
from .knowledge import KnowledgeEngine
from .logger import Logger
from .llm import LLMClient

def create_app(world,agents,bus,logger,knowledge,llm,tick_engine):
    app=FastAPI(title="K-town",version="0.1.0")
    clients:Set[WebSocket]=set()
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
        return tick_engine.day_summaries

    @app.get("/api/day/{day}")
    async def get_day(day:int):
        if 1<=day<=len(tick_engine.day_summaries):
            return tick_engine.day_summaries[day-1]
        return JSONResponse({"error":"day not found"},status_code=404)

    @app.get("/api/logs/decisions")
    async def get_decisions(n:int=50):
        return logger.query_decisions(n)

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
        clients.add(websocket)
        try:
            await websocket.send_json({"type":"state","data":{
                "tick":world.state.tick,"weather":world.state.weather,
                "agents":[a.to_dict() for a in agents],
                "locations":world.to_dict()["locations"],
                "knowledge":knowledge.to_dict()
            }})
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
            clients.discard(websocket)

    return app