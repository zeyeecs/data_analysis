from __future__ import annotations

import threading
import time
from typing import Any, Iterator

import requests

from src.config import env

_RETRYABLE = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
)
_MAX_RETRIES = 5


class FeishuClient:
    _token_lock = threading.Lock()
    _shared_token: str | None = None
    _shared_token_expire_at = 0.0

    def __init__(self) -> None:
        self.base = env("FEISHU_API_BASE").rstrip("/")

    @classmethod
    def _request(cls, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = requests.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt + 1 >= _MAX_RETRIES:
                    break
                wait = min(2**attempt, 30)
                time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    def _ensure_token(self) -> str:
        now = time.time()
        if FeishuClient._shared_token and now < FeishuClient._shared_token_expire_at - 60:
            return FeishuClient._shared_token

        with FeishuClient._token_lock:
            now = time.time()
            if FeishuClient._shared_token and now < FeishuClient._shared_token_expire_at - 60:
                return FeishuClient._shared_token

            resp = self._request(
                "POST",
                f"{self.base}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": env("FEISHU_APP_ID"),
                    "app_secret": env("FEISHU_APP_SECRET"),
                },
                timeout=60,
            )
            payload = resp.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"Feishu auth failed: {payload}")

            FeishuClient._shared_token = payload["tenant_access_token"]
            FeishuClient._shared_token_expire_at = time.time() + int(payload.get("expire", 7200))
            return FeishuClient._shared_token

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._ensure_token()}"}

    def list_files(self, folder_token: str) -> Iterator[dict[str, Any]]:
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "folder_token": folder_token,
                "page_size": 200,
            }
            if page_token:
                params["page_token"] = page_token

            resp = self._request(
                "GET",
                f"{self.base}/drive/v1/files",
                headers=self.headers,
                params=params,
                timeout=120,
            )
            payload = resp.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"List files failed: {payload}")

            data = payload["data"]
            for item in data.get("files", []):
                if item.get("type") == "file":
                    yield item

            if not data.get("has_more"):
                break
            page_token = data.get("next_page_token")

    def download_file(
        self, file_token: str, max_bytes: int | None = 100 * 1024 * 1024
    ) -> tuple[bytes | None, int | None]:
        """Download file bytes. Returns (content, size_bytes).

        If max_bytes is set and Content-Length exceeds it, skips download.
        If stream exceeds max_bytes, aborts and returns (None, partial_size).
        """
        resp = self._request(
            "GET",
            f"{self.base}/drive/v1/files/{file_token}/download",
            headers=self.headers,
            timeout=600,
            stream=True,
        )

        content_length = resp.headers.get("Content-Length")
        if max_bytes is not None and content_length:
            size_hint = int(content_length)
            if size_hint > max_bytes:
                resp.close()
                return None, size_hint

        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                resp.close()
                return None, total
            chunks.append(chunk)
        return b"".join(chunks), total
