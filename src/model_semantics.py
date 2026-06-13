"""用 LLM 对商品标题/型号做逐词语义分类（品牌、材质、款式、尺码、颜色等）。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.config import ROOT, env_bool, env_int


def _optional_env(name: str, default: str) -> str:
    import os

    value = os.environ.get(name)
    return value if value else default


_CACHE_PATH = ROOT / "data" / "semantic_parse_cache.db"

_TOKEN_ROLES = frozenset(
    {
        "brand",
        "material",
        "model",
        "size",
        "color",
        "hardware",
        "modifier",
        "bag_type",
        "condition",
        "connector",
        "other",
    }
)

_PROMPT_VERSION = "model-canonical-v2"

_SYSTEM_PROMPT = """你是二奢商品字段清洗专家。目标：输出稳定、可聚合的 canonical model（对应入库列 model / product_name）。

## 第一优先级：model 纯洁且一致

model = **完整官方款式名（含多词系列名）+ 尺码**。同一款式在所有商品上必须输出**完全相同**的 model 字符串。

### model 必须包含（不可拆短）
- 多词系列名整体保留：gg marmont、speedy bandouliere、rockstud spike、cc top handle、bamboo daily top handle、le click east west、le chiquito noeud、tassel oval、falabella box、re-edition 2005、herbag zip、puzzle fold、wallet on chain double c、elsa sellier
- 尺码/规格：25、35、bb、pm、mm、mini 等留在 model 尾部

### model 必须剔除（不得出现）
- brand（品牌名）
- material（材质/皮料：leather、taurillon、monogram、canvas、velvet…）
- color（颜色词，除非 color 列已单独给出且标题重复出现）
- bag_type（crossbody bag、handbag、shoulder bag、clutch、watch…）
- hardware（hardware、palladium hardware…）
- 连接词/噪声（with、and、in）

### 禁止行为
- 禁止把系列名的一部分挪到 other/material：gg、rockstud、bandouliere、top handle、east west、noeud、tassel、re-edition 等是 **model 组成部分**
- 禁止同一款式在不同行输出不同写法（如一行 marmont、一行 gg marmont）
- 只有爱马仕等少数 **工艺变体**（sellier、retourne、touch、cargo picotin、faubourg）及 **特别版**（so black）可进 other；Lancel「Elsa Sellier」中 Sellier 仍是 model 一部分
- cargo 仅 Hermès **Cargo Picotin** 系列；Moncler/Rick Owens 等「cargo 夹克/鞋」中 cargo 是 model 一部分
- shadow、monogram shadow 等材质/系列名不是 other

## 第二优先级：material / color

- material：皮料/面料；V 表「款式 材质 包型」→ material 只含材质词
- color：专有色名；无则 null

## other（次要，可 null）

- Hermès 工艺/结构：sellier、retourne、touch（任意 Hermès 款式线）、cargo（仅 Cargo Picotin）、faubourg（Kelly/Roulis/Videpoches 等 Barenia Faubourg 版；Faubourg 鞋/表款名不算）
- 跨品牌特别版：so black（全黑五金/特别版，如 Chanel So Black Boy Flap）
- 其余一律 null；禁止 shadow

## 输出格式

- 小写 ASCII 英文；法文/重音译英文（cuir→leather、noir→black、hermès→hermes）
- 只输出 JSON，无 markdown

## 示例（canonical model）

brand=Hermes | Hermes Birkin Colvert with Hardware 35
→ model="birkin 35", material=null, color="colvert", other=null

brand=Hermes | Hermes Kelly Sellier 28 Togo
→ model="kelly 28", material="togo", color=null, other="sellier"

brand=Hermes | Touch Lindy Bag Swift Mini
→ model="lindy mini", material="swift", color=null, other="touch"

brand=Hermes | Cargo Picotin Lock Bag Canvas PM
→ model="picotin lock pm", material="canvas", color=null, other="cargo"

