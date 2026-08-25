"""Data-driven multi-week campaign progression for K-town.

The first playable slice is the tutorial week.  Later weeks are deliberately
defined here, outside ``tick.py`` and the UI, so adding a chapter normally
means adding content data and an effect definition instead of extending the
simulation loop with another collection of one-off conditionals.

The director owns only campaign state and chapter scheduling.  Ordinary time,
cost, validation, and request execution still belong to ``ActionResolver``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional


CAMPAIGN_STATE_VERSION = 1


@dataclass(frozen=True)
class ChapterDefinition:
    id: str
    week: int
    title: str
    subtitle: str
    unlock_day: int
    pressure: str
    objective: str
    request_ids: tuple[str, ...]


CHAPTERS: tuple[ChapterDefinition, ...] = (
    ChapterDefinition(
        id="week_1_rain", week=1, title="雨前的七天",
        subtitle="先记住三个人，再决定把时间留给哪里。",
        unlock_day=1,
        pressure="暴雨预告、屋顶漏雨，以及一条还没有证据的矿道传闻。",
        objective="在归灯集前让居民看见彼此愿意帮忙。",
        request_ids=("lina_dry_wood", "torin_roof", "mei_town_chronicle"),
    ),
    ChapterDefinition(
        id="week_2_water", week=2, title="河水改道",
        subtitle="雨季留下的泥沙会把远处的麻烦带到每个人门口。",
        unlock_day=8,
        pressure="学校蓄水槽堵塞，商队也在重新评估经过矿道的路线。",
        objective="在有限材料下决定先保住水、先确认路，还是相信旧地图。",
        request_ids=("school_cistern", "scout_safe_path"),
    ),
    ChapterDefinition(
        id="week_3_lanterns", week=3, title="灯火与账本",
        subtitle="小镇不只需要修好东西，也要决定谁能被照顾到。",
        unlock_day=15,
        pressure="归灯集临近，商人要看见一条值得信任的路，学校缺少夜灯。",
        objective="让外来者的安全和镇民自己的需要同时被写进计划。",
        request_ids=("merchant_route", "school_lanterns"),
    ),
    ChapterDefinition(
        id="week_4_fair", week=4, title="归灯集",
        subtitle="最后的选择不是赢下镇子，而是让大家认出这一周的改变。",
        unlock_day=22,
        pressure="灯火集将在本周结束，商队、居民和旧传闻都会来到同一张桌边。",
        objective="决定把小镇这一周形成的信任，交给谁来继续。",
        request_ids=("lantern_fair_council",),
    ),
)


_CHAPTER_BY_ID = {chapter.id: chapter for chapter in CHAPTERS}


# Effects are content data.  The director interprets this small vocabulary and
# applies it through the same action result that the request option produced.
CAMPAIGN_EFFECTS: Dict[str, Dict[str, Any]] = {
    "campaign:water:clear": {
        "flag": {"water_solution": "cistern_clean"},
        "scores": {"care": 2, "safety": 1},
        "marker": {"school_water": "清理干净"},
        "preparedness": 1,
        "requester_tie": 4,
        "knowledge": {"subject": "clean_water", "claim": "学校蓄水槽已经清理，雨季的水可以暂时安心饮用", "confidence": 0.9},
    },
    "campaign:water:filter": {
        "flag": {"water_solution": "cloth_filter"},
        "scores": {"care": 1, "trust": 1},
        "marker": {"school_water": "布滤层"},
        "requester_tie": 3,
        "knowledge": {"subject": "clean_water", "claim": "学校用布滤层暂时挡住泥沙，但蓄水槽还需要彻底清理", "confidence": 0.72},
    },
    "campaign:path:inspect": {
        "flag": {"path_solution": "mine_marked"},
        "scores": {"safety": 3, "welcome": 1},
        "marker": {"mine_path": "已标记塌方"},
        "requester_tie": 4,
        "knowledge": {"subject": "safe_route", "claim": "旧矿道东侧有新塌方，商队应该绕行河谷北坡", "confidence": 0.88},
    },
    "campaign:path:old_map": {
        "flag": {"path_solution": "old_map"},
        "scores": {"welcome": 2, "safety": -1},
        "marker": {"mine_path": "沿旧地图"},
        "requester_tie": 2,
        "knowledge": {"subject": "safe_route", "claim": "梅奶奶的旧地图仍标着一条穿过矿道的近路，但没有新证据", "confidence": 0.48},
    },
    "campaign:market:open": {
        "flag": {"market_solution": "open_market"},
        "scores": {"welcome": 3, "trust": 1},
        "marker": {"market_route": "开放集市"},
        "preparedness": 2,
        "requester_tie": 4,
    },
    "campaign:market:local": {
        "flag": {"market_solution": "local_stock"},
        "scores": {"care": 2, "trust": 2, "welcome": -1},
        "marker": {"market_route": "先保镇内"},
        "preparedness": 1,
        "requester_tie": 3,
    },
    "campaign:lantern:school": {
        "flag": {"lantern_solution": "school_lamps"},
        "scores": {"care": 3, "trust": 1},
        "marker": {"lantern_route": "学校借灯"},
        "preparedness": 1,
        "requester_tie": 4,
        "knowledge": {"subject": "lantern_route", "claim": "学校愿意把夜灯借给回灯集的北路，孩子们会少一盏室内灯", "confidence": 0.86},
    },
    "campaign:lantern:mine": {
        "flag": {"lantern_solution": "mine_glow"},
        "scores": {"welcome": 2, "safety": -1},
        "marker": {"lantern_route": "矿石灯火"},
        "preparedness": 2,
        "requester_tie": 3,
        "knowledge": {"subject": "lantern_route", "claim": "矿工愿意提供矿石灯火，但通往矿洞的路仍需要有人值守", "confidence": 0.7},
    },
    "campaign:fair:welcome": {
        "flag": {"fair_solution": "welcome_caravan"},
        "scores": {"welcome": 4, "trust": 1},
        "marker": {"fair_table": "商队与居民同桌"},
        "preparedness": 2,
        "requester_tie": 4,
    },
    "campaign:fair:local": {
        "flag": {"fair_solution": "local_fair"},
        "scores": {"care": 3, "trust": 2},
        "marker": {"fair_table": "先照顾镇民"},
        "preparedness": 1,
        "requester_tie": 4,
    },
    "campaign:fair:council": {
        "flag": {"fair_solution": "open_council"},
        "scores": {"trust": 4, "safety": 1, "care": 1},
        "marker": {"fair_table": "公开商议"},
        "preparedness": 1,
        "requester_tie": 5,
    },
}


def chapter_for_day(day: int) -> ChapterDefinition:
    """Return the latest chapter unlocked on ``day``."""

    current = CHAPTERS[0]
    for chapter in CHAPTERS:
        if chapter.unlock_day <= day:
            current = chapter
        else:
            break
    return current


class CampaignDirector:
    """Own chapter unlocks, content effects, and the multi-week ending."""

    def __init__(self, engine):
        self.engine = engine
        self.state: Dict[str, Any] = {}
        self.reset()

    def reset(self) -> None:
        self.state = {
            "schema_version": CAMPAIGN_STATE_VERSION,
            "active_chapter_id": CHAPTERS[0].id,
            "unlocked_chapters": [CHAPTERS[0].id],
            "chapter_history": [],
            "flags": {},
            "scores": {"care": 0, "safety": 0, "trust": 0, "welcome": 0},
            "final_outcome": None,
        }

    @property
    def active_chapter(self) -> ChapterDefinition:
        return _CHAPTER_BY_ID.get(
            self.state.get("active_chapter_id", CHAPTERS[0].id), CHAPTERS[0]
        )

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.state)

    def restore(self, payload: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(payload, dict):
            return False
        version = int(payload.get("schema_version", 0))
        if version != CAMPAIGN_STATE_VERSION:
            return False
        self.reset()
        self.state.update({
            "active_chapter_id": str(payload.get("active_chapter_id", CHAPTERS[0].id)),
            "unlocked_chapters": [str(item) for item in payload.get("unlocked_chapters", [])],
            "chapter_history": copy.deepcopy(payload.get("chapter_history", [])),
            "flags": copy.deepcopy(payload.get("flags", {})),
            "scores": {
                key: int(payload.get("scores", {}).get(key, 0))
                for key in ("care", "safety", "trust", "welcome")
            },
            "final_outcome": copy.deepcopy(payload.get("final_outcome")),
        })
        if CHAPTERS[0].id not in self.state["unlocked_chapters"]:
            self.state["unlocked_chapters"].insert(0, CHAPTERS[0].id)
        return True

    def ensure_new_game(self) -> None:
        """Reset campaign state while preserving the engine's initial requests."""

        self.reset()

    def sync_for_day(self, day: int) -> List[Dict[str, Any]]:
        """Unlock due chapters and seed their requests once.

        Called after the previous day's summary has been written and the engine
        has advanced its ``current_day``.  The returned events belong to the
        new day and therefore remain visible in the next day's event stream.
        """

        events: List[Dict[str, Any]] = []
        for chapter in CHAPTERS:
            if chapter.unlock_day > day or chapter.id in self.state["unlocked_chapters"]:
                continue
            previous = self.active_chapter
            self._finish_chapter(previous, day - 1)
            self.state["unlocked_chapters"].append(chapter.id)
            self.state["active_chapter_id"] = chapter.id
            self._seed_chapter_requests(chapter.id)
            event = {
                "tick": self.engine.world.state.tick,
                "type": "campaign_chapter",
                "location": "square",
                "action": f"第{chapter.week}周开始：{chapter.title}。{chapter.pressure}",
                "chapter_id": chapter.id,
            }
            events.append(event)
            self.engine.daily_agent_logs.setdefault("", []).append(event["action"])

        if day >= CHAPTERS[-1].unlock_day + 7 and not self.state.get("final_outcome"):
            self._finish_chapter(self.active_chapter, day - 1)
            self.state["final_outcome"] = self._build_final_outcome()
            events.append({
                "tick": self.engine.world.state.tick,
                "type": "campaign_complete",
                "location": "square",
                "action": self.state["final_outcome"]["summary"],
            })

        if events:
            self.engine.current_day_events.extend(events)
        return events

    def _seed_chapter_requests(self, chapter_id: str) -> None:
        from requests import seed_chapter_requests

        existing_ids = {request.id for request in self.engine.requests}
        for request in seed_chapter_requests(chapter_id):
            if request.id not in existing_ids:
                self.engine.requests.append(request)

    def _finish_chapter(self, chapter: ChapterDefinition, completed_day: int) -> None:
        if any(item.get("chapter_id") == chapter.id for item in self.state["chapter_history"]):
            return
        requests = [
            request for request in self.engine.requests
            if getattr(request, "chapter_id", "week_1_rain") == chapter.id
        ]
        completed = [request.id for request in requests if request.status == "completed"]
        unresolved = [request.id for request in requests if request.status == "active"]
        expired = [request.id for request in requests if request.status == "expired"]
        result = {
            "chapter_id": chapter.id,
            "week": chapter.week,
            "title": chapter.title,
            "completed_day": completed_day,
            "completed_requests": completed,
            "unresolved_requests": unresolved,
            "expired_requests": expired,
            "scores": copy.deepcopy(self.state["scores"]),
            "markers": copy.deepcopy(getattr(self.engine.world.state, "campaign_markers", {})),
        }
        self.state["chapter_history"].append(result)

    def record_request_effect(self, request, option, record_change: Optional[Callable] = None, result=None) -> None:
        """Record legacy week-one choices in the same campaign score ledger."""

        effect = option.effect
        legacy = {
            "lina_gather_wood": {"care": 1, "flag": {"wood_solution": "gathered"}},
            "lina_share_roof_plan": {"care": 1, "trust": 2, "flag": {"wood_solution": "planned"}},
            "lina_deliver_wood": {"care": 2, "trust": 2, "flag": {"wood_solution": "delivered"}},
            "torin_temporary_cover": {"safety": 1, "flag": {"roof_solution": "temporary"}},
            "torin_formal_repair": {"safety": 3, "trust": 1, "flag": {"roof_solution": "formal"}},
            "mei_listen_memory": {"trust": 1, "flag": {"chronicle_solution": "listened"}},
            "mei_organize_chronicle": {"care": 2, "trust": 1, "flag": {"chronicle_solution": "organized"}},
            "mei_check_rumor": {"safety": 1, "flag": {"chronicle_solution": "verified"}},
        }
        definition = legacy.get(effect)
        if definition:
            self._apply_definition(definition, request, option, record_change, result)

    def apply_effect(self, actor, request, option, action_result, record_change: Callable) -> bool:
        """Apply a data-defined effect and return whether it was recognized."""

        definition = CAMPAIGN_EFFECTS.get(option.effect)
        if not definition:
            return False
        self._apply_definition(definition, request, option, record_change, action_result, actor=actor)
        return True

    def _apply_definition(self, definition, request, option, record_change, result, actor=None) -> None:
        effect_id = option.effect
        flag = definition.get("flag", {})
        for key, value in flag.items():
            before = self.state["flags"].get(key)
            self.state["flags"][key] = value
            if record_change:
                record_change(result, "campaign", f"flag:{key}", before, value, effect_id)

        for key, delta in definition.get("scores", {}).items():
            before = int(self.state["scores"].get(key, 0))
            after = before + int(delta)
            self.state["scores"][key] = after
            if record_change:
                record_change(result, "campaign", f"score:{key}", before, after, effect_id)

        marker = definition.get("marker")
        if marker:
            markers = getattr(self.engine.world.state, "campaign_markers", {})
            for key, value in marker.items():
                before = markers.get(key)
                markers[key] = value
                if record_change:
                    record_change(result, "world", f"marker:{key}", before, value, effect_id)
            self.engine.world.state.campaign_markers = markers

        preparedness_delta = int(definition.get("preparedness", 0))
        if preparedness_delta:
            before = self.engine.world.state.lantern_fair_preparedness
            self.engine.world.state.lantern_fair_preparedness = max(0, before + preparedness_delta)
            if record_change:
                record_change(result, "world", "lantern_fair_preparedness", before,
                              self.engine.world.state.lantern_fair_preparedness, effect_id)

        requester = next((item for item in self.engine.agents if item.identity.id == request.requester_id), None)
        if requester is not None and actor is not None:
            delta = float(definition.get("requester_tie", 0))
            if delta:
                before = requester.state.social_ties.get(actor.identity.id, 0)
                requester.state.social_ties[actor.identity.id] = before + delta
                if record_change:
                    record_change(result, f"{requester.identity.id}:{actor.identity.id}", "tie",
                                  before, before + delta, effect_id)

        knowledge = definition.get("knowledge")
        if knowledge and actor is not None:
            claim = self.engine.knowledge.observe_with_action(
                actor.identity.id,
                knowledge["subject"],
                knowledge["claim"],
                request.location,
                confidence=float(knowledge.get("confidence", 0.7)),
                action_type="campaign_choice",
                action_target=request.location,
            )
            if record_change:
                record_change(result, actor.identity.id, "knowledge", "无", claim.id, effect_id)

    def payload(self, day: Optional[int] = None) -> Dict[str, Any]:
        day = int(day if day is not None else self.engine.current_day)
        chapter = self.active_chapter
        next_chapter = next((item for item in CHAPTERS if item.unlock_day > day), None)
        active_requests = [
            request.id for request in self.engine.requests
            if getattr(request, "chapter_id", "week_1_rain") == chapter.id
            and request.status == "active"
        ]
        return {
            "schema_version": CAMPAIGN_STATE_VERSION,
            "week": chapter.week,
            "chapter_id": chapter.id,
            "title": chapter.title,
            "subtitle": chapter.subtitle,
            "pressure": chapter.pressure,
            "objective": chapter.objective,
            "day": day,
            "day_in_chapter": max(1, day - chapter.unlock_day + 1),
            "days_until_next": max(0, next_chapter.unlock_day - day) if next_chapter else 0,
            "next_chapter": {"week": next_chapter.week, "title": next_chapter.title,
                              "unlock_day": next_chapter.unlock_day} if next_chapter else None,
            "active_request_ids": active_requests,
            "flags": copy.deepcopy(self.state["flags"]),
            "scores": copy.deepcopy(self.state["scores"]),
            "markers": copy.deepcopy(getattr(self.engine.world.state, "campaign_markers", {})),
            "unlocked_chapters": list(self.state["unlocked_chapters"]),
            "chapter_history": copy.deepcopy(self.state["chapter_history"]),
            "final_outcome": copy.deepcopy(self.state.get("final_outcome")),
            "chapters": [
                {
                    "id": item.id,
                    "week": item.week,
                    "title": item.title,
                    "subtitle": item.subtitle,
                    "unlock_day": item.unlock_day,
                    "status": (
                        "current" if item.id == chapter.id else
                        "unlocked" if item.id in self.state["unlocked_chapters"] else
                        "upcoming"
                    ),
                }
                for item in CHAPTERS
            ],
        }

    def _build_final_outcome(self) -> Dict[str, Any]:
        scores = self.state["scores"]
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        lead = ranked[0][0] if ranked else "trust"
        descriptions = {
            "care": "小镇先记住了谁需要被照顾。归灯集的灯没有最亮，却照到了最容易被漏掉的人。",
            "safety": "小镇先记住了如何确认危险。商队绕开了不稳的路，也愿意把这份谨慎带回来。",
            "trust": "小镇先记住了公开商量的习惯。居民不再等一个人替大家做决定。",
            "welcome": "小镇先记住了开放的勇气。新的脚步走进来时，居民仍保留了自己的声音。",
        }
        return {
            "headline": f"第4周结束：{descriptions.get(lead, descriptions['trust'])}",
            "summary": f"归灯集结束了。{descriptions.get(lead, descriptions['trust'])}",
            "lead_value": lead,
            "scores": copy.deepcopy(scores),
            "markers": copy.deepcopy(getattr(self.engine.world.state, "campaign_markers", {})),
        }


__all__ = [
    "CAMPAIGN_STATE_VERSION", "CAMPAIGN_EFFECTS", "CHAPTERS", "ChapterDefinition",
    "CampaignDirector", "chapter_for_day",
]
