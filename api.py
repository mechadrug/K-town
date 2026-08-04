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





def create_app(world,agents,bus,logger,knowledge,llm,tick_engine,ws_clients:Set[WebSocket],dialogue_sys=None):

    app=FastAPI(title="K-town",version="0.2.0")

    base=os.path.dirname(os.path.abspath(__file__))

    static_dir=os.path.join(base,'static')

    if os.path.exists(static_dir):

        app.mount('/static',StaticFiles(directory=static_dir),name='static')

    # 挂载静态文件

    def _build_state_payload() -> dict:
        """构建前端全量状态载荷：/api/state 与 WS 共用同一来源，避免字段漂移"""
        player = None
        for a in agents:
            if a.identity.role.value == "player":
                player = a.to_dict()
                break
        return {
            "tick": world.state.tick,
            "weather": world.state.weather,
            "weather_name": world.get_weather_name(),
            "locations": world.to_dict()["locations"],
            "agents": [a.to_dict() for a in agents],
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
            "location_levels": world.state.location_levels
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

                r=a.to_dict()

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
                knowledge.observe(aid, "思考", claim_text, actor.state.location)
                result = f"你把一段想法写进了小镇的记忆：{claim_text}"
                insight = tick_engine._check_insight(actor, claim_text)
                if insight:
                    result = insight
                # 每日目标：提交思考推进"传播知识"目标
                if tick_engine.quest_engine:
                    tick_engine.quest_engine.update_progress(actor, action_type="add_claim")
            logger.log_player_action(PlayerAction(tick=tick_engine.world.state.tick, action_type=t, payload=action, result=result))
            return {"status": "ok", "result": result}

        # === 回合制：1 AP = 1 小时。非休息动作须在清醒时段，且推进世界时钟 ===
        hour = tick_engine.world.state.tick % tick_engine.day_length
        ws, wl = tick_engine.wake_hour, tick_engine.waking_hours
        is_night = not (ws <= hour < ws + wl)
        ap_cost = {"move": 1, "work": 1, "talk": 1, "investigate": 2, "trade": 1,
                   "observe": 0, "sleep": 0, "trade_offer": 1, "accept_trade": 0,
                   "add_claim": 1, "trigger_event": 1}.get(t, 1)

        if t == "rest":
            # 休息 = 结束今天：推进到次日清晨，跨过午夜日结（AP 自动重置）
            to_next_wake = (ws - hour) % tick_engine.day_length or tick_engine.day_length
            tick_engine.advance(to_next_wake)
            await tick_engine.wait_caught_up()
            result = "你睡了一觉，迎来了新的一天"
            logger.log_player_action(PlayerAction(tick=tick_engine.world.state.tick, action_type=t, payload=action, result=result))
            return {"status": "ok", "result": result}
        if is_night:
            # 十三时：夜晚只能用独立的夜间行动力（night_ap），不扣常规 AP
            if actor.state.night_ap <= 0:
                return {"status": "error", "result": "夜深了，镇上的人都睡了。你虽有古玉佩护佑，却也困倦难当——点「休息」吧。"}
            actor.state.night_ap -= 1
        if not is_night and actor.identity.role.value == 'player' and t in ("move", "work", "talk", "investigate") and actor.state.ap < ap_cost:
            return {"status": "error", "result": f"行动力不足（剩余{actor.state.ap}点，需要{ap_cost}点）"}
        if ap_cost > 0:
            tick_engine.advance(ap_cost)

        result = ""

        if t == "trigger_event":
            event_type = action.get("event_type", "weather_change")
            location = action.get("location", "square")
            payload = action.get("payload", {})
            event = Event(tick=tick_engine.world.state.tick, type=EventType(event_type), location=location, payload=payload)
            bus.publish(event)
            result = f"触发了{event_type}事件"
        elif t == "reset":
            return await reset_simulation()
        elif t in ("work", "rest", "investigate", "move", "talk", "trade", "observe", "sleep"):
            # 常规动作：走与 NPC 相同的执行管线（_handle_action 内部处理玩家 AP 消耗）
            act = {"type": t, "target": tgt}
            before = len(tick_engine.daily_agent_logs.get(aid, []))
            await tick_engine._handle_action(actor, act, tick_engine.world.state.tick)
            logs = tick_engine.daily_agent_logs.get(aid, [])
            result = logs[-1] if len(logs) > before else f"{actor.identity.name}执行了{t}"
        elif t == "trade_offer":
            item = action.get("item", "")
            price = action.get("price", 0)
            target = tgt
            if target and item and price > 0:
                offer = TradeOffer(from_agent=aid, to_agent=target, item=item, price=price)
                world.state.trade_offers.append(offer)
                result = f"向{target}发起了{item}的交易请求，价格{price}金币"
            else:
                result = "交易参数错误"
        elif t == "accept_trade":
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

        # 十三时：夜晚行动可能撞见遗迹残响（末世伏笔）
        if is_night and t in ("move", "work", "investigate", "talk", "observe"):
            mystery = tick_engine._night_mystery(actor)
            if mystery:
                result = mystery + "\n" + result

        # 记录玩家操作
        player_action = PlayerAction(tick=tick_engine.world.state.tick, action_type=t, payload=action, result=result)
        logger.log_player_action(player_action)

        # 等待回合制推进落地（1 AP = 1 小时），让前端看到时间流逝与结果
        await tick_engine.wait_caught_up()

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

        # 重新初始化所有模块

        world.__init__()

        bus.__init__()

        knowledge.__init__()

        knowledge.persistence = logger  # 重设持久化钩子（__init__ 会清掉它）

        logger.__init__()

        agents.clear()

        new_agents = populate_agents()

        agents.extend(new_agents)

        for a in new_agents:

            world.add_agent_to_location(a.identity.id, a.state.location)

        # 重新生成第一天事件

        agent_ids = [a.identity.id for a in agents]

        tick_engine.scheduler.generate_daily_schedule(1, agent_ids, world)

        # 重新生成每日目标

        tick_engine.quest_engine.generate_daily_goals(1)

        return {"status":"ok", "result": "模拟已重置"}

    @app.get("/api/quests")

    async def get_quests():

        """获取任务列表"""

        if tick_engine.quest_engine:

            return tick_engine.quest_engine.to_dict()

        return {'active_quests': [], 'completed_quests': [], 'achievements': [], 'total_completed': 0, 'total_quests': 0}







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

        

        # 获取选项（语境化）

        ctx = _dialogue_context(target)

        options = dialogue_sys.generate_options(player, target, ctx)

        option = None

        for opt in options:

            if opt["id"] == option_id:

                option = opt

                break

        if not option:

            return {"success": False, "message": "无效的对话选项"}

        # 回合制：夜晚需十三时夜间行动力才能对话；对话消耗 1 小时
        dl_hour = tick_engine.world.state.tick % tick_engine.day_length
        dl_night = not (tick_engine.wake_hour <= dl_hour < tick_engine.wake_hour + tick_engine.waking_hours)
        if dl_night:
            if player.state.night_ap <= 0:
                return {"success": False, "message": "夜深了，大家都睡了。只有十三时的夜间行动力才能让你撑着聊下去。"}
            player.state.night_ap -= 1

        # 检查AP（白天扣常规 AP；夜晚已走夜间行动力）

        ap_cost = 2 if option.get("energy_cost") else 1

        if not dl_night:
            if player.state.ap < ap_cost:
                return {"success": False, "message": f"AP不足（需要{ap_cost}点）"}
            player.state.ap -= ap_cost

        tick_engine.advance(ap_cost)

        # 执行对话

        result = dialogue_sys.execute_dialogue(player, target, option, ctx)

        # 回合制推进落地（对话 = 1 小时）

        # 应用关系变化（双向）

        tie_change = result["tie_change"]

        current_tie = target.state.social_ties.get(player.identity.id, 0)

        target.state.social_ties[player.identity.id] = current_tie + tie_change

        player.state.social_ties[target.identity.id] = \
            player.state.social_ties.get(target.identity.id, 0) + tie_change * 0.7

        # 应用心情变化（对话有情绪后果）

        if result.get("mood_effect", 0) != 0:
            _shift_mood(target, result["mood_effect"])

        # 知识交换：成功的"闲聊/请教/分享"——对方的知识传给你；你的知识也传给在场者
        if result["success"] and option.get("give_knowledge"):
            top = max(knowledge.agent_knowledge(target.identity.id),
                      key=lambda c: c.confidence, default=None)
            if top and top.confidence > 0.4:
                knowledge.observe(player.identity.id, top.subject, top.claim,
                                  target.state.location, confidence=min(0.9, top.confidence * 0.8))
                if result.get("knowledge_gained"):
                    result["knowledge_gained"] = f"{result['knowledge_gained']}，还听说了「{top.claim}」"
            p_top = max(knowledge.agent_knowledge(player.identity.id),
                        key=lambda c: c.confidence, default=None)
            if p_top and p_top.confidence > 0.5:
                for a in agents:
                    if a.identity.id != player.identity.id and a.state.location == player.state.location:
                        knowledge.propagate(p_top.id, player.identity.id, a.identity.id, 0.6)

        # 记录日志（进入日报，让对话可见可回溯）

        tick_engine.daily_agent_logs[player.identity.id].append(
            f"与{target.identity.name}对话：{result['message']}"
        )

        return {
            "success": result["success"],
            "message": result["message"],
            "tie_change": tie_change,
            "new_tie": round(current_tie + tie_change, 1),
            "knowledge_gained": result.get("knowledge_gained"),
            "mood_effect": result.get("mood_effect", 0),
            "ap_remaining": player.state.ap
        }



    @app.websocket("/ws")

    async def ws_endpoint(websocket:WebSocket):

        await websocket.accept()

        ws_clients.add(websocket)

        try:

            # 获取玩家状态

            player = None

            for a in agents:

                if a.identity.role.value == "player":

                    player = a.to_dict()

                    break

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

