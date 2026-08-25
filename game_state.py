"""Versioned save and restore contract for the playable town state.

The API payloads intentionally omit implementation details and are not a save
format.  This module keeps the persistence boundary explicit so a restart can
resume the same seven-day simulation without reseeding requests or consuming a
different random sequence.
"""

from __future__ import annotations

import copy
import json
import random
import time
from dataclasses import dataclass, field, fields
from typing import Any, Dict, Iterable, List, Optional

from agent import Agent
from crisis import Crisis
from events import EventBus
from knowledge import claim_to_dict
from models import (
    AgentIdentity,
    AgentState,
    AgentTask,
    ClaimScope,
    ClaimSource,
    Event,
    EventType,
    Goal,
    KnowledgeClaim,
    Mood,
    Role,
    TradeOffer,
    WorldState,
)
from requests import RequestOption, TownRequest


GAME_STATE_VERSION = 1


@dataclass
class GameState:
    """Stable top-level save shape stored by ``Storage``.

    The individual sections are dictionaries instead of a deeply nested class
    hierarchy so fields can be added in later versions without making old saves
    impossible to inspect or migrate.
    """

    schema_version: int = GAME_STATE_VERSION
    saved_at: float = field(default_factory=time.time)
    world: Dict[str, Any] = field(default_factory=dict)
    agents: List[Dict[str, Any]] = field(default_factory=list)
    knowledge: Dict[str, Any] = field(default_factory=dict)
    requests: List[Dict[str, Any]] = field(default_factory=list)
    crises: List[Dict[str, Any]] = field(default_factory=list)
    bus: Dict[str, Any] = field(default_factory=dict)
    engine: Dict[str, Any] = field(default_factory=dict)
    random_state: Any = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "saved_at": self.saved_at,
            "world": self.world,
            "agents": self.agents,
            "knowledge": self.knowledge,
            "requests": self.requests,
            "crises": self.crises,
            "bus": self.bus,
            "engine": self.engine,
            "random_state": self.random_state,
        }


def build_game_state(engine) -> Dict[str, Any]:
    """Create a JSON-safe save snapshot from a live ``TickEngine``."""

    state = GameState(
        world=_world_to_dict(engine.world),
        agents=[_agent_to_dict(agent) for agent in engine.agents],
        knowledge=_knowledge_to_dict(engine.knowledge),
        requests=[_request_to_dict(request) for request in engine.requests],
        crises=[_crisis_to_dict(crisis) for crisis in engine.crises],
        bus={
            "event_log": [_event_to_dict(event) for event in engine.bus.all_events],
            "scheduled": [_event_to_dict(event) for event in getattr(engine.bus, "_scheduled", [])],
        },
        engine={
            "current_day": engine.current_day,
            "pending_advance": engine._pending_advance,
            "day_summaries": _json_copy(engine.day_summaries),
            "current_day_events": _json_copy(engine.current_day_events),
            "current_day_decisions": _json_copy(engine.current_day_decisions),
            "daily_agent_logs": _json_copy(engine.daily_agent_logs),
            "prev_agent_states": _json_copy(engine.prev_agent_states),
            "prev_knowledge_count": engine.prev_knowledge_count,
            "prev_total_gold": engine.prev_total_gold,
            "tick_since_last_db_write": engine._tick_since_last_db_write,
            "llm_calls_today": engine._llm_calls_today,
            "llm_cache": _json_copy(engine._llm_cache),
            "upgrades_done": engine._upgrades_done,
            "insight_day": engine._insight_day,
            "resolver_action_sequence": engine.resolver._action_sequence,
            "lore_fragments": sorted(getattr(engine, "lore_fragments", set())),
            "lore_clues": _json_copy(getattr(engine, "lore_clues", {})),
            "lore_unlocked": _json_copy(getattr(engine, "lore_unlocked", [])),
            "factions": _json_copy(engine.faction_system.factions),
            "next_faction_id": engine.faction_system.next_faction_id,
            "campaign": engine.campaign.to_dict() if getattr(engine, "campaign", None) else {},
        },
        random_state=_json_copy(random.getstate()),
    )
    return state.to_dict()


