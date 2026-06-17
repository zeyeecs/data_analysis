from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from src.task_agent import store

_active_process: subprocess.Popen[str] | None = None
_active_task_id: str | None = None
_process_lock = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _python_bin() -> str:
    return str(_repo_root() / ".venv" / "bin" / "python3")


def build_command(task_type: str, params: dict[str, Any]) -> tuple[str, list[str]]:
    python = _python_bin()
    match task_type:
        case "import-incremental":
            return python, [
                "-u",
                "scripts/import_to_tables.py",
                "--category",
                "F",
                "--category",
                "R",
                "--category",
                "V",
            ]
        case "import-reimport":
            return python, [
                "-u",
                "scripts/import_to_tables.py",
                "--reimport-all",
                "--category",
                "F",
                "--category",
                "R",
                "--category",
                "V",
            ]
        case "import-table":
            table = params.get("table") or "F"
            return python, ["-u", "scripts/import_to_tables.py", "--category", table]
        case "llm-format-full":
            return python, ["-u", "scripts/format_product_fields.py", "--write-db"]
        case "llm-format-reconcile":
            return python, [
                "-u",
                "scripts/format_product_fields.py",
                "--write-db",
                "--only-list-brand",
            ]
        case "pipeline":
            return "bash", ["scripts/run_server_pipeline.sh"]
        case _:
            raise ValueError(f"未支持的任务类型: {task_type}")


def read_log_tail(log_file: str | None, max_lines: int = 80) -> str | None:
    if not log_file:
        return None
    path = Path(log_file)
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines).strip()
    return "\n".join(lines[-max_lines:]).strip()


def _on_process_exit(task_id: str, returncode: int | None) -> None:
    global _active_process, _active_task_id
    with _process_lock:
        _active_process = None
        _active_task_id = None

    if returncode == 0:
        store.finalize_task(task_id, "completed", returncode, None)
    else:
        message = "进程异常退出" if returncode is None else f"退出码 {returncode}"
        store.finalize_task(task_id, "failed", returncode, message)
    drain_queue()


def _watch_process(task_id: str, process: subprocess.Popen[str]) -> None:
    returncode = process.wait()
    _on_process_exit(task_id, returncode)


def start_task(task: dict[str, Any]) -> None:
    global _active_process, _active_task_id
    repo_root = _repo_root()
    log_dir = store.tasks_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{task['id']}.log"
    command, args = build_command(task["type"], task.get("params") or {})

    with log_file.open("a", encoding="utf-8") as log_stream:
        log_stream.write(f"=== start {task['label']} ===\n")
        log_stream.write(f"command: {command} {' '.join(args)}\n\n")

    with log_file.open("ab") as log_stream:
        process = subprocess.Popen(
            [command, *args],
            cwd=repo_root,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )

    store.mark_running(task["id"], str(log_file))
    with _process_lock:
        _active_process = process
        _active_task_id = task["id"]

    threading.Thread(
        target=_watch_process,
        args=(task["id"], process),
        daemon=True,
        name=f"sjkx-task-{task['id'][:8]}",
    ).start()


def drain_queue() -> None:
    with _process_lock:
        if _active_process is not None and _active_process.poll() is None:
            return

    running_id = store.get_running_task_id()
    if running_id:
        running_task = store.get_task(running_id)
        if running_task and running_task.get("status") == "running" and _active_process is None:
            store.finalize_task(running_id, "failed", None, "代理重启导致任务中断")
        elif running_task and running_task.get("status") != "running":
            store.set_running_task_id(None)

    with _process_lock:
        if _active_process is not None and _active_process.poll() is None:
            return

    next_task = store.get_next_pending()
    if not next_task:
        return
    start_task(next_task)


def is_runner_available() -> tuple[bool, str | None]:
    repo_root = _repo_root()
    python = Path(_python_bin())
    import_script = repo_root / "scripts" / "import_to_tables.py"
    format_script = repo_root / "scripts" / "format_product_fields.py"
    if not import_script.exists() or not format_script.exists():
        return False, "未找到 Python 脚本"
    if not python.exists():
        return False, "未找到 .venv，请先安装 Python 依赖"
    return True, None