brand=Hermes | Kelly Handbag Barenia Faubourg 28
→ model="kelly 28", material="barenia", color=null, other="faubourg"

brand=Chanel | So Black Boy Flap Bag Caviar Medium
→ model="boy flap medium", material="caviar", color=null, other="so black"

brand=Gucci | GG Marmont leather handbag
→ model="gg marmont", material="leather", color=null, other=null

brand=Louis Vuitton | Speedy Bandouliere 25
→ model="speedy bandouliere 25", material=null, color=null, other=null

brand=Valentino Garavani | Rockstud Spike leather crossbody bag
→ model="rockstud spike", material="leather", color=null, other=null

brand=Chanel | CC Top Handle leather handbag
→ model="cc top handle", material="leather", color=null, other=null

brand=Gucci | Bamboo Daily Top Handle leather bag
→ model="bamboo daily top handle", material="leather", color=null, other=null

brand=Alaia | Le Click East West leather bag
→ model="le click east west", material="leather", color=null, other=null

brand=Jacquemus | Le Chiquito Noeud leather bag
→ model="le chiquito noeud", material="leather", color=null, other=null

brand=Prada | Re-Edition 2005 nylon bag
→ model="re-edition 2005", material="nylon", color=null, other=null

brand=Hermes | Herbag Zip leather bag
→ model="herbag zip", material="leather", color=null, other=null

brand=Loewe | Puzzle Fold leather bag
→ model="puzzle fold", material="leather", color=null, other=null

brand=Lancel | Elsa Sellier leather handbag
→ model="elsa sellier", material="leather", color=null, other=null

brand=Marni | Trunk leather crossbody bag
→ model="trunk", material="leather", color=null, other=null

