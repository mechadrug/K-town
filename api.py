"""FastAPI + WebSocket API layer."""

import json,asyncio,os

from typing import Set

from fastapi import FastAPI,WebSocket,WebSocketDisconnect

from fastapi.responses import JSONResponse,HTMLResponse

from fastapi.staticfiles import StaticFiles

from world import World

from events import EventBus

from knowledge import KnowledgeEngine

from llm import LLMClient

from agent import populate_agents

from models import Event, EventType, PlayerAction, TradeOffer, Mood

from actions import Action
from requests import seed_initial_requests

_LOCATION_CN = {"square": "广场", "workshop": "工坊", "wilderness": "荒野", "school": "学校", "mine": "矿洞"}
_MOOD_CN = {"happy": "轻松", "neutral": "平静", "anxious": "焦虑", "angry": "恼火", "sad": "低落"}


def _request_payload(request, agents):
    return {
        "id": request.id, "requester_id": request.requester_id,
        "requester_name": next((a.identity.name for a in agents if a.identity.id == request.requester_id), request.requester_id),
        "location": request.location, "location_name": _LOCATION_CN.get(request.location, request.location),
        "title": request.title, "situation": request.situation, "deadline": request.deadline,
        "status": request.status, "completed_day": request.completed_day,
        "chapter_id": getattr(request, "chapter_id", "week_1_rain"),
        "progress": request.progress, "max_progress": request.max_progress,
        "used_options": list(request.used_options), "visible_risks": list(request.visible_risks),
        "next_day_observations": list(request.next_day_observations),
        "observed_next_day_observations": list(request.observed_next_day_observations),
        "options": [{
            "id": option.id, "label": option.label, "requires": option.requires,
            "requires_cn": option.requires_cn, "cost_ap": option.cost_ap,
            "cost_hours": option.cost_hours, "result_desc": option.result_desc,
            "next_observation": option.next_observation, "effect": option.effect,
            "progress_delta": option.progress_delta, "closes_request": option.closes_request,
            "visible_risk": option.visible_risk, "next_day_observation": option.next_day_observation,
        } for option in request.options],
    }


def _agent_profile_payload(agent, world, requests):
    state = agent.state
    emotions = state.emotions or {}
    request = next((item for item in requests if item["requester_id"] == agent.identity.id and item["status"] == "active"), None)
    if request:
        reason = f"{request['title']}：{request['situation']}"
    elif world.state.weather == "rainy" and state.location == "workshop":
        reason = "暴雨让工坊的屋檐和炉台都更难照看。"
    elif state.current_task:
        reason = f"正在处理“{state.current_task.description}”。"
    elif emotions.get("anxiety", 50) >= 65:
        reason = "最近听到的消息还没有得到确认。"
    elif emotions.get("sadness", 50) >= 65:
        reason = "连续几天的疲惫让他暂时不想和人打交道。"
    else:
        reason = "眼下没有新的压力，按自己的节奏生活。"
    dominant = max(emotions, key=emotions.get) if emotions else "neutral"
    tendency = {"anxiety": "先确认风险，再决定是否答应别人。", "anger": "倾向把手头的事做完，不喜欢被打断。", "sadness": "更愿意独自待着，只有熟人来才会松口。", "joy": "愿意找人商量，也更容易接受临时的帮助。"}.get(dominant, "按自己的目标稳稳推进。")
    responses = []
    if request:
        responses = [{"request_id": request["id"], "request_title": request["title"], "location": request["location"], "option_id": option["id"], "label": option["label"], "cost_ap": option["cost_ap"], "cost_hours": option["cost_hours"], "available_here": state.location == request["location"]} for option in request["options"]]
    return {
        "current_task": state.current_task.description if state.current_task else f"在{_LOCATION_CN.get(state.location, state.location)}按自己的节奏生活",
        "feeling": _MOOD_CN.get(state.mood.value, "平静"), "mood": state.mood.value,
        "reason": reason, "tendency": tendency, "responses": responses,
        "emotion_detail": {key: round(emotions.get(key, 50), 1) for key in ("joy", "anxiety", "anger", "sadness")},
    }


