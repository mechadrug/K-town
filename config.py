"""Configuration loader for K-town server."""
import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServerConfig:
    ws_port: int = 8080
    http_port: int = 8080


@dataclass
class TickConfig:
    rate: float = 1.0  # seconds per tick
    day_length: int = 24


@dataclass
class WorldConfig:
    locations: int = 3
    agents: int = 10


@dataclass
class LLMConfig:
    provider: str = "longcat"
    base_url: str = "https://api.longcat.chat/anthropic"
    api_key: str = ""
    model: str = "LongCat-2.0"
    max_calls_per_tick: int = 2


@dataclass
class LoggingConfig:
    level: str = "info"
    output: str = "stdout"
    persist: bool = False


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    tick: TickConfig = field(default_factory=TickConfig)
    world: WorldConfig = field(default_factory=WorldConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


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
    if "world" in data:
        cfg.world = WorldConfig(**{k: v for k, v in data["world"].items() if k in WorldConfig.__dataclass_fields__})
    if "llm" in data:
        cfg.llm = LLMConfig(**{k: v for k, v in data["llm"].items() if k in LLMConfig.__dataclass_fields__})
    if "logging" in data:
        cfg.logging = LoggingConfig(**{k: v for k, v in data["logging"].items() if k in LoggingConfig.__dataclass_fields__})
    
    # Check env var for API key
    env_key = os.environ.get("LLM_API_KEY")
    if env_key:
        cfg.llm.api_key = env_key
    
    return cfg

