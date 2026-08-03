"""SQLite数据库持久化模块"""
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = "k_town.db"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表"""
        cursor = self.conn.cursor()
        # 每日摘要表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day INTEGER NOT NULL,
                weather TEXT NOT NULL,
                overall_summary TEXT NOT NULL,
                stats JSON NOT NULL,
                agents JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Agent行为日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                behaviors JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 世界状态快照表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS world_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                day INTEGER NOT NULL,
                state JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 事件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                day INTEGER NOT NULL,
                type TEXT NOT NULL,
                location TEXT NOT NULL,
                payload JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def reset(self):
        """重置数据库，清空所有数据"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM day_summaries")
        cursor.execute("DELETE FROM agent_logs")
        cursor.execute("DELETE FROM world_snapshots")
        cursor.execute("DELETE FROM events")
        self.conn.commit()
    
    def save_day_summary(self, summary: Dict[str, Any]):
        """保存每日摘要"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO day_summaries (day, weather, overall_summary, stats, agents)
            VALUES (?, ?, ?, ?, ?)
        """, (
            summary["day"],
            summary["weather"],
            summary["overall_summary"],
            json.dumps(summary["stats"], ensure_ascii=False),
            json.dumps(summary["agents"], ensure_ascii=False)
        ))
        self.conn.commit()
    
    def get_day_summaries(self, limit: int = 30) -> List[Dict[str, Any]]:
        """获取最近的每日摘要"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT day, weather, overall_summary, stats, agents, created_at
            FROM day_summaries
            ORDER BY day DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [
            {
                "day": row[0],
                "weather": row[1],
                "overall_summary": row[2],
                "stats": json.loads(row[3]),
                "agents": json.loads(row[4]),
                "created_at": row[5]
            }
            for row in rows
        ][::-1]  # 反转顺序，从早到晚
    
    def save_agent_log(self, day: int, agent_id: str, agent_name: str, behaviors: List[str]):
        """保存Agent行为日志"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO agent_logs (day, agent_id, agent_name, behaviors)
            VALUES (?, ?, ?, ?)
        """, (day, agent_id, agent_name, json.dumps(behaviors, ensure_ascii=False)))
        self.conn.commit()
    
    def get_agent_logs(self, day: int, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取指定日期的Agent行为日志"""
        cursor = self.conn.cursor()
        if agent_id:
            cursor.execute("""
                SELECT agent_id, agent_name, behaviors
                FROM agent_logs
                WHERE day = ? AND agent_id = ?
                ORDER BY created_at DESC
            """, (day, agent_id))
        else:
            cursor.execute("""
                SELECT agent_id, agent_name, behaviors
                FROM agent_logs
                WHERE day = ?
                ORDER BY created_at DESC
            """, (day,))
        rows = cursor.fetchall()
        return [
            {
                "agent_id": row[0],
                "agent_name": row[1],
                "behaviors": json.loads(row[2])
            }
            for row in rows
        ]
    
    def save_world_snapshot(self, tick: int, day: int, state: Dict[str, Any]):
        """保存世界状态快照（每24 tick保存一次）"""
        if tick % 24 == 0:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO world_snapshots (tick, day, state)
                VALUES (?, ?, ?)
            """, (tick, day, json.dumps(state, ensure_ascii=False)))
            self.conn.commit()
    
    def get_world_snapshot(self, day: int) -> Optional[Dict[str, Any]]:
        """获取指定日期的世界状态快照"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT state
            FROM world_snapshots
            WHERE day = ?
            ORDER BY tick DESC
            LIMIT 1
        """, (day,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None
    
    def save_event(self, tick: int, day: int, event_type: str, location: str, payload: Dict[str, Any]):
        """保存事件到数据库"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO events (tick, day, type, location, payload)
            VALUES (?, ?, ?, ?, ?)
        """, (tick, day, event_type, location, json.dumps(payload, ensure_ascii=False)))
        self.conn.commit()
    
    def get_events(self, day: int) -> List[Dict[str, Any]]:
        """获取指定日期的事件列表"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT tick, type, location, payload, created_at
            FROM events
            WHERE day = ?
            ORDER BY tick ASC
        """, (day,))
        rows = cursor.fetchall()
        return [
            {
                "tick": row[0],
                "type": row[1],
                "location": row[2],
                "payload": json.loads(row[3]),
                "created_at": row[4]
            }
            for row in rows
        ]
    
    def close(self):
        self.conn.close()
