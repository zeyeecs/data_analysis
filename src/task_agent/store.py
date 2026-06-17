from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.task_agent.definitions import DEFINITION_BY_TYPE, build_task_label

MAX_RECENT_TASKS = 20
_lock = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def tasks_dir() -> Path:
    override = os.environ.get("SJKX_TASK_DIR")
    if override:
        return Path(override)
    return _repo_root() / "logs" / "ai-tasks"


def state_path() -> Path:
    return tasks_dir() / "state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _empty_state() -> dict[str, Any]:
    return {"tasks": [], "runningTaskId": None}


def _read_state_unlocked() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(data.get("tasks"), list):
        return _empty_state()
    return {"tasks": data["tasks"], "runningTaskId": data.get("runningTaskId")}


def _write_state_unlocked(state: dict[str, Any]) -> None:
    directory = tasks_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path()
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def create_task(task_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    definition = DEFINITION_BY_TYPE.get(task_type)
    if not definition:
        raise ValueError(f"未知任务类型: {task_type}")
    if definition.get("requiresTable") and not params.get("table"):
        raise ValueError("该任务需要指定竞品表（F / R / V）")

    task = {
        "id": str(uuid.uuid4()),
        "type": task_type,
        "label": build_task_label(task_type, params),
        "description": definition["description"],
        "params": params,
        "status": "pending",
        "createdAt": _now_iso(),
        "startedAt": None,
        "finishedAt": None,
        "logFile": None,
        "exitCode": None,
        "error": None,
    }

    with _lock:
        state = _read_state_unlocked()
        state["tasks"].insert(0, task)
        _write_state_unlocked(state)
    return task


def get_task(task_id: str) -> dict[str, Any] | None:
    with _lock:
        state = _read_state_unlocked()
        for task in state["tasks"]:
            if task["id"] == task_id:
                return task
    return None


def list_snapshot() -> dict[str, Any]:
    with _lock:
        state = _read_state_unlocked()
        tasks = state["tasks"]
        pending = [task for task in tasks if task.get("status") == "pending"]
        running = next(
            (
                task
                for task in tasks
                if task.get("id") == state.get("runningTaskId") and task.get("status") == "running"
            ),
            None,
        )
        if running is None:
            running = next((task for task in tasks if task.get("status") == "running"), None)
        recent = [
            task
            for task in tasks
            if task.get("status") in {"completed", "failed", "cancelled"}
        ][:MAX_RECENT_TASKS]
        return {"pending": pending, "running": running, "recent": recent}


def get_running_task_id() -> str | None:
    with _lock:
        return _read_state_unlocked().get("runningTaskId")


def set_running_task_id(task_id: str | None) -> None:
    with _lock:
        state = _read_state_unlocked()
        state["runningTaskId"] = task_id
        _write_state_unlocked(state)


def get_next_pending() -> dict[str, Any] | None:
    with _lock:
        state = _read_state_unlocked()
        return next((task for task in state["tasks"] if task.get("status") == "pending"), None)


def mark_running(task_id: str, log_file: str) -> dict[str, Any] | None:
    with _lock:
        state = _read_state_unlocked()
        for index, task in enumerate(state["tasks"]):
            if task["id"] != task_id:
                continue
            updated = {
                **task,
                "status": "running",
                "startedAt": _now_iso(),
                "logFile": log_file,
                "exitCode": None,
                "error": None,
            }
            state["tasks"][index] = updated
            state["runningTaskId"] = task_id
            _write_state_unlocked(state)
            return updated
    return None


def finalize_task(
    task_id: str,
    status: str,
    exit_code: int | None,
    error: str | None,
) -> dict[str, Any] | None:
    with _lock:
        state = _read_state_unlocked()
        if state.get("runningTaskId") == task_id:
            state["runningTaskId"] = None
        for index, task in enumerate(state["tasks"]):
            if task["id"] != task_id:
                continue
            updated = {
                **task,
                "status": status,
                "finishedAt": _now_iso(),
                "exitCode": exit_code,
                "error": error,
            }
            state["tasks"][index] = updated
            _write_state_unlocked(state)
            return updated
    return None


def cancel_pending(task_id: str) -> dict[str, Any] | None:
    with _lock:
        state = _read_state_unlocked()
        for index, task in enumerate(state["tasks"]):
            if task["id"] != task_id or task.get("status") != "pending":
                continue
            updated = {**task, "status": "cancelled", "finishedAt": _now_iso()}
            state["tasks"][index] = updated
            _write_state_unlocked(state)
            return updated
    return None
