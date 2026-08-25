"""Phase 2 居民感知与因果链剧本。

覆盖 v5 §4.2 的最小验收：
1. 同一场雨在不同人格上产生不同动作；
2. 事件进入短期记忆，并在决策日志中留下 observations/reason；
3. 知识传播后，接收者下一次决策能读到该知识；
4. 日报从结构化动作结果生成最多三条因果回信。
"""
import asyncio
import os
import random
import tempfile

from agent import Agent, populate_agents
from events import EventBus
from knowledge import KnowledgeEngine
from llm import LLMClient
from models import AgentIdentity, Event, EventType, Role
from storage import Storage
from tick import TickEngine
from world import World


def build_engine():
    world = World()
    bus = EventBus()
    db_dir = tempfile.mkdtemp(prefix="ktown_phase2_")
    storage = Storage(os.path.join(db_dir, "phase2.db"))
    knowledge = KnowledgeEngine()
    agents = populate_agents()
    for agent in agents:
        world.add_agent_to_location(agent.identity.id, agent.state.location)
    llm = LLMClient("", "", "mock", "mock")
    return TickEngine(world, bus, agents, knowledge, storage, llm,
                      day_length=20, auto_reset=True, db=storage), db_dir


async def main():
    random.seed(11)
    engine, db_dir = build_engine()
    try:
        sensitive = Agent(
            AgentIdentity("sensitive", "敏感居民", Role.STORYTELLER,
                          personality={"extraversion": .5, "conscientiousness": .4,
                                       "openness": .5, "agreeableness": .5,
                                       "stability": .3}),
            location="workshop",
        )
        steady = Agent(
            AgentIdentity("steady", "稳重居民", Role.CARPENTER,
                          personality={"extraversion": .5, "conscientiousness": .9,
                                       "openness": .5, "agreeableness": .5,
                                       "stability": .9}),
            location="workshop",
        )
        rain = Event(6, EventType.WEATHER_IMPACT, "workshop",
                     {"weather": "rainy", "impact": -0.2})
        sensitive_obs = sensitive.perceive([rain], weather="rainy", tick=6)
        steady_obs = steady.perceive([rain], weather="rainy", tick=6)
        sensitive_action, sensitive_trace = sensitive.decide_with_trace(
            6, [sensitive, steady],
            ["weather_impact at workshop: {'weather': 'rainy'}"],
        )
        steady_action, steady_trace = steady.decide_with_trace(
            6, [sensitive, steady],
            ["weather_impact at workshop: {'weather': 'rainy'}"],
        )
        assert sensitive_obs and steady_obs
        assert sensitive_action["type"] != steady_action["type"] or sensitive_action["target"] != steady_action["target"]
        assert sensitive_trace["reason"] != steady_trace["reason"]
        print("  ✓ 雨天感知进入短期记忆，并让不同人格采取不同动作")

        source = engine.knowledge.observe_with_action(
            "agent_scout", "旧矿道", "旧矿道入口有塌方，暂时不要走那里",
            "wilderness", confidence=.9, action_type="avoid_location",
            action_target="wilderness", emotional_valence=-.8,
        )
        received = engine.knowledge.propagate(source.id, "agent_scout", "agent_forager", .8)
        assert received and any(c.id == source.id for c in engine.knowledge.agent_knowledge("agent_forager"))
        actions = engine.knowledge.derive_actions_for_agent("agent_forager")
        assert actions and actions[0]["type"] == "avoid"
        print("  ✓ 知识传播后改变接收者的下一次路线建议")

        engine.world.state.tick = 5
        engine.bus.publish(Event(6, EventType.WEATHER_CHANGE, "square", {"weather": "rainy"}))
        await engine.step()
        decisions = engine.db.query_decisions(100)
        assert decisions and any(d["observations"] for d in decisions)
        assert any(d["reason"] for d in decisions)
        assert any(d["next_observation"] or d["changes"] for d in decisions)
        print("  ✓ tick 事件快照进入居民决策日志，包含观察/原因/变化")

        # 直接模拟一个可追溯的后果，验证日报只选最多三条。
        engine.daily_agent_logs["agent_player"].extend([
            "因为暴雨预告，所以莉娜把木料移进工坊",
            "因为莉娜分享了草图，所以托林改用临时遮雨层",
            "因为旧矿道传闻，所以费尔南改走河谷",
            "因为无关日志，所以这条不应被选为第四条",
        ])
        summary = engine._generate_day_summary(1)
        assert len(summary["causal_beats"]) == 3
        print("  ✓ 日报从同一日志生成最多三条因果回信")
    finally:
        engine.db.close()
        import shutil
        shutil.rmtree(db_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