def restore_game_state(engine, payload: Dict[str, Any]) -> bool:
    """Hydrate an existing ``TickEngine`` from a version 1 snapshot.

    ``engine.agents`` is updated in place because FastAPI holds the list object
    passed in by ``main.py``.  Returning ``False`` lets the caller use its legacy
    partial-restoration fallback for an older database without a game-state row.
    """

    if not isinstance(payload, dict) or payload.get("schema_version") != GAME_STATE_VERSION:
        return False

    try:
        restored_agents = [_agent_from_dict(item) for item in payload.get("agents", [])]
        if not restored_agents:
            return False

        _restore_world(engine.world, payload.get("world", {}))
        engine.agents[:] = restored_agents
        _sync_locations(engine.world, engine.agents)
        _restore_knowledge(engine.knowledge, payload.get("knowledge", {}))
        engine.requests = [_request_from_dict(item) for item in payload.get("requests", [])]
        engine.crises = [_crisis_from_dict(item, engine) for item in payload.get("crises", [])]
        _restore_bus(engine.bus, payload.get("bus", {}))
        _restore_engine_fields(engine, payload.get("engine", {}))
        random_state = payload.get("random_state")
        if random_state:
            random.setstate(_to_tuple(random_state))
        engine.resolver.world = engine.world
        engine.resolver.knowledge = engine.knowledge
        engine.resolver.agents = engine.agents
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _json_copy(value: Any) -> Any:
    """Make a deep JSON-compatible copy while retaining deterministic ordering."""

    return json.loads(json.dumps(value, ensure_ascii=False, default=_json_default))


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _agent_to_dict(agent) -> Dict[str, Any]:
    state = agent.state
    task = None
    if state.current_task is not None:
        task = {
            "description": state.current_task.description,
            "location": state.current_task.location,
            "started_at": state.current_task.started_at,
        }
    return {
        "identity": {
            "id": agent.identity.id,
            "name": agent.identity.name,
            "role": agent.identity.role.value,
            "traits": _json_copy(agent.identity.traits),
            "skills": _json_copy(agent.identity.skills),
            "personality": _json_copy(agent.identity.personality),
        },
        "state": {
            "energy": state.energy,
            "mood": state.mood.value,
            "gold": state.gold,
            "location": state.location,
            "current_task": task,
            "inventory": _json_copy(state.inventory),
            "social_ties": _json_copy(state.social_ties),
            "food": state.food,
            "hunger": state.hunger,
            "ap": state.ap,
            "ap_max": state.ap_max,
            "night_ap": state.night_ap,
            "faction_id": state.faction_id,
            "emotions": _json_copy(state.emotions),
            "habit_bias": _json_copy(state.habit_bias),
            "habit_counts": _json_copy(state.habit_counts),
            "short_term_memory": _json_copy(state.short_term_memory),
        },
        "goals": [
            {
                "id": goal.id,
                "description": goal.description,
                "base_priority": goal.base_priority,
                "urgency": goal.urgency,
                "completed": goal.completed,
            }
            for goal in agent.goals
        ],
        "diary": _json_copy(agent.diary),
    }


