import os
from pathlib import Path
import yaml

def config_dir() -> Path:
    custom_path = os.environ.get("BRAEVITY_HOME")

    if custom_path:
        dir_path = Path(custom_path)
    else:
        dir_path = Path.home() / ".braevity"
    return dir_path

def config_path() -> Path:
    return config_dir() / "config.yaml"

def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def save_config(config: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(config, f)   