def _today_threads(requests_payload, world, crisis_items=None, campaign=None):
    active_count = sum(1 for item in requests_payload if item["status"] == "active")
    request_items = [{
        "id": item["id"], "title": item["title"], "requester": item["requester_name"],
        "location": item["location"], "location_name": item["location_name"],
        "detail": item["situation"], "status": item["status"], "deadline": item["deadline"],
        "options_count": len(item["options"]),
        "action": {
            "kind": "request", "request_id": item["id"],
            "label": "打开请求详情" if item["status"] == "active" else "查看请求结果",
        },
    } for item in requests_payload]
    roof = world.workshop_roof_status()
    forecast_day = world.state.rain_forecast_day or 3
    pressure = {"id": "rain_pressure", "title": f"暴雨预告：第{forecast_day}天", "detail": f"工坊屋顶现在是“{roof['label']}”。{roof['description']}", "location": "workshop", "location_name": "工坊", "status": "urgent" if world.state.weather == "rainy" else "watch", "action": {"kind": "move", "target": "workshop", "label": "去工坊看看"}, "next_observation": "临时遮雨会保住当天炉火，但次日仍可能滴漏。" if roof["stage"] == 1 else "把时间留给正式修缮，明天会看见屋顶是否稳住。"}
    rumor_text = {"unconfirmed": "旧矿道可能有塌方，暂时还没人能证明真假。", "circulating": "旧矿道的消息正在广场传开，罗文建议谨慎通行。", "needs_verification": "不同居民说法不一，传闻已被标成“待核实”。", "marked": "旧矿道路口已经挂上“待确认，谨慎通行”的路标。"}.get(world.state.mine_rumor_status, "旧矿道的消息还没有定论。")
    clue = {"id": "mine_rumor", "title": "旧矿道传闻", "detail": rumor_text, "location": "mine", "location_name": "矿洞", "status": world.state.mine_rumor_status, "confidence": round(world.state.mine_rumor_confidence * 100), "action": {"kind": "move", "target": "mine", "label": "去矿洞核实"}, "next_observation": "有人相信它之后，居民会改变自己的路线。"}
    pressure_items = [pressure]
    if campaign:
        pressure_items.insert(0, {
            "id": "campaign_pressure",
            "title": f"第{campaign['week']}周 · {campaign['title']}",
            "detail": f"{campaign['pressure']} 当前目标：{campaign['objective']}",
            "status": "chapter",
            "next_observation": campaign.get("next_chapter", {}).get("title") if campaign.get("next_chapter") else "这一章正在走向结算。",
            "action": {"kind": "campaign", "label": "查看本周章程"},
        })
    for crisis in crisis_items or []:
        pressure_items.append({
            "id": f"crisis_{crisis['id']}",
            "title": "正在发生的危机",
            "detail": crisis["desc"],
            "status": "urgent",
            "progress": crisis["progress"],
            "target": crisis["target"],
            "days_remaining": crisis["days_remaining"],
            "action": {
                "kind": "crisis", "crisis_id": crisis["id"],
                "label": "今天帮忙（3 AP）",
            },
        })
    return [
        {"id": "resident_requests", "kind": "requests", "title": "居民请求", "detail": f"今天有{active_count}位居民在等回应；每一条都会占用不同的时间。", "items": request_items},
        {"id": "town_pressure", "kind": "pressure", "title": "镇上压力", "detail": "天气会把选择变成明天的场景。", "items": pressure_items},
        {"id": "follow_up_clue", "kind": "clue", "title": "可跟进线索", "detail": "你可以相信、转述，也可以亲自去确认。", "items": [clue]},
    ]


def _public_agent(agent, world, requests):
    payload = agent.to_dict()
    payload["profile"] = _agent_profile_payload(agent, world, requests)
    return payload





