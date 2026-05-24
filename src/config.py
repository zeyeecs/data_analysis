from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> None:
    """加载 .env / database.env。database.env 优先于 shell 中同名变量（避免错误 DATABASE_URL 污染）。"""
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "database.env", override=True)


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def feishu_folders() -> dict[str, str]:
    return {
        "F": env("FEISHU_FOLDER_F"),
        "R": env("FEISHU_FOLDER_R"),
        "V": env("FEISHU_FOLDER_V"),
        "F_SOURCE": env("FEISHU_FOLDER_F_SOURCE"),
        "R_SOURCE": env("FEISHU_FOLDER_R_SOURCE"),
        "V_SOURCE": env("FEISHU_FOLDER_V_SOURCE"),
    }
