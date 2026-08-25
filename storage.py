"""统一数据访问层 —— K-town 唯一持久化入口。

替代旧的 db.py / database.py / logger.py / static_db.py 四套互不兼容实现。

设计要点：
- 单一 sqlite 连接（WAL + busy_timeout），全程复用，消除多写者竞争。
- _init_schema() 通过 town_meta 里的 schema_version 检测；版本不符时重建全部
  受管表，从根上消除“表不存在 / 列不匹配”这类 schema 漂移崩溃。
- 同时暴露 Logger 风格（log_* / query_*）与 Database 风格（save_*/get_*）方法，
  供 main / tick / api 三处统一调用。
"""

import sqlite3
import json
import time
import threading
from typing import Any, Dict, List, Optional

DB_PATH = "k_town.db"

# 受本层管理、可按版本重建的表
_MANAGED_TABLES = [
    "world_events",
    "agent_decisions",
    "knowledge_changes",
    "player_actions",
    "day_summaries",
    "world_snapshots",
    "agent_logs",
    "knowledge_pool",
    "knowledge_distribution",
    "agent_states",
    "game_states",
    "town_meta",
]

SCHEMA_VERSION = 6


class Storage:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        # FastAPI's test client and the websocket server may call the shared
        # storage object from different threads.  SQLite still serializes the
        # short critical sections below through this re-entrant lock.
        self._lock = threading.RLock()

    @property
    def conn(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    self.db_path, timeout=10, check_same_thread=False
                )
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA busy_timeout=5000")
                self._init_schema()
            return self._conn

    # ------------------------------------------------------------------ schema

    def _init_schema(self) -> None:
        """初始化/重建权威表结构。schema 版本不符时重建（丢弃旧占位数据）。"""
        version = self._get_schema_version()
        if version is not None and version == SCHEMA_VERSION:
            self._create_indexes()
            return
        # v4 只有决策表缺少 Phase 2 因果字段，做原地迁移，保留已有回放数据。
        if version == 4:
            self._migrate_v4_to_v5()
            self._migrate_v5_to_v6()
            self._set_schema_version(SCHEMA_VERSION)
            self._create_indexes()
            return
        # v6 adds a single versioned game-state slot.  Keep v5 logs and saves
        # intact instead of rebuilding the managed tables during an upgrade.
        if version == 5:
            self._migrate_v5_to_v6()
            self._set_schema_version(SCHEMA_VERSION)
            self._create_indexes()
            return
        # 首次建表或版本升级：重建全部受管表
        for table in _MANAGED_TABLES:
            try:
                self._conn.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass
        self._create_tables()
        self._set_schema_version(SCHEMA_VERSION)
        self._create_indexes()
        try:
            self._conn.execute("VACUUM")
        except Exception:
            pass

    def _migrate_v4_to_v5(self) -> None:
        """为决策日志增加感知/原因/变化字段，不丢弃已有存档。"""
        columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(agent_decisions)").fetchall()
        }
        additions = {
            "observations": "JSON",
            "reason": "TEXT",
            "changes": "JSON",
            "next_observation": "TEXT",
        }
        for name, ddl in additions.items():
            if name not in columns:
                self._conn.execute(f"ALTER TABLE agent_decisions ADD COLUMN {name} {ddl}")
        self._conn.commit()

    def _migrate_v5_to_v6(self) -> None:
        """Add the versioned full-state save slot without dropping v5 history."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS game_states (
                slot TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                state JSON NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def _get_schema_version(self) -> Optional[int]:
        try:
            row = self._conn.execute(
                "SELECT value FROM town_meta WHERE key='schema_version'"
            ).fetchone()
        except Exception:
            return None
        if not row:
            return None
        try:
            v = row["value"]
            # JSON 类型列可能已被 sqlite3 自动反序列化为 int/str
            return v if isinstance(v, int) else int(json.loads(v))
        except Exception:
            return None

    def _set_schema_version(self, version: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO town_meta (key, value, updated_at) VALUES ('schema_version', ?, ?)",
            (json.dumps(version), time.time()),
        )
        self._conn.commit()

    def _create_tables(self) -> None:
        c = self._conn.cursor()

        # ---- 日志类（Logger 职责）----
        c.execute("""
            CREATE TABLE world_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                day INTEGER NOT NULL DEFAULT 0,
                type TEXT NOT NULL,
                location TEXT NOT NULL,
                agents JSON,
                payload JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE agent_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                action_desc TEXT NOT NULL,
                action_type TEXT NOT NULL,
                goal TEXT NOT NULL,
                confidence FLOAT NOT NULL,
                source TEXT NOT NULL,
                observations JSON,
                reason TEXT,
                changes JSON,
                next_observation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE knowledge_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                claim_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                action TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE player_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                payload JSON NOT NULL,
                result TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ---- 世界状态类（Database 职责）----
        c.execute("""
            CREATE TABLE day_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day INTEGER NOT NULL UNIQUE,
                weather TEXT NOT NULL,
                overall_summary TEXT NOT NULL,
                stats JSON,
                agents JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE world_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                day INTEGER NOT NULL,
                state JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                agent_name TEXT,
                behaviors JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE agent_states (
                agent_id TEXT PRIMARY KEY,
                state JSON,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE game_states (
                slot TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                state JSON NOT NULL,
                updated_at REAL NOT NULL
            )
        """)

        # ---- 知识持久化（KnowledgeClaim）----
        c.execute("""
            CREATE TABLE knowledge_pool (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                claim TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                scope TEXT NOT NULL,
                created_by TEXT NOT NULL,
                location TEXT NOT NULL,
                actionable INTEGER DEFAULT 0,
                action_type TEXT DEFAULT '',
                action_target TEXT DEFAULT '',
                emotional_valence REAL DEFAULT 0.0,
                target_agent_ids JSON DEFAULT '[]',
                solidified INTEGER DEFAULT 0,
                version INTEGER DEFAULT 1,
                created_day INTEGER NOT NULL,
                created_at REAL NOT NULL,
                contradicted_by JSON DEFAULT '[]'
            )
        """)
        c.execute("""
            CREATE TABLE knowledge_distribution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                received_day INTEGER NOT NULL,
                confidence_at_receive REAL NOT NULL,
                UNIQUE(knowledge_id, agent_id)
            )
        """)
        c.execute("""
            CREATE TABLE town_meta (
                key TEXT PRIMARY KEY,
                value JSON NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def _create_indexes(self) -> None:
        for ddl in (
            "CREATE INDEX IF NOT EXISTS idx_world_events_tick_day ON world_events(tick, day)",
            "CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent_tick ON agent_decisions(agent_id, tick)",
            "CREATE INDEX IF NOT EXISTS idx_world_snapshots_day ON world_snapshots(day)",
            "CREATE INDEX IF NOT EXISTS idx_agent_logs_day ON agent_logs(day)",
            "CREATE INDEX IF NOT EXISTS idx_kd_knowledge ON knowledge_distribution(knowledge_id)",
        ):
            try:
                self._conn.execute(ddl)
            except Exception:
                pass
        self._conn.commit()

    # ------------------------------------------------------------------ 世界事件

    def log_world_event(self, tick: int, type: str, location: str,
                        agents: Optional[list] = None, payload: Optional[dict] = None) -> None:
        self.conn.execute(
            "INSERT INTO world_events (tick, type, location, agents, payload) VALUES (?, ?, ?, ?, ?)",
            (tick, type, location, json.dumps(agents or []), json.dumps(payload or {}, ensure_ascii=False)),
        )
        self.conn.commit()

    def query_world_events(self, limit: int = 100) -> List[dict]:
        rows = self.conn.execute(
            "SELECT tick, day, type, location, agents, payload, created_at FROM world_events ORDER BY tick DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = [self._world_event_row(r) for r in rows]
        out.reverse()
        return out

    @staticmethod
    def _world_event_row(r: sqlite3.Row) -> dict:
        return {
            "tick": r["tick"],
            "day": r["day"],
            "type": r["type"],
            "location": r["location"],
            "agents": json.loads(r["agents"]) if r["agents"] else [],
            "payload": json.loads(r["payload"]) if r["payload"] else {},
            "created_at": r["created_at"],
        }

    # ------------------------------------------------------------------ 决策/知识/玩家日志

    def log_decision(self, tick: int, agent_id: str, action_desc: str, action_type: str,
                     goal: str, confidence: float, source: str,
                     observations: Optional[list] = None, reason: str = "",
                     changes: Optional[list] = None,
                     next_observation: Optional[str] = None) -> None:
        self.conn.execute(
            "INSERT INTO agent_decisions (tick, agent_id, action_desc, action_type, goal, confidence, source, observations, reason, changes, next_observation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tick, agent_id, action_desc, action_type, goal, confidence, source,
             json.dumps(observations or [], ensure_ascii=False), reason,
             json.dumps(changes or [], ensure_ascii=False), next_observation),
        )
        self.conn.commit()

    def query_decisions(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT tick, agent_id, action_desc, action_type, goal, confidence, source, observations, reason, changes, next_observation, created_at FROM agent_decisions ORDER BY tick DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["observations"] = json.loads(item["observations"]) if item.get("observations") else []
            item["changes"] = json.loads(item["changes"]) if item.get("changes") else []
            out.append(item)
        out.reverse()
        return out

    def log_knowledge(self, tick: int, claim_id: str, agent_id: str, action: str,
                      old_value: str, new_value: str) -> None:
        self.conn.execute(
            "INSERT INTO knowledge_changes (tick, claim_id, agent_id, action, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?)",
            (tick, claim_id, agent_id, action, old_value, new_value),
        )
        self.conn.commit()

    def log_player_action(self, player_action) -> None:
        self.conn.execute(
            "INSERT INTO player_actions (tick, action_type, payload, result) VALUES (?, ?, ?, ?)",
            (player_action.tick, player_action.action_type,
             json.dumps(player_action.payload, ensure_ascii=False), player_action.result),
        )
        self.conn.commit()

    def query_player_actions(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT tick, action_type, payload, result, created_at FROM player_actions ORDER BY tick DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = [{
            "tick": r["tick"], "action_type": r["action_type"],
            "payload": json.loads(r["payload"]) if r["payload"] else {},
            "result": r["result"], "created_at": r["created_at"],
        } for r in rows]
        out.reverse()
        return out

    # ------------------------------------------------------------------ 每日摘要

    def save_day_summary(self, summary: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO day_summaries (day, weather, overall_summary, stats, agents) VALUES (?, ?, ?, ?, ?)",
            (summary["day"], summary["weather"], summary["overall_summary"],
             json.dumps(summary["stats"], ensure_ascii=False),
             json.dumps({
                 "agents": summary["agents"],
                 "causal_beats": summary.get("causal_beats", []),
             }, ensure_ascii=False)),
        )
        self.conn.commit()

    def get_day_summaries(self, limit: int = 30) -> List[dict]:
        try:
            rows = self.conn.execute(
                "SELECT day, weather, overall_summary, stats, agents FROM day_summaries ORDER BY day DESC LIMIT ?",
                (limit,),
            ).fetchall()
        except Exception:
            return []
        out = []
        for r in rows:
            agent_blob = json.loads(r["agents"]) if r["agents"] else []
            if isinstance(agent_blob, dict):
                agents = agent_blob.get("agents", [])
                causal_beats = agent_blob.get("causal_beats", [])
            else:
                agents = agent_blob
                causal_beats = []
            out.append({
                "day": r["day"], "weather": r["weather"], "overall_summary": r["overall_summary"],
                "stats": json.loads(r["stats"]) if r["stats"] else {},
                "agents": agents, "causal_beats": causal_beats,
            })
        out.reverse()
        return out

    # ------------------------------------------------------------------ 世界快照

    def save_world_snapshot(self, tick: int, day: int, state: dict) -> None:
        self.conn.execute(
            "INSERT INTO world_snapshots (tick, day, state) VALUES (?, ?, ?)",
            # default=str：世界状态中可能含 dataclass（如 TradeOffer），降级为字符串避免崩溃
            (tick, day, json.dumps(state, ensure_ascii=False, default=str)),
        )
        self.conn.commit()

    save_snapshot = save_world_snapshot  # 兼容旧调用名

    def get_world_snapshot(self, day: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT state FROM world_snapshots WHERE day = ? ORDER BY tick DESC LIMIT 1",
            (day,),
        ).fetchone()
        return json.loads(row["state"]) if row else None

    get_snapshot = get_world_snapshot

    # ------------------------------------------------------------------ Versioned game state

    def save_game_state(self, state: Dict[str, Any], slot: str = "current") -> None:
        """Atomically replace the current full simulation snapshot."""
        schema_version = int(state.get("schema_version", 1))
        payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO game_states (slot, schema_version, state, updated_at) VALUES (?, ?, ?, ?)",
                (slot, schema_version, payload, time.time()),
            )
            self.conn.commit()

    def load_game_state(self, slot: str = "current") -> Optional[Dict[str, Any]]:
        """Return a complete save snapshot, or ``None`` when no v6 save exists."""
        try:
            row = self.conn.execute(
                "SELECT state FROM game_states WHERE slot = ?", (slot,)
            ).fetchone()
        except Exception:
            return None
        if not row:
            return None
        try:
            return json.loads(row["state"])
        except (TypeError, json.JSONDecodeError):
            return None

    # ------------------------------------------------------------------ Agent 行为日志

    def save_agents_state(self, agents_state: list) -> None:
        """存档：保存全部 Agent 完整状态（含情绪/习惯/性格/关系/技能/日记）。"""
        for s in agents_state:
            self.conn.execute(
                "INSERT OR REPLACE INTO agent_states (agent_id, state) VALUES (?, ?)",
                (s["id"], json.dumps(s, ensure_ascii=False)),
            )
        self.conn.commit()

    def load_agents_state(self) -> List[dict]:
        """读档：恢复全部 Agent 状态（空表返回空列表）。"""
        rows = self.conn.execute("SELECT agent_id, state FROM agent_states").fetchall()
        return [json.loads(r["state"]) for r in rows]

    def save_agent_log(self, day: int, agent_id: str, agent_name: str, behaviors: list) -> None:
        self.conn.execute(
            "INSERT INTO agent_logs (day, agent_id, agent_name, behaviors) VALUES (?, ?, ?, ?)",
            (day, agent_id, agent_name, json.dumps(behaviors, ensure_ascii=False)),
        )
        self.conn.commit()

    def get_agent_logs(self, day: int, agent_id: Optional[str] = None) -> List[dict]:
        if agent_id:
            rows = self.conn.execute(
                "SELECT day, agent_id, agent_name, behaviors FROM agent_logs WHERE day = ? AND agent_id = ? ORDER BY id",
                (day, agent_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT day, agent_id, agent_name, behaviors FROM agent_logs WHERE day = ? ORDER BY id",
                (day,),
            ).fetchall()
        return [{
            "day": r["day"], "agent_id": r["agent_id"], "agent_name": r["agent_name"],
            "behaviors": json.loads(r["behaviors"]) if r["behaviors"] else [],
        } for r in rows]

    # ------------------------------------------------------------------ 事件存储

    def save_event(self, tick: int, day: int, event_type: str, location: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO world_events (tick, day, type, location, payload) VALUES (?, ?, ?, ?, ?)",
            (tick, day, event_type, location, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()

    def get_events(self, day: int) -> List[dict]:
        rows = self.conn.execute(
            "SELECT tick, day, type, location, payload FROM world_events WHERE day = ? ORDER BY tick ASC",
            (day,),
        ).fetchall()
        return [{
            "tick": r["tick"], "day": r["day"], "type": r["type"], "location": r["location"],
            "payload": json.loads(r["payload"]) if r["payload"] else {},
        } for r in rows]

    # ------------------------------------------------------------------ 知识持久化

    def add_knowledge(self, claim: Dict[str, Any], target_agent_ids: Optional[List[str]] = None) -> str:
        self.conn.execute(
            "INSERT OR REPLACE INTO knowledge_pool (id, subject, claim, source, confidence, scope, created_by, location, "
            "actionable, action_type, action_target, emotional_valence, target_agent_ids, solidified, version, created_day, created_at, contradicted_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (claim["id"], claim.get("subject", ""), claim.get("claim", ""), claim.get("source", "observation"),
             claim.get("confidence", 0.6), claim.get("scope", "private"), claim.get("created_by", ""),
             claim.get("location", ""), 1 if claim.get("actionable") else 0, claim.get("action_type", ""),
             claim.get("action_target", ""), claim.get("emotional_valence", 0.0),
             json.dumps(target_agent_ids or []), 1 if claim.get("solidified") else 0,
             claim.get("version", 1), claim.get("created_day", 1), claim.get("created_at", time.time()),
             json.dumps(claim.get("contradicted_by", []))),
        )
        self.conn.commit()
        return claim["id"]

    # ------------------------------------------------------------------ 元数据

    def get_knowledge_pool(self) -> List[dict]:
        """获取知识池全部知识（用于引擎断点恢复 / 审计）"""
        try:
            rows = self.conn.execute("SELECT * FROM knowledge_pool").fetchall()
        except Exception:
            return []
        return [self._knowledge_row_to_dict(r) for r in rows]

    @staticmethod
    def _knowledge_row_to_dict(r: sqlite3.Row) -> dict:
        return {
            "id": r["id"],
            "subject": r["subject"],
            "claim": r["claim"],
            "source": r["source"],
            "confidence": r["confidence"],
            "scope": r["scope"],
            "created_by": r["created_by"],
            "location": r["location"],
            "actionable": bool(r["actionable"]),
            "action_type": r["action_type"],
            "action_target": r["action_target"],
            "emotional_valence": r["emotional_valence"],
            "target_agent_ids": json.loads(r["target_agent_ids"]) if r["target_agent_ids"] else [],
            "solidified": bool(r["solidified"]),
            "version": r["version"],
            "contradicted_by": json.loads(r["contradicted_by"]) if r["contradicted_by"] else [],
            "created_at": r["created_at"],
        }



    def reset(self) -> None:
        """清空全部受管表数据（保留 schema 与 schema_version）。"""
        for table in _MANAGED_TABLES:
            try:
                self.conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        # 关键修复：reset 清空了 town_meta（含 schema_version），必须重写，
        # 否则下次打开 _init_schema 检测不到版本 → 误判为首次建表 → 重建全部表（丢档）
        self._set_schema_version(SCHEMA_VERSION)
        self.conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