def create_app(world,agents,bus,logger,knowledge,llm,tick_engine,ws_clients:Set[WebSocket],dialogue_sys=None):

    app=FastAPI(title="K-town",version="0.2.0")

    def _action_payload(ar) -> dict:
        """将统一 resolver 结果转换成 REST/WS 共用的可读契约。"""
        return {
            "status": "ok" if ar.accepted else "error",
            "result": ar.result,
            "accepted": ar.accepted,
            "cost": ar.cost,
            "hours": ar.hours,
            "action_id": ar.action_id,
            "changes": [c.__dict__ for c in ar.changes],
            "story_beats": list(ar.story_beats),
            "next_observation": ar.next_observation,
            "error_code": ar.error_code,
            "request_id": ar.request_id,
            "details": dict(getattr(ar, "details", {}) or {}),
        }

    def _active_crisis_payloads() -> list[dict]:
        return [{
            "id": index, "type": crisis.crisis_type, "desc": crisis.desc,
            "progress": crisis.progress, "target": crisis.target,
            "days_remaining": crisis.days_remaining, "active": crisis.active,
            "outcome": crisis.outcome, "interventions": crisis.interventions,
        } for index, crisis in enumerate(tick_engine.crises) if crisis.active]

    base=os.path.dirname(os.path.abspath(__file__))

    static_dir=os.path.join(base,'static')

    if os.path.exists(static_dir):

        app.mount('/static',StaticFiles(directory=static_dir),name='static')

    # 挂载静态文件

    def _build_state_payload() -> dict:
        """构建前端全量状态载荷：/api/state 与 WS 共用同一来源，避免字段漂移"""
        requests_payload = [_request_payload(request, agents) for request in getattr(tick_engine, "requests", [])]
        public_agents = [_public_agent(agent, world, requests_payload) for agent in agents]
        player = next((payload for payload in public_agents if payload["role"] == "player"), None)
        return {
            "tick": world.state.tick,
            "weather": world.state.weather,
            "weather_name": world.get_weather_name(),
            "locations": world.to_dict()["locations"],
            "agents": public_agents,
            "knowledge_claims": [
                {"id": c.id, "subject": c.subject, "claim": c.claim, "source": c.source.value,
                 "confidence": c.confidence, "created_by": c.created_by, "location": c.location,
                 "solidified": c.solidified} for c in knowledge.claims.values()
            ],
            "prices": world.prices,
            "resources": world.resources,
            "price_history": {k: v[-7:] for k, v in world.price_history.items()},
            "events": [{"type": e.get("type", ""), "action": e.get("action", e.get("payload", "")), "tick": e.get("tick", 0)} for e in tick_engine.current_day_events[-20:]],
            "knowledge": knowledge.to_dict(),
            "player": player,
            "trade_offers": [{"from": t.from_agent, "to": t.to_agent, "item": t.item, "price": t.price, "status": t.status} for t in world.state.trade_offers],
            "factions": tick_engine.faction_system.factions,
            "location_levels": world.state.location_levels,
            "workshop_roof": world.workshop_roof_status(),
            "rain_forecast": {"day": world.state.rain_forecast_day,
                               "announced": world.state.rain_forecast_announced,
                               "weather": "rainy"},
            "mine_rumor": {"status": world.state.mine_rumor_status,
                           "confidence": world.state.mine_rumor_confidence},
            "lantern_fair_preparedness": world.state.lantern_fair_preparedness,
            "campaign_markers": dict(getattr(world.state, "campaign_markers", {})),
            "campaign": tick_engine.campaign.payload(tick_engine.current_day),
            "crises": _active_crisis_payloads(),
            # 今日三条线：请求、镇上压力、可跟进线索。原始请求仍在 requests
            # 中供详情使用；这个摘要让首屏不必先打开任务 Tab。
            "requests": requests_payload,
            "today_threads": _today_threads(
                requests_payload, world, _active_crisis_payloads(),
                tick_engine.campaign.payload(tick_engine.current_day),
            ),
            # 长期目标线（v4 §5）：重建进度 + 身世之谜进度
            "progress": {
                "rebuild": {
                    "upgrades_done": tick_engine._upgrades_done,
                    "levels": world.state.location_levels,
                    "next_threshold": 100 * (tick_engine._upgrades_done + 1) ** 2,
                    "total_gold": sum(a.state.gold for a in agents),
                },
                "lore": {
                    "fragments": sorted(getattr(tick_engine, 'lore_fragments', set())),
                    "collected": len(getattr(tick_engine, 'lore_fragments', set())),
                    "total": tick_engine.LORE_TOTAL_FRAGMENTS,
                    "unlocked": getattr(tick_engine, 'lore_unlocked', []),
                },
            }
        }

    def _dialogue_context(target) -> dict:
        """构建对话语境：心情 + 正在做的事（决定话题与后果）"""
        return {
            "mood": target.state.mood.value,
            "current_task": target.state.current_task.description if target.state.current_task else None,
        }

    def _shift_mood(target, direction: int):
        """按情绪梯度移动一格心情（+1 变好 / -1 变差）"""
        ladder = ["sad", "angry", "anxious", "neutral", "happy"]
        current = target.state.mood.value
        idx = ladder.index(current) if current in ladder else 3
        new_idx = max(0, min(len(ladder) - 1, idx + direction))
        target.state.mood = Mood(ladder[new_idx])

    @app.get("/")

    async def index():

        html_path=os.path.join(base,"templates","index-v2.html")

        with open(html_path,"r",encoding="utf-8") as f:

            return HTMLResponse(f.read())



    @app.get("/api/state")

    async def get_state():

        return _build_state_payload()



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

                request_payload = [_request_payload(request, agents) for request in getattr(tick_engine, "requests", [])]
                r=_public_agent(a, world, request_payload)

                r["knowledge"]=[{"id":k.id,"subject":k.subject,"claim":k.claim,"confidence":k.confidence} for k in knowledge.agent_knowledge(agent_id)]

                return r

        return JSONResponse({"error":"not found"},status_code=404)



    @app.get("/api/timeline")

    async def get_timeline(day:int=0):

        events=logger.query_world_events(200)

        if day>0:

            base=(day-1)*20

            events=[e for e in events if base<=e["tick"]<base+20]

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



    @app.get("/api/logs/player")

    async def get_player_logs(n:int=50):

        """获取玩家操作日志"""

        return logger.query_player_actions(n)



    @app.post("/api/player/action")

    async def player_action(action:dict):

        """玩家行动：与 NPC 共用同一动作执行管线（tick_engine._handle_action）。"""
        t = action.get("type", "")
        aid = action.get("agent_id", "agent_player")
        # 客户端只能代表玩家；NPC 的自主动作由 tick 决策循环触发。
        if aid != "agent_player":
            return {"status": "error", "result": "只能由玩家身份发起行动", "error_code": "actor_forbidden"}
        tgt = action.get("target", action.get("destination", ""))

        # 归一化动作名（兼容旧前端叫法）
        if t in ("add_claim", "add_knowledge", "addKnowledge", "claim"):
            t = "add_claim"

        # 定位执行者
        actor = None
        for a in agents:
            if a.identity.id == aid:
                actor = a
                break
        if actor is None:
            return {"status": "error", "result": "找不到执行者"}

        # 每日领悟：把思考写进小镇的记忆（0 AP，每日一次，随时可提交）。
        # 若触及隐藏剧情的关键词，封印松动——领悟技能、想起记忆碎片。
        if t == "add_claim":
            claim_text = action.get("claim", "")
            if not claim_text:
                result = "思考内容为空"
            elif tick_engine._insight_day == tick_engine.current_day:
                return {"status": "error", "result": "今日的思考已经交出去了。明日再悟吧。"}
            else:
                tick_engine._insight_day = tick_engine.current_day
                knowledge.observe("agent_player", "思考", claim_text, actor.state.location)
                result = f"你把一段想法写进了小镇的记忆：{claim_text}"
                insight = tick_engine._check_insight(actor, claim_text)
                if insight:
                    result = insight
                # 每日目标：提交思考推进"传播知识"目标
                if getattr(tick_engine, "quest_engine", None):
                    tick_engine.quest_engine.update_progress(actor, action_type="add_claim")
            logger.log_player_action(PlayerAction(tick=tick_engine.world.state.tick, action_type=t, payload=action, result=result))
            tick_engine.persist_game_state()
            return {"status": "ok", "result": result, "accepted": True, "cost": 0,
                    "hours": 0, "action_id": f"insight_{tick_engine.current_day}",
                    "changes": [], "story_beats": [result],
                    "next_observation": "明天，镇上的人可能会回应这段想法。",
                    "error_code": None}

        # === v5 统一结算：所有常规动作经 ActionResolver（校验/扣费/推进单一入口）===
        if t == "reset":
            # 仅开发用：玩家首屏已无入口，保留 API 供调试
            return await reset_simulation()
        elif t in ("work", "rest", "investigate", "move", "talk", "trade", "observe", "sleep"):
            # 常规动作：统一走 ActionResolver（校验/扣费/推进单一入口）
            ar = tick_engine.resolver.resolve(actor, Action(
                actor_id=aid, kind=t,
                target_id=tgt if t in ("talk", "trade", "conflict") else "",
                target_location=tgt if t == "move" else "",
                payload={},
            ))
            await tick_engine.wait_caught_up()
            return _action_payload(ar)
        elif t == "request_respond":
            ar = tick_engine.resolver.resolve(actor, Action(
                actor_id=aid, kind="request_respond",
                payload={"request_id": action.get("request_id", ""), "option": action.get("option", "")},
            ))
            await tick_engine.wait_caught_up()
            return _action_payload(ar)
        elif t == "trade_offer":
            item = action.get("item", "")
            price = action.get("price", 0)
            target = tgt
            if target and item and price > 0:
                ar = tick_engine.resolver.resolve(actor, Action(
                    actor_id=aid, kind="trade",
                    target_id=target, payload={},
                ))
                await tick_engine.wait_caught_up()
                if not ar.accepted:
                    return {"status": "error", "result": ar.result}
                offer = TradeOffer(from_agent=aid, to_agent=target, item=item, price=price)
                world.state.trade_offers.append(offer)
                # NPC 当场响应（基于当前市价判断合理价，避免价格波动导致误判）
                tick_engine._process_npc_trades()
                tick_engine.persist_game_state()
                result = f"向{target}发起了{item}的交易请求，价格{price}金币"
                if offer.status == "accepted":
                    result = f"{target}接受了你的{item}交易（{price}金币）"
                elif offer.status == "rejected":
                    result = f"{target}拒绝了你的{item}交易（出价不合理或对方买不起）"
            else:
                result = "交易参数错误"
        elif t == "accept_trade":
            # 免费动作（0 AP / 0 小时）：不推进时间，无作弊空间
            offer_id = action.get("offer_id", -1)
            if 0 <= offer_id < len(world.state.trade_offers):
                offer = world.state.trade_offers[offer_id]
                for a in agents:
                    if a.identity.id == offer.to_agent:
                        if a.state.gold >= offer.price:
                            a.state.gold -= offer.price
                            a.state.inventory.append(offer.item)
                            offer.status = "accepted"
                            result = f"接受了{offer.from_agent}的交易，花费{offer.price}金币购买{offer.item}"
                        else:
                            result = "金币不足，无法完成交易"
                        break
            else:
                result = "交易不存在"
        else:
            result = f"未知操作：{t}"

        # 记录玩家操作
        player_action = PlayerAction(tick=tick_engine.world.state.tick, action_type=t, payload=action, result=result)
        logger.log_player_action(player_action)
        tick_engine.persist_game_state()

        return {"status": "error" if "AP不足" in result else "ok", "result": result}



    @app.post("/api/reset")

    async def reset_simulation():

        """重置模拟，清空所有数据"""

        # 清空数据库

        tick_engine.db.reset()

        # 清空内存数据

        tick_engine.day_summaries = []

        tick_engine.current_day = 1

        tick_engine.current_day_events = []
        tick_engine.current_day_decisions = []
        tick_engine.daily_agent_logs = {}
        tick_engine.crises = []
        tick_engine._pending_advance = 0
        tick_engine._is_stepping = False
        tick_engine._pending_snapshots = []
        tick_engine._tick_since_last_db_write = 0
        tick_engine._insight_day = 0
        tick_engine._upgrades_done = 0
        tick_engine._llm_calls_today = 0
        tick_engine._llm_cache = {}
        tick_engine.prev_agent_states = []
        tick_engine.prev_knowledge_count = 0
        tick_engine.prev_total_gold = 0
        tick_engine.restored_from_save = False
        tick_engine.faction_system.factions = {}
        tick_engine.faction_system.next_faction_id = 1
        tick_engine.lore_fragments = set()
        tick_engine.lore_clues = {}
        tick_engine.lore_unlocked = []
        tick_engine.campaign.ensure_new_game()

        # 重新初始化所有模块

        world.__init__()

        bus.__init__()

        knowledge.__init__()

        knowledge.persistence = logger

        agents.clear()

        new_agents = populate_agents()

        agents.extend(new_agents)

        for a in new_agents:

            world.add_agent_to_location(a.identity.id, a.state.location)

        # 请求状态和 resolver 的序列号也属于新游戏状态。
        tick_engine.requests = seed_initial_requests()
        tick_engine.resolver.agents = agents
        tick_engine.resolver.world = world
        tick_engine.resolver.knowledge = knowledge
        tick_engine.resolver._action_sequence = 0
        tick_engine.daily_agent_logs = {a.identity.id: [] for a in agents}

        # 重新生成第一天事件

        agent_ids = [a.identity.id for a in agents]

        tick_engine.scheduler.generate_daily_schedule(1, agent_ids, world)
        world.state.tick = tick_engine.wake_hour

        # 重新生成每日目标

        if getattr(tick_engine, "quest_engine", None):
            tick_engine.quest_engine.generate_daily_goals(1)

        tick_engine._save_current_state()
        tick_engine.persist_game_state()

        return {"status":"ok", "result": "模拟已重置"}

    @app.get("/api/quests")

    async def get_quests():

        """获取任务列表"""

        if tick_engine.quest_engine:

            return tick_engine.quest_engine.to_dict()

        return {'active_quests': [], 'completed_quests': [], 'achievements': [], 'total_completed': 0, 'total_quests': 0}

    @app.get("/api/requests")

    async def get_requests():

        """小镇请求（v5 纵切片）：具体请求与选项（成本/前置），玩家可见可回应"""

        return [_request_payload(request, agents) for request in getattr(tick_engine, "requests", [])]

    @app.get("/api/today-threads")
    async def get_today_threads():
        """首屏三条线的只读接口，与 /api/state 使用同一份数据结构。"""
        requests_payload = [_request_payload(request, agents) for request in getattr(tick_engine, "requests", [])]
        return _today_threads(
            requests_payload, world, _active_crisis_payloads(),
            tick_engine.campaign.payload(tick_engine.current_day),
        )

    @app.get("/api/progress")

    async def get_progress():

        """长期目标线进度（v4 §5）：小镇重建 + 身世之谜"""

        return {
            "rebuild": {
                "upgrades_done": tick_engine._upgrades_done,
                "levels": world.state.location_levels,
                "next_threshold": 100 * (tick_engine._upgrades_done + 1) ** 2,
                "total_gold": sum(a.state.gold for a in agents),
                "desc": f"修缮 {tick_engine._upgrades_done}/15 处（目标：5 地点全部 Lv5）",
            },
            "lore": {
                "fragments": sorted(getattr(tick_engine, 'lore_fragments', set())),
                "collected": len(getattr(tick_engine, 'lore_fragments', set())),
                "total": tick_engine.LORE_TOTAL_FRAGMENTS,
                "unlocked": getattr(tick_engine, 'lore_unlocked', []),
                "desc": f"身世碎片 {len(getattr(tick_engine, 'lore_fragments', set()))}/{tick_engine.LORE_TOTAL_FRAGMENTS} 片（通过每日思考触及真相关键词收集）",
            },
        }

    @app.get("/api/campaign")
    async def get_campaign():
        """Current multi-week chapter and its observable consequences."""
        return tick_engine.campaign.payload(tick_engine.current_day)

    @app.get("/api/crises")

    async def get_crises():

        """获取进行中的危机（v4 §4）"""

        return [{
            "id": i,
            "type": c.crisis_type,
            "desc": c.desc,
            "progress": c.progress,
            "target": c.target,
            "days_remaining": c.days_remaining,
            "active": c.active,
            "outcome": c.outcome,
            "interventions": c.interventions,
        } for i, c in enumerate(tick_engine.crises) if c.active]

    @app.post("/api/crisis/{crisis_id}/intervene")

    async def intervene_crisis(crisis_id: int, body: dict = None):

        """玩家干预危机（v4 §4）：帮忙/调查/澄清/旁观"""

        body = body or {}
        action_type = body.get("action", "watch")
        if crisis_id < 0 or crisis_id >= len(tick_engine.crises):
            return {"status": "error", "result": "危机不存在"}
        crisis = tick_engine.crises[crisis_id]
        if not crisis.active:
            return {"status": "error", "result": "这场危机已经结束了"}
        player = next((a for a in agents if a.identity.role.value == 'player'), None)
        if not player:
            return {"status": "error", "result": "找不到玩家"}
        ar = tick_engine.resolver.resolve(player, Action(
            actor_id=player.identity.id,
            kind="crisis_intervene",
            payload={"crisis_id": crisis_id, "action_type": action_type},
        ))
        await tick_engine.wait_caught_up()
        return _action_payload(ar)







    @app.get("/api/dialogue/options/{agent_id}")

    async def get_dialogue_options(agent_id: str):

        """获取与指定Agent的对话选项（语境化：心情/正在做的事）"""

        if not dialogue_sys:

            return {"options": [], "tie": 0, "level": "未知"}

        player = None

        target = None

        for a in agents:

            if a.identity.role.value == "player":

                player = a

            if a.identity.id == agent_id:

                target = a

        if not player or not target:

            return {"options": [], "tie": 0, "level": "未知"}

        if target.identity.role.value == "player":
            return {"options": [], "tie": 0, "level": "未知", "error_code": "self_target"}

        tie = target.state.social_ties.get(player.identity.id, 0)

        ctx = _dialogue_context(target)

        options = dialogue_sys.generate_options(player, target, ctx)

        level = dialogue_sys.get_relationship_level(tie)

        return {
            "options": options,
            "tie": round(tie, 1),
            "level": level,
            "agent_name": target.identity.name,
            "mood": target.state.mood.value,
            "current_task": ctx["current_task"],
        }



    @app.post("/api/dialogue/execute/{agent_id}")

    async def execute_dialogue(agent_id: str, body: dict = None):

        """执行对话"""

        body = body or {}

        option_id = body.get("option_id", "chat")

        

        if not dialogue_sys:

            return {"success": False, "message": "对话系统未初始化"}

        

        player = None

        target = None

        for a in agents:

            if a.identity.role.value == "player":

                player = a

            if a.identity.id == agent_id:

                target = a

        

        if not player or not target:

            return {"success": False, "message": "找不到对话对象"}

        if target.identity.role.value == "player":
            return {"success": False, "message": "不能和自己对话", "error_code": "self_target"}

        # v5 校验：对话必须同地点（禁止跨地点免费社交）

        if player.state.location != target.state.location:

            return {"success": False, "message": f"{target.identity.name}不在这里，去{target.identity.name}所在的地点才能交谈"}



        ar = tick_engine.resolver.resolve(player, Action(
            actor_id=player.identity.id,
            kind="dialogue",
            target_id=target.identity.id,
            payload={"option_id": option_id},
        ))
        await tick_engine.wait_caught_up()
        payload = _action_payload(ar)
        payload.update({
            "success": bool(payload["details"].get("success")) if ar.accepted else False,
            "message": ar.result,
            "tie_change": payload["details"].get("tie_change", 0),
            "knowledge_gained": payload["details"].get("knowledge_gained"),
            "mood_effect": payload["details"].get("mood_effect", 0),
            "ap_remaining": player.state.ap,
            "night_ap_remaining": player.state.night_ap,
        })
        return payload



    @app.websocket("/ws")

    async def ws_endpoint(websocket:WebSocket):

        await websocket.accept()

        ws_clients.add(websocket)

        try:

            # 获取玩家状态
            player = next(
                (payload for payload in _build_state_payload()["agents"] if payload["role"] == "player"),
                None,
            )

            # 发送当前状态和历史摘要

            await websocket.send_json({"type": "state", "data": _build_state_payload()})

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

                        result = await player_action(msg.get("action",{}))

                        await websocket.send_json({"type":"player_action_result", "data": result})

                        # 发送更新后的状态

                        await websocket.send_json({"type": "state", "data": _build_state_payload()})

                except json.JSONDecodeError:

                    pass

        except WebSocketDisconnect:

            pass

        finally:

            ws_clients.discard(websocket)



    return app