def _agent_from_dict(data: Dict[str, Any]):
    identity_data = data.get("identity", {})
    state_data = data.get("state", {})
    role_value = identity_data.get("role", Role.PLAYER.value)
    try:
        role = Role(role_value)
    except ValueError:
        role = Role.PLAYER
    identity = AgentIdentity(
        id=str(identity_data.get("id", "agent_unknown")),
        name=str(identity_data.get("name", "居民")),
        role=role,
        traits=list(identity_data.get("traits", [])),
        skills=dict(identity_data.get("skills", {})),
        personality=dict(identity_data.get("personality", {})),
    )
    agent = Agent(identity, location=state_data.get("location", "square"))
    task_data = state_data.get("current_task")
    task = None
    if isinstance(task_data, dict) and task_data.get("description"):
        task = AgentTask(
            description=str(task_data["description"]),
            location=str(task_data.get("location", state_data.get("location", "square"))),
            started_at=float(task_data.get("started_at", time.time())),
        )
    try:
        mood = Mood(state_data.get("mood", Mood.NEUTRAL.value))
    except ValueError:
        mood = Mood.NEUTRAL
    agent.state = AgentState(
        energy=float(state_data.get("energy", 100.0)),
        mood=mood,
        gold=int(state_data.get("gold", 0)),
        location=str(state_data.get("location", "square")),
        current_task=task,
        inventory=list(state_data.get("inventory", [])),
        social_ties=dict(state_data.get("social_ties", {})),
        food=int(state_data.get("food", 5)),
        hunger=float(state_data.get("hunger", 0)),
        ap=int(state_data.get("ap", 12)),
        ap_max=int(state_data.get("ap_max", 12)),
        night_ap=int(state_data.get("night_ap", 0)),
        faction_id=str(state_data.get("faction_id", "")),
        emotions=dict(state_data.get("emotions", {})),
        habit_bias=dict(state_data.get("habit_bias", {})),
        habit_counts=dict(state_data.get("habit_counts", {})),
        short_term_memory=list(state_data.get("short_term_memory", [])),
    )
    agent.goals = [
        Goal(
            id=str(goal.get("id", "")),
            description=str(goal.get("description", "")),
            base_priority=float(goal.get("base_priority", 5.0)),
            urgency=float(goal.get("urgency", 0.5)),
            completed=bool(goal.get("completed", False)),
        )
        for goal in data.get("goals", [])
    ]
    agent.diary = list(data.get("diary", []))
    return agent


def _world_to_dict(world) -> Dict[str, Any]:
    state = {}
    for definition in fields(WorldState):
        value = getattr(world.state, definition.name)
        if definition.name == "trade_offers":
            state[definition.name] = [
                {
                    "from_agent": offer.from_agent,
                    "to_agent": offer.to_agent,
                    "item": offer.item,
                    "price": offer.price,
                    "status": offer.status,
                }
                for offer in value
            ]
        else:
            state[definition.name] = _json_copy(value)
    return {
        "state": state,
        "resources": _json_copy(world.resources),
        "prices": _json_copy(world.prices),
        "price_history": _json_copy(world.price_history),
        "demand": _json_copy(world.demand),
        "supply": _json_copy(world.supply),
    }


def _restore_world(world, data: Dict[str, Any]) -> None:
    state_data = data.get("state", {})
    restored = WorldState()
    for definition in fields(WorldState):
        if definition.name not in state_data:
            continue
        value = state_data[definition.name]
        if definition.name == "trade_offers":
            value = [
                TradeOffer(
                    from_agent=str(offer.get("from_agent", "")),
                    to_agent=str(offer.get("to_agent", "")),
                    item=str(offer.get("item", "")),
                    price=int(offer.get("price", 0)),
                    status=str(offer.get("status", "pending")),
                )
                for offer in value
            ]
        setattr(restored, definition.name, copy.deepcopy(value))
    world.state = restored
    for field_name in ("resources", "prices", "price_history", "demand", "supply"):
        if field_name in data:
            setattr(world, field_name, copy.deepcopy(data[field_name]))


def _sync_locations(world, agents: Iterable) -> None:
    for location in world.locations.values():
        location["agents"] = []
    for agent in agents:
        if agent.state.location not in world.locations:
            agent.state.location = "square"
        world.add_agent_to_location(agent.identity.id, agent.state.location)


def _knowledge_to_dict(knowledge) -> Dict[str, Any]:
    return {
        "claims": [claim_to_dict(claim) for claim in knowledge.claims.values()],
        "agent_claims": _json_copy(knowledge.agent_claims),
        "next_claim_sequence": int(getattr(knowledge, "_claim_sequence", 0)),
    }


