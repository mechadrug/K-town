"""日志系统模块"""
import sqlite3
import json
from typing import List, Dict, Any
from datetime import datetime

DB_PATH = "k_town.db"

class Logger:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_tables()
    
    def _init_tables(self):
        """初始化日志表"""
        cursor = self.conn.cursor()
        # 世界事件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS world_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                type TEXT NOT NULL,
                location TEXT NOT NULL,
                agents JSON,
                payload JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Agent决策表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                action_desc TEXT NOT NULL,
                action_type TEXT NOT NULL,
                goal TEXT NOT NULL,
                confidence FLOAT NOT NULL,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 知识变化表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_changes (
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
        # 玩家操作表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                payload JSON NOT NULL,
                result TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def log_world_event(self, tick, type, location, agents=None, payload=None):
        """记录世界事件"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO world_events (tick, type, location, agents, payload)
            VALUES (?, ?, ?, ?, ?)
        """, (tick, type, location, json.dumps(agents or []), json.dumps(payload or {})))
        self.conn.commit()
    
    def log_decision(self, tick, agent_id, action_desc, action_type, goal, confidence, source):
        """记录Agent决策"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO agent_decisions (tick, agent_id, action_desc, action_type, goal, confidence, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tick, agent_id, action_desc, action_type, goal, confidence, source))
        self.conn.commit()
    
    def log_knowledge(self, tick, claim_id, agent_id, action, old_value, new_value):
        """记录知识变化"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO knowledge_changes (tick, claim_id, agent_id, action, old_value, new_value)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tick, claim_id, agent_id, action, old_value, new_value))
        self.conn.commit()
    
    def log_player_action(self, player_action):
        """记录玩家操作"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO player_actions (tick, action_type, payload, result)
            VALUES (?, ?, ?, ?)
        """, (player_action.tick, player_action.action_type, json.dumps(player_action.payload, ensure_ascii=False), player_action.result))
        self.conn.commit()
    
    def query_world_events(self, limit=100):
        """查询世界事件"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT tick, type, location, agents, payload, created_at
            FROM world_events
            ORDER BY tick DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [
            {
                "tick": row[0],
                "type": row[1],
                "location": row[2],
                "agents": json.loads(row[3]) if row[3] else [],
                "payload": json.loads(row[4]) if row[4] else {},
                "created_at": row[5]
            }
            for row in rows
        ][::-1]
    
    def query_decisions(self, limit=50):
        """查询Agent决策"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT tick, agent_id, action_desc, action_type, goal, confidence, source, created_at
            FROM agent_decisions
            ORDER BY tick DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [
            {
                "tick": row[0],
                "agent_id": row[1],
                "action_desc": row[2],
                "action_type": row[3],
                "goal": row[4],
                "confidence": row[5],
                "source": row[6],
                "created_at": row[7]
            }
            for row in rows
        ][::-1]
    
    def query_player_actions(self, limit=50):
        """查询玩家操作"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT tick, action_type, payload, result, created_at
            FROM player_actions
            ORDER BY tick DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [
            {
                "tick": row[0],
                "action_type": row[1],
                "payload": json.loads(row[2]) if row[2] else {},
                "result": row[3],
                "created_at": row[4]
            }
            for row in rows
        ][::-1]
    
    def reset(self):
        """重置日志"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM world_events")
        cursor.execute("DELETE FROM agent_decisions")
        cursor.execute("DELETE FROM knowledge_changes")
        cursor.execute("DELETE FROM player_actions")
        self.conn.commit()
    
    def close(self):
        self.conn.close()
