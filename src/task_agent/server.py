from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.task_agent.definitions import TASK_DEFINITIONS
from src.task_agent import runner, store

VALID_TYPES = {item["type"] for item in TASK_DEFINITIONS}
VALID_TABLES = {"F", "R", "V"}


def _expected_secret() -> str | None:
    value = os.environ.get("SJKX_TASK_AGENT_SECRET", "").strip()
    return value or None


def _snapshot_response() -> dict[str, Any]:
    available, message = runner.is_runner_available()
    snapshot = store.list_snapshot()
    running = snapshot.get("running")
    return {
        **snapshot,
        "availableTypes": TASK_DEFINITIONS,
        "runnerAvailable": available,
        "runnerMessage": message,
        "runningLogTail": runner.read_log_tail(running.get("logFile") if running else None),
    }


class TaskAgentHandler(BaseHTTPRequestHandler):
    server_version = "sjkx-task-agent/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    def _authorized(self) -> bool:
        secret = _expected_secret()
        if not secret:
            return True
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {secret}":
            return True
        return auth == secret

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    def _reject_unauthorized(self) -> None:
        self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "未授权"})

    def do_GET(self) -> None:
        if not self._authorized():
            self._reject_unauthorized()
            return
        parsed = urlparse(self.path)
        if parsed.path != "/api/ai-tasks":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "未找到"})
            return
        runner.drain_queue()
        self._send_json(HTTPStatus.OK, _snapshot_response())

    def do_POST(self) -> None:
        if not self._authorized():
            self._reject_unauthorized()
            return
        parsed = urlparse(self.path)
        if parsed.path != "/api/ai-tasks":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "未找到"})
            return

        available, message = runner.is_runner_available()
        if not available:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": message or "无法执行任务"})
            return

        try:
            payload = self._read_json_body()
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        task_type = payload.get("type")
        if task_type not in VALID_TYPES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "无效的任务类型"})
            return

        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        table = params.get("table")
        if table is not None and table not in VALID_TABLES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "table 必须是 F / R / V"})
            return

        try:
            task = store.create_task(task_type, params)
            runner.drain_queue()
            self._send_json(HTTPStatus.CREATED, {"task": task})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_DELETE(self) -> None:
        if not self._authorized():
            self._reject_unauthorized()
            return
        parsed = urlparse(self.path)
        if parsed.path != "/api/ai-tasks":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "未找到"})
            return

        task_id = parse_qs(parsed.query).get("id", [None])[0]
        if not task_id:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "缺少任务 id"})
            return

        cancelled = store.cancel_pending(task_id)
        if not cancelled:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "任务不存在或无法取消"})
            return
        self._send_json(HTTPStatus.OK, {"task": cancelled})


def main() -> int:
    load_config()
    host = os.environ.get("SJKX_TASK_AGENT_HOST", "127.0.0.1")
    port = int(os.environ.get("SJKX_TASK_AGENT_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), TaskAgentHandler)
    print(f"sjkx task agent listening on http://{host}:{port}/api/ai-tasks", flush=True)
    if not _expected_secret():
        print("warning: SJKX_TASK_AGENT_SECRET 未设置，任何请求均可触发任务", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
