from __future__ import annotations

import hashlib
import mimetypes
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import env_int
from src.r2_storage import R2Storage

_URL_RE = re.compile(r"https?://[^\s,;|\]\"'>]+", re.IGNORECASE)
_FEISHU_HOST_MARKERS = ("feishu.cn", "larksuite.com", "feishu.com")
_MAX_IMAGES_PER_FIELD = 20
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_session: requests.Session | None = None


@dataclass
class MirrorStats:
    ok: int = 0
    failed: int = 0
    skipped_cached: int = 0

    def add(self, other: MirrorStats) -> None:
        self.ok += other.ok
        self.failed += other.failed
        self.skipped_cached += other.skipped_cached


def _http_session() -> requests.Session:
    global _session
    if _session is not None:
        return _session
    workers = env_int("IMAGE_MIRROR_WORKERS", 8)
    pool = max(workers * 2, 8)
    retries = Retry(
        total=env_int("IMAGE_MIRROR_HTTP_RETRIES", 3),
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update({"User-Agent": _DEFAULT_UA, "Accept": "image/*,*/*;q=0.8"})
    adapter = HTTPAdapter(max_retries=retries, pool_connections=pool, pool_maxsize=pool)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    _session = session
    return session


def extract_urls(text: str) -> list[str]:
    """从单元格文本中提取 HTTP(S) URL（去重、保序）。"""
    seen: set[str] = set()
    out: list[str] = []
    for match in _URL_RE.finditer(text.strip()):
        url = match.group(0).rstrip(".,);]")
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _needs_feishu_auth(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(marker in host for marker in _FEISHU_HOST_MARKERS)


def _guess_extension(url: str, content_type: str | None) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if ext:
            return ext if ext != ".jpe" else ".jpg"
    path = urlparse(url).path
    if "." in path:
        suffix = path.rsplit(".", 1)[-1].lower()
        if suffix in {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"}:
            return "." + ("jpg" if suffix == "jpeg" else suffix)
    return ".jpg"


def _global_object_key(prefix: str, source_url: str, ext: str) -> str:
    """同一源 URL 全局共用一个 R2 对象，避免按商品重复下载。"""
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}/by-source/{digest}{ext}"


def download_image(url: str, *, feishu_headers: dict[str, str] | None) -> tuple[bytes, str | None]:
    session = _http_session()
    timeout = env_int("IMAGE_MIRROR_DOWNLOAD_TIMEOUT", 90)
    attempts = env_int("IMAGE_MIRROR_DOWNLOAD_RETRIES", 5)
    headers: dict[str, str] = {}
    if feishu_headers and _needs_feishu_auth(url):
        headers.update(feishu_headers)

    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = session.get(url, headers=headers, timeout=timeout, stream=True)
            resp.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_IMAGE_BYTES:
                    raise ValueError(f"image exceeds {_MAX_IMAGE_BYTES} bytes: {url}")
                chunks.append(chunk)
            content_type = resp.headers.get("Content-Type")
            return b"".join(chunks), content_type
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt + 1 < attempts:
                time.sleep(min(2**attempt, 8))
    assert last_exc is not None
    raise last_exc


class ImageMirrorCache:
    """按源 URL 去重：每张图最多下载/上传一次，多行共用。"""

    def __init__(
        self,
        storage: R2Storage,
        *,
        key_prefix: str,
        feishu_headers: dict[str, str] | None,
    ) -> None:
        self._storage = storage
        self._key_prefix = key_prefix
        self._feishu_headers = feishu_headers
        self._map: dict[str, str] = {}
        self._failed: set[str] = set()
        self.stats = MirrorStats()

    def resolve(self, url: str) -> str:
        if url in self._map:
            self.stats.skipped_cached += 1
            return self._map[url]
        if url in self._failed:
            return url
        try:
            r2_url = self._mirror_once(url)
            self._map[url] = r2_url
            self.stats.ok += 1
            return r2_url
        except Exception:
            self._failed.add(url)
            self.stats.failed += 1
            return url

    def _mirror_once(self, url: str) -> str:
        ext = _guess_extension(url, None)
        key = _global_object_key(self._key_prefix, url, ext)
        if self._storage.exists(key):
            return self._storage.public_url(key)
        body, content_type = download_image(url, feishu_headers=self._feishu_headers)
        ext = _guess_extension(url, content_type)
        key = _global_object_key(self._key_prefix, url, ext)
        if self._storage.exists(key):
            return self._storage.public_url(key)
        self._storage.upload(key, body, content_type)
        return self._storage.public_url(key)

    def replace_in_text(self, text: str | None) -> str | None:
        if not text or not str(text).strip():
            return text
        raw = str(text)
        urls = extract_urls(raw)
        if not urls:
            return text
        out = raw
        for url in urls[:_MAX_IMAGES_PER_FIELD]:
            out = out.replace(url, self.resolve(url))
        return out


def _collect_record_urls(record: dict[str, Any], table_kind: str) -> list[str]:
    urls: list[str] = []
    if table_kind in {"F", "R"}:
        for field in ("image_path", "image_urls"):
            if record.get(field):
                urls.extend(extract_urls(str(record[field])))
    elif table_kind == "V" and record.get("image"):
        urls.extend(extract_urls(str(record["image"])))
    return urls


def mirror_records_batch(
    records: list[dict[str, Any]],
    *,
    table_kind: str,
    storage: R2Storage,
    key_prefix: str,
    feishu_headers: dict[str, str] | None,
) -> MirrorStats:
    """先并行镜像去重后的 URL，再写回各行字段。"""
    cache = ImageMirrorCache(storage, key_prefix=key_prefix, feishu_headers=feishu_headers)
    unique: list[str] = []
    seen: set[str] = set()
    for record in records:
        for url in _collect_record_urls(record, table_kind):
            if url not in seen:
                seen.add(url)
                unique.append(url)

    workers = env_int("IMAGE_MIRROR_WORKERS", 8)
    print(f"    去重后 {len(unique)} 个图片 URL（共 {len(records)} 行），并行度 {workers}", flush=True)

    if unique:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(cache.resolve, url): url for url in unique}
            done = 0
            for fut in as_completed(futures):
                fut.result()
                done += 1
                if done % 100 == 0 or done == len(unique):
                    print(
                        f"      镜像进度 {done}/{len(unique)} "
                        f"(成功 {cache.stats.ok}, 失败 {cache.stats.failed})",
                        flush=True,
                    )

    for record in records:
        if table_kind in {"F", "R"}:
            if record.get("image_path"):
                record["image_path"] = cache.replace_in_text(record.get("image_path"))
            if record.get("image_urls"):
                record["image_urls"] = cache.replace_in_text(record.get("image_urls"))
        elif table_kind == "V" and record.get("image"):
            record["image"] = cache.replace_in_text(record.get("image"))

    return cache.stats


def mirror_record_images(
    record: dict[str, Any],
    *,
    table_kind: str,
    storage: R2Storage,
    key_prefix: str,
    feishu_headers: dict[str, str] | None,
) -> MirrorStats:
    """单行镜像（保留供测试）；大批量请用 mirror_records_batch。"""
    cache = ImageMirrorCache(storage, key_prefix=key_prefix, feishu_headers=feishu_headers)
    if table_kind in {"F", "R"}:
        if record.get("image_path"):
            record["image_path"] = cache.replace_in_text(record.get("image_path"))
        if record.get("image_urls"):
            record["image_urls"] = cache.replace_in_text(record.get("image_urls"))
    elif table_kind == "V" and record.get("image"):
        record["image"] = cache.replace_in_text(record.get("image"))
    return cache.stats
