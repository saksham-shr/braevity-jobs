import os
from pathlib import Path
import yaml


def config_dir() -> Path:
    env = os.environ.get("BRAEVITY_HOME")
    if env:
        return Path(env)
    return Path.home() / ".braevity"


def config_path() -> Path:
    return config_dir() / "config.yaml"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(data: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
