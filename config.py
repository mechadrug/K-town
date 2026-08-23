"""Configuration loader for K-town server."""
import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServerConfig:
    http_port: int = 8090
    db_path: str = "k_town.db"  # SQLite 数据库路径（测试用临时库，禁止指向运行中的默认库）
    reset_on_start: bool = False  # 启动即清空数据库（新游戏）；False = 继续游戏（部分恢复）


@dataclass
class TickConfig:
    day_length: int = 20  # 世界观：一天 20 小时
    waking_hours: int = 12  # 玩家清醒小时数 = 每日 AP 数
    wake_hour: int = 5  # 清晨醒来时刻（余下 20-12=8 小时为睡眠）


@dataclass
class LLMConfig:
    provider: str = "longcat"
    base_url: str = "https://api.longcat.chat/anthropic"
    api_key: str = ""
    model: str = "LongCat-2.0"


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    tick: TickConfig = field(default_factory=TickConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


def load_config(path: str = "config.yaml") -> Config:
    """Load config from YAML file, fall back to defaults."""
    cfg = Config()
    if not os.path.exists(path):
        print(f"[config] {path} not found, using defaults")
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    if "server" in data:
        cfg.server = ServerConfig(**{k: v for k, v in data["server"].items() if k in ServerConfig.__dataclass_fields__})
    if "tick" in data:
        cfg.tick = TickConfig(**{k: v for k, v in data["tick"].items() if k in TickConfig.__dataclass_fields__})
    if "llm" in data:
        cfg.llm = LLMConfig(**{k: v for k, v in data["llm"].items() if k in LLMConfig.__dataclass_fields__})

    # Check env var for API key
    env_key = os.environ.get("LLM_API_KEY")
    if env_key:
        cfg.llm.api_key = env_key
    
    return cfg