def _restore_knowledge(knowledge, data: Dict[str, Any]) -> None:
    persistence = knowledge.persistence
    knowledge.reset()
    knowledge.persistence = persistence
    for item in data.get("claims", []):
        try:
            claim = KnowledgeClaim(
                id=str(item["id"]),
                subject=str(item["subject"]),
                claim=str(item["claim"]),
                source=ClaimSource(item.get("source", ClaimSource.OBSERVATION.value)),
                confidence=float(item.get("confidence", 0.6)),
                scope=ClaimScope(item.get("scope", ClaimScope.PRIVATE.value)),
                created_by=str(item.get("created_by", "")),
                location=str(item.get("location", "")),
                actionable=bool(item.get("actionable", False)),
                action_type=str(item.get("action_type", "")),
                action_target=str(item.get("action_target", "")),
                emotional_valence=float(item.get("emotional_valence", 0.0)),
                created_at=float(item.get("created_at", time.time())),
                contradicted_by=list(item.get("contradicted_by", [])),
                solidified=bool(item.get("solidified", False)),
                version=int(item.get("version", 1)),
            )
        except (KeyError, TypeError, ValueError):
            continue
        knowledge.claims[claim.id] = claim
        knowledge._update_index(claim)
    restored_claims = {
        str(agent_id): [claim_id for claim_id in claim_ids if claim_id in knowledge.claims]
        for agent_id, claim_ids in data.get("agent_claims", {}).items()
    }
    for claim in knowledge.claims.values():
        restored_claims.setdefault(claim.created_by, [])
        if claim.id not in restored_claims[claim.created_by]:
            restored_claims[claim.created_by].append(claim.id)
    knowledge.agent_claims = restored_claims
    knowledge._claim_sequence = max(0, int(data.get("next_claim_sequence", 0)))


def _request_to_dict(request: TownRequest) -> Dict[str, Any]:
    return {
        "id": request.id,
        "requester_id": request.requester_id,
        "location": request.location,
        "title": request.title,
        "situation": request.situation,
        "deadline": request.deadline,
        "status": request.status,
        "completed_day": request.completed_day,
        "progress": request.progress,
        "max_progress": request.max_progress,
        "used_options": _json_copy(request.used_options),
        "observed_option_ids": _json_copy(request.observed_option_ids),
        "next_day_observations": _json_copy(request.next_day_observations),
        "observed_next_day_observations": _json_copy(request.observed_next_day_observations),
        "visible_risks": _json_copy(request.visible_risks),
        "tags": _json_copy(request.tags),
        "chapter_id": getattr(request, "chapter_id", "week_1_rain"),
        "options": [
            {
                "id": option.id,
                "label": option.label,
                "requires": option.requires,
                "requires_cn": option.requires_cn,
                "cost_ap": option.cost_ap,
                "cost_hours": option.cost_hours,
                "result_desc": option.result_desc,
                "next_observation": option.next_observation,
                "effect": option.effect,
                "progress_delta": option.progress_delta,
                "closes_request": option.closes_request,
                "visible_risk": option.visible_risk,
                "next_day_observation": option.next_day_observation,
            }
            for option in request.options
        ],
    }


def _request_from_dict(data: Dict[str, Any]) -> TownRequest:
    options = [
        RequestOption(
            id=str(option["id"]),
            label=str(option["label"]),
            requires=str(option.get("requires", "")),
            requires_cn=str(option.get("requires_cn", "")),
            cost_ap=int(option.get("cost_ap", 0)),
            cost_hours=int(option.get("cost_hours", 0)),
            result_desc=str(option.get("result_desc", "")),
            next_observation=str(option.get("next_observation", "")),
            effect=str(option.get("effect", "")),
            progress_delta=int(option.get("progress_delta", 0)),
            closes_request=bool(option.get("closes_request", False)),
            visible_risk=str(option.get("visible_risk", "")),
            next_day_observation=str(option.get("next_day_observation", "")),
        )
        for option in data.get("options", [])
    ]
    return TownRequest(
        id=str(data["id"]),
        requester_id=str(data["requester_id"]),
        location=str(data["location"]),
        title=str(data["title"]),
        situation=str(data["situation"]),
        deadline=int(data["deadline"]),
        status=str(data.get("status", "active")),
        options=options,
        completed_day=int(data.get("completed_day", 0)),
        progress=int(data.get("progress", 0)),
        max_progress=int(data.get("max_progress", 1)),
        used_options=list(data.get("used_options", [])),
        observed_option_ids=list(data.get("observed_option_ids", [])),
        next_day_observations=list(data.get("next_day_observations", [])),
        observed_next_day_observations=list(data.get("observed_next_day_observations", [])),
        visible_risks=list(data.get("visible_risks", [])),
        tags=list(data.get("tags", [])),
        chapter_id=str(data.get("chapter_id", "week_1_rain")),
    )


