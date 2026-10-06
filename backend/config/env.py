"""Lightweight environment loader using Python standard library only.
Reads .env from the project root and populates os.environ.
"""
import os
from pathlib import Path

# Project root is two levels up from backend/config/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


def load_env(env_path: Path = ENV_FILE) -> None:
    if not env_path.is_file():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            os.environ.setdefault(key, val)


def get_env(key: str, default: str = "", cast=None):
    val = os.environ.get(key, default)
    if cast is bool:
        return str(val).lower() in ("true", "1", "yes", "t")
    if cast is int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    if cast:
        return cast(val)
    return val


load_env()