JSON schema:
{
  "tokens": [{"text": "词", "role": "brand|material|model|size|color|hardware|modifier|bag_type|condition|connector|other"}],
  "material": "字符串或 null",
  "model": "字符串或 null",
  "color": "字符串或 null",
  "other": "字符串或 null"
}
"""


@dataclass(frozen=True)
class TokenClassification:
    text: str
    role: str


@dataclass
class SemanticParseResult:
    tokens: tuple[TokenClassification, ...]
    material: str | None
    model: str | None
    color: str | None
    other: str | None = None

    @classmethod
    def from_llm_payload(cls, payload: dict[str, Any]) -> SemanticParseResult:
        tokens: list[TokenClassification] = []
        for item in payload.get("tokens") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            role = str(item.get("role") or "other").strip().lower()
            if not text:
                continue
            if role not in _TOKEN_ROLES:
                role = "other"
            tokens.append(TokenClassification(text=text, role=role))

        material = _clean_field(payload.get("material"))
        model = _clean_field(payload.get("model"))
        color = _clean_field(payload.get("color"))
        other = _clean_field(payload.get("other"))

        if not model:
            model = _assemble_model_from_tokens(tokens)
        if not material:
            material = _assemble_material_from_tokens(tokens)
        if not color:
            color = _assemble_color_from_tokens(tokens)
        if not other:
            other = _assemble_other_from_tokens(tokens)

        return cls(tokens=tuple(tokens), material=material, model=model, color=color, other=other)


def use_llm_semantics() -> bool:
    return env_bool("PRODUCT_FORMAT_USE_LLM", False)


def _clean_field(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    return re.sub(r"\s+", " ", text)


def _assemble_material_from_tokens(tokens: list[TokenClassification]) -> str | None:
    parts = [t.text for t in tokens if t.role == "material"]
    return " ".join(parts).strip() or None


def _assemble_color_from_tokens(tokens: list[TokenClassification]) -> str | None:
    parts = [t.text for t in tokens if t.role == "color"]
    return " ".join(parts).strip() or None


def _assemble_other_from_tokens(tokens: list[TokenClassification]) -> str | None:
    parts = [t.text for t in tokens if t.role == "modifier"]
    return " ".join(parts).strip() or None


def _assemble_model_from_tokens(tokens: list[TokenClassification]) -> str | None:
    """从 token 序列拼飞书型号：款式词 + 尾部尺码。"""
    model_parts: list[str] = []
    size_parts: list[str] = []
    for token in tokens:
        if token.role == "model":
            model_parts.append(token.text)
        elif token.role == "size":
            size_parts.append(token.text)
    series = " ".join(model_parts).strip() or None
    size = " ".join(size_parts).strip() or None
    if series and size:
        return f"{series} {size}"
    return series or size


def _cache_key(brand: str | None, text: str, color: str | None, condition: str | None) -> str:
    raw = "|".join(
        [
            _PROMPT_VERSION,
            (brand or "").strip().lower(),
            text.strip().lower(),
            (color or "").strip().lower(),
            (condition or "").strip().lower(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _text_cache_dims(brand: str | None, text: str) -> tuple[str, str]:
    versioned_brand = f"{_PROMPT_VERSION}|{(brand or '').strip().lower()}"
    return versioned_brand, text.strip().lower()


_memory_cache: dict[str, dict[str, Any]] = {}
_memory_text_cache: dict[tuple[str, str], dict[str, Any]] = {}
_sqlite_conn: sqlite3.Connection | None = None
_cache_stats: dict[str, int] = {
    "memory_hit": 0,
    "text_hit": 0,
    "sqlite_hit": 0,
    "text_sqlite_hit": 0,
    "llm_call": 0,
}


def semantic_parse_cache_stats() -> dict[str, int]:
    """本次进程内语义解析缓存命中统计（供批处理脚本观测提速效果）。"""
    return dict(_cache_stats)


def reset_semantic_parse_cache_stats() -> None:
    for key in _cache_stats:
        _cache_stats[key] = 0


def _cache_db_path() -> Path:
    return Path(_optional_env("SEMANTIC_PARSE_CACHE_PATH", str(_CACHE_PATH)))


def _ensure_cache_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_parse_cache (
                cache_key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_parse_text_cache (
                brand TEXT NOT NULL,
                title TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (brand, title)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _sqlite_connection() -> sqlite3.Connection | None:
    global _sqlite_conn
    path = _cache_db_path()
    if not path.is_file():
        return None
    if _sqlite_conn is None:
        _ensure_cache_db(path)
        _sqlite_conn = sqlite3.connect(path)
    return _sqlite_conn


def _load_cached_payload(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _remember_payload(
    *,
    key: str,
    brand: str | None,
    text: str,
    payload: dict[str, Any],
    persist: bool,
) -> None:
    _memory_cache[key] = payload
    _memory_text_cache[_text_cache_dims(brand, text)] = payload
    if not persist:
        return
    encoded = json.dumps(payload, ensure_ascii=False)
    now = time.time()
    conn = _sqlite_connection()
    if conn is None:
        _ensure_cache_db(_cache_db_path())
        conn = _sqlite_connection()
    if conn is None:
        return
    brand_key, title_key = _text_cache_dims(brand, text)
    conn.execute(
        """
        INSERT OR REPLACE INTO semantic_parse_cache (cache_key, response_json, created_at)
        VALUES (?, ?, ?)
        """,
        (key, encoded, now),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO semantic_parse_text_cache (brand, title, response_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (brand_key, title_key, encoded, now),
    )
    conn.commit()


def _cache_get(key: str) -> dict[str, Any] | None:
    cached = _memory_cache.get(key)
    if cached is not None:
        _cache_stats["memory_hit"] += 1
        return cached

    conn = _sqlite_connection()
    if conn is None:
        return None
    row = conn.execute(
        "SELECT response_json FROM semantic_parse_cache WHERE cache_key = ?",
        (key,),
    ).fetchone()
    if not row:
        return None
    payload = _load_cached_payload(row[0])
    if payload is None:
        return None
    _memory_cache[key] = payload
    _cache_stats["sqlite_hit"] += 1
    return payload


def _text_cache_get(brand: str | None, text: str) -> dict[str, Any] | None:
    dims = _text_cache_dims(brand, text)
    cached = _memory_text_cache.get(dims)
    if cached is not None:
        _cache_stats["text_hit"] += 1
        return cached

    conn = _sqlite_connection()
    if conn is None:
        return None
    row = conn.execute(
        """
        SELECT response_json FROM semantic_parse_text_cache
        WHERE brand = ? AND title = ?
        """,
        dims,
    ).fetchone()
    if not row:
        return None
    payload = _load_cached_payload(row[0])
    if payload is None:
        return None
    _memory_text_cache[dims] = payload
    _cache_stats["text_sqlite_hit"] += 1
    return payload


def _cache_set(key: str, brand: str | None, text: str, payload: dict[str, Any]) -> None:
    _remember_payload(key=key, brand=brand, text=text, payload=payload, persist=True)


def _get_env(name: str, default: str | None = None) -> str | None:
    import os

    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip()


def _looks_like_placeholder_api_key(key: str) -> bool:
    lowered = key.lower().strip()
    if not lowered.startswith("sk-"):
        return True
    if len(lowered) < 20:
        return True
    # 常见示例/占位 key
    if "123456789" in lowered or lowered.endswith("example"):
        return True
    return False


def _api_key_fingerprint(key: str) -> str:
    text = key.strip()
    if len(text) <= 8:
        return "***"
    return f"{text[:7]}...{text[-4:]}"


def verify_llm_auth() -> tuple[bool, list[str]]:
    """探测 LLM 鉴权是否可用（云端/本地均发最小 chat）。"""
    notes: list[str] = []
    try:
        cfg = _resolve_llm_settings()
    except RuntimeError as exc:
        return False, [str(exc)]

    base = str(cfg["base_url"])
    model = str(cfg["model"])
    api_key = str(cfg["api_key"])

    if _looks_like_placeholder_api_key(api_key):
        notes.append(
            f"DEEPSEEK_API_KEY 疑似占位符（{_api_key_fingerprint(api_key)}），"
            "请在 https://platform.deepseek.com/api_keys 创建真实密钥并写入 .env"
        )
        return False, notes

    try:
        probe = requests.post(
            f"{base.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ok"}],
                "temperature": 0,
            },
            timeout=min(int(cfg["timeout_sec"]), 30),
        )
        if probe.status_code == 401:
            notes.append(
                "DeepSeek 返回 401：API Key 无效或已失效。"
                "请检查 .env 中 DEEPSEEK_API_KEY 是否为 platform.deepseek.com 签发的 sk- 密钥"
            )
            return False, notes
        if probe.status_code >= 400:
            notes.append(f"LLM 探测失败 HTTP {probe.status_code}: {probe.text[:200]}")
            return False, notes
        return True, notes
    except requests.RequestException as exc:
        notes.append(f"无法连接 LLM: {exc}")
        return False, notes


def _is_local_llm_base(base_url: str) -> bool:
    lowered = base_url.lower()
    return any(
        host in lowered
        for host in (
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "[::1]",
            "host.docker.internal",
        )
    )


def _resolve_llm_settings() -> dict[str, str | bool | int]:
    """优先 DeepSeek（DEEPSEEK_*），否则 OPENAI_*（含本地 Ollama）。"""
    deepseek_key = _get_env("DEEPSEEK_API_KEY")
    deepseek_base = _get_env("DEEPSEEK_BASE_URL")
    use_deepseek = bool(deepseek_key or deepseek_base)

    if use_deepseek:
        base_url = (deepseek_base or "https://api.deepseek.com/v1").rstrip("/")
        model = _get_env("DEEPSEEK_MODEL") or _get_env("OPENAI_MODEL") or "deepseek-chat"
        api_key = deepseek_key or _get_env("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("未设置 DEEPSEEK_API_KEY（或 OPENAI_API_KEY）")
        provider = "deepseek"
    else:
        base_url = (_get_env("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").rstrip("/")
        model = _get_env("OPENAI_MODEL", "gpt-4o-mini") or ""
        api_key = _llm_api_key_for_base(base_url)
        provider = "openai"

    local = _is_local_llm_base(base_url)
    timeout = env_int(
        "OPENAI_TIMEOUT_SEC",
        env_int("DEEPSEEK_TIMEOUT_SEC", 120 if local else 60),
    )
    json_mode = env_bool(
        "OPENAI_JSON_MODE",
        env_bool("DEEPSEEK_JSON_MODE", not local),
    )
    return {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "local": local,
        "json_mode": json_mode,
        "timeout_sec": timeout,
    }


def _llm_api_key_for_base(base_url: str) -> str:
    """本地 OpenAI 兼容服务（Ollama 等）通常不需要真实 key。"""
    explicit = _get_env("OPENAI_API_KEY")
    if explicit:
        return explicit
    if _is_local_llm_base(base_url):
        return "ollama"
    raise RuntimeError("未设置 OPENAI_API_KEY（本地模型可填 ollama 或留空并指向 localhost）")


def _parse_json_payload(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("LLM 返回非 JSON 对象")
    return payload


def _post_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    user_content: str,
    timeout: int,
    json_mode: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return _parse_json_payload(content)


def _call_llm(
    *,
    brand: str | None,
    text: str,
    color: str | None,
    condition: str | None,
) -> dict[str, Any]:
    cfg = _resolve_llm_settings()
    base_url = str(cfg["base_url"])
    api_key = str(cfg["api_key"])
    model = str(cfg["model"])
    timeout = int(cfg["timeout_sec"])
    json_mode = bool(cfg["json_mode"])

    user_lines = [f"brand: {brand or '(空)'}", f"title: {text}"]
    if color:
        user_lines.append(f"color列: {color}")
    if condition:
        user_lines.append(f"condition列: {condition}")
    user_content = "\n".join(user_lines)

    try:
        return _post_chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=model,
            user_content=user_content,
            timeout=timeout,
            json_mode=json_mode,
        )
    except requests.HTTPError as exc:
        # 部分本地模型不支持 response_format=json_object，关闭后重试
        if json_mode and exc.response is not None and exc.response.status_code in {400, 422}:
            return _post_chat_completion(
                base_url=base_url,
                api_key=api_key,
                model=model,
                user_content=user_content,
                timeout=timeout,
                json_mode=False,
            )
        raise


def llm_runtime_config() -> dict[str, str | bool | int]:
    try:
        cfg = _resolve_llm_settings()
        api_key = str(cfg["api_key"])
        if not api_key:
            key_status = "missing"
        elif _looks_like_placeholder_api_key(api_key):
            key_status = "placeholder"
        else:
            key_status = "set"
    except RuntimeError:
        deepseek_mode = bool(
            _get_env("DEEPSEEK_API_KEY") or _get_env("DEEPSEEK_BASE_URL") or _get_env("DEEPSEEK_MODEL")
        )
        cfg = {
            "provider": "deepseek" if deepseek_mode else "unknown",
            "base_url": _get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1") or "",
            "model": _get_env("DEEPSEEK_MODEL", "deepseek-chat") or "",
            "api_key": "",
            "local": False,
            "json_mode": True,
            "timeout_sec": 60,
        }
        key_status = "missing"
    return {
        "provider": str(cfg.get("provider", "")),
        "base_url": str(cfg.get("base_url", "")),
        "model": str(cfg.get("model", "")),
        "api_key_status": key_status,
        "local": bool(cfg.get("local")),
        "json_mode": bool(cfg.get("json_mode")),
        "timeout_sec": int(cfg.get("timeout_sec", 60)),
        "use_llm": use_llm_semantics(),
    }


def diagnose_llm() -> list[str]:
    """返回人类可读诊断信息；空列表表示配置层面无明显问题。"""
    cfg = llm_runtime_config()
    notes: list[str] = []
    base = str(cfg["base_url"])

    if cfg["api_key_status"] in {"missing", "placeholder"}:
        if cfg.get("provider") == "deepseek":
            notes.append("未设置有效的 DEEPSEEK_API_KEY（https://platform.deepseek.com/api_keys）")
        else:
            notes.append("未设置 OPENAI_API_KEY（云端必填；本地可设 OPENAI_API_KEY=ollama）")
    elif not cfg["local"]:
        ok, auth_notes = verify_llm_auth()
        notes.extend(auth_notes)
        if not ok and not auth_notes:
            notes.append("LLM 鉴权探测失败")

    if not cfg["model"]:
        notes.append("未设置 OPENAI_MODEL")

    if cfg["local"]:
        notes.append(f"本地 LLM 端点: {base}")
        try:
            resp = requests.get(f"{base}/models", timeout=5)
            if resp.status_code >= 400:
                notes.append(f"无法连接本地服务 ({resp.status_code})，请先安装并启动 Ollama / LM Studio")
            else:
                models = resp.json().get("data") or []
                ids = [m.get("id", "") for m in models if isinstance(m, dict)]
                if cfg["model"] and ids and cfg["model"] not in ids:
                    preview = ", ".join(ids[:5])
                    notes.append(
                        f"模型 {cfg['model']!r} 不在本地列表中；可用: {preview}"
                        + (" ..." if len(ids) > 5 else "")
                    )
                # /models 正常不代表能推理；探测一次最小 chat
                if cfg["model"]:
                    probe = requests.post(
                        f"{base}/chat/completions",
                        headers={"Authorization": "Bearer ollama", "Content-Type": "application/json"},
                        json={
                            "model": cfg["model"],
                            "messages": [{"role": "user", "content": "ok"}],
                            "temperature": 0,
                        },
                        timeout=30,
                    )
                    if probe.status_code >= 400:
                        detail = probe.text[:300]
                        if "llama-server binary not found" in detail:
                            notes.append(
                                "Ollama 推理引擎缺失（brew formula 安装不完整）。"
                                "请改用: brew install --cask ollama-app，然后 open -a Ollama"
                            )
                        else:
                            notes.append(f"本地推理失败 HTTP {probe.status_code}: {detail}")
        except requests.RequestException as exc:
            notes.append(
                "本地 LLM 未响应。推荐: brew install --cask ollama-app && open -a Ollama && ollama pull qwen2.5:7b"
            )
            notes.append(f"详情: {exc}")
            notes.append("环境变量请写入 .env（见 .env.example），不要直接在终端粘贴 KEY=VALUE 行")

    return notes


def semantic_parse_model(
    text: str | None,
    *,
    brand: str | None = None,
    color: str | None = None,
    condition: str | None = None,
    use_cache: bool = True,
    error_out: list[str] | None = None,
) -> SemanticParseResult | None:
    """
    调用 LLM 对标题逐词分类。失败返回 None（由调用方回退规则引擎）。
    error_out: 若提供，写入失败原因（供 demo/调试）。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    key = _cache_key(brand, cleaned, color, condition)
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            _memory_text_cache[_text_cache_dims(brand, cleaned)] = cached
            return SemanticParseResult.from_llm_payload(cached)

        # 重复字段提速：同 brand+title 已解析过则沿用上次结果，不再调 LLM
        cached = _text_cache_get(brand, cleaned)
        if cached is not None:
            return SemanticParseResult.from_llm_payload(cached)

    try:
        payload = _call_llm(brand=brand, text=cleaned, color=color, condition=condition)
    except Exception as exc:
        if error_out is not None:
            error_out.append(str(exc))
        return None

    _cache_stats["llm_call"] += 1
    if use_cache:
        _cache_set(key, brand, cleaned, payload)
    return SemanticParseResult.from_llm_payload(payload)