def _crisis_to_dict(crisis) -> Dict[str, Any]:
    return {
        "crisis_type": crisis.crisis_type,
        "start_day": crisis.start_day,
        "duration_days": crisis.duration_days,
        "target": crisis.target,
        "energy_loss": crisis.energy_loss,
        "gold_loss": crisis.gold_loss,
        "desc": crisis.desc,
        "progress": crisis.progress,
        "interventions": _json_copy(crisis.interventions),
        "last_intervene_day": crisis.last_intervene_day,
        "outcome": crisis.outcome,
    }


def _crisis_from_dict(data: Dict[str, Any], engine):
    crisis = Crisis(str(data["crisis_type"]), int(data["start_day"]), engine)
    for key in (
        "duration_days",
        "target",
        "energy_loss",
        "gold_loss",
        "desc",
        "progress",
        "interventions",
        "last_intervene_day",
        "outcome",
    ):
        if key in data:
            setattr(crisis, key, copy.deepcopy(data[key]))
    return crisis


def _event_to_dict(event: Event) -> Dict[str, Any]:
    return {
        "tick": event.tick,
        "type": event.type.value,
        "location": event.location,
        "payload": _json_copy(event.payload),
    }


def _event_from_dict(data: Dict[str, Any]) -> Optional[Event]:
    try:
        return Event(
            tick=int(data["tick"]),
            type=EventType(data["type"]),
            location=str(data.get("location", "")),
            payload=dict(data.get("payload", {})),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _restore_bus(bus: EventBus, data: Dict[str, Any]) -> None:
    event_log = [_event_from_dict(item) for item in data.get("event_log", [])]
    scheduled = [_event_from_dict(item) for item in data.get("scheduled", [])]
    bus._event_log = [event for event in event_log if event is not None]
    bus._scheduled = [event for event in scheduled if event is not None]


def _restore_engine_fields(engine, data: Dict[str, Any]) -> None:
    engine.current_day = int(data.get("current_day", engine.current_day))
    engine._pending_advance = int(data.get("pending_advance", 0))
    engine.day_summaries = list(data.get("day_summaries", []))
    engine.current_day_events = list(data.get("current_day_events", []))
    engine.current_day_decisions = list(data.get("current_day_decisions", []))
    engine.daily_agent_logs = dict(data.get("daily_agent_logs", {}))
    engine.prev_agent_states = list(data.get("prev_agent_states", []))
    engine.prev_knowledge_count = int(data.get("prev_knowledge_count", len(engine.knowledge.claims)))
    engine.prev_total_gold = int(data.get("prev_total_gold", 0))
    engine._tick_since_last_db_write = int(data.get("tick_since_last_db_write", 0))
    engine._llm_calls_today = int(data.get("llm_calls_today", 0))
    engine._llm_cache = dict(data.get("llm_cache", {}))
    engine._upgrades_done = int(data.get("upgrades_done", 0))
    engine._insight_day = int(data.get("insight_day", 0))
    engine.resolver._action_sequence = int(data.get("resolver_action_sequence", 0))
    if data.get("lore_fragments") or data.get("lore_clues") or data.get("lore_unlocked"):
        engine.lore_fragments = set(data.get("lore_fragments", []))
        engine.lore_clues = dict(data.get("lore_clues", {}))
        engine.lore_unlocked = list(data.get("lore_unlocked", []))
    engine.faction_system.factions = dict(data.get("factions", {}))
    engine.faction_system.next_faction_id = int(data.get("next_faction_id", 1))
    if getattr(engine, "campaign", None):
        engine.campaign.restore(data.get("campaign"))


def _to_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_to_tuple(item) for item in value)
    if isinstance(value, dict):
        return {key: _to_tuple(item) for key, item in value.items()}
    return value
