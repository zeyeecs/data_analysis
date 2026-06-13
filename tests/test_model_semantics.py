from __future__ import annotations

from src.model_semantics import (
    SemanticParseResult,
    TokenClassification,
    _assemble_model_from_tokens,
    _is_local_llm_base,
    _llm_api_key_for_base,
    _resolve_llm_settings,
    reset_semantic_parse_cache_stats,
    semantic_parse_model,
)


def test_local_llm_detection() -> None:
    assert _is_local_llm_base("http://127.0.0.1:11434/v1")
    assert _is_local_llm_base("http://localhost:1234/v1")
    assert not _is_local_llm_base("https://api.deepseek.com/v1")


def test_local_llm_api_key_fallback(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert _llm_api_key_for_base("http://127.0.0.1:11434/v1") == "ollama"


def test_deepseek_settings_precedence(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    cfg = _resolve_llm_settings()
    assert cfg["provider"] == "deepseek"
    assert cfg["base_url"] == "https://api.deepseek.com/v1"
    assert cfg["model"] == "deepseek-chat"
    assert cfg["local"] is False
    assert cfg["json_mode"] is True


def test_assemble_model_from_tokens_birkin() -> None:
    tokens = [
        TokenClassification("Hermes", "brand"),
        TokenClassification("Taurillon", "material"),
        TokenClassification("Birkin", "model"),
        TokenClassification("with", "connector"),
        TokenClassification("Hardware", "hardware"),
        TokenClassification("35", "size"),
    ]
    assert _assemble_model_from_tokens(tokens) == "Birkin 35"


def test_from_llm_payload_uses_top_level_fields() -> None:
    result = SemanticParseResult.from_llm_payload(
        {
            "tokens": [
                {"text": "Birkin", "role": "model"},
                {"text": "35", "role": "size"},
            ],
            "material": "Taurillon",
            "model": "Birkin 35",
            "color": None,
            "other": None,
        }
    )
    assert result.material == "Taurillon"
    assert result.model == "Birkin 35"
    assert result.color is None
    assert result.other is None


def test_from_llm_payload_assembles_other_from_modifier_tokens() -> None:
    result = SemanticParseResult.from_llm_payload(
        {
            "tokens": [
                {"text": "Kelly", "role": "model"},
                {"text": "Sellier", "role": "modifier"},
                {"text": "28", "role": "size"},
            ],
            "material": None,
            "model": "kelly 28",
            "color": None,
            "other": None,
        }
    )
    assert result.model == "kelly 28"
    assert result.other == "Sellier"


def test_from_llm_payload_assembles_when_model_missing() -> None:
    result = SemanticParseResult.from_llm_payload(
        {
            "tokens": [
                {"text": "Graceful", "role": "model"},
                {"text": "MM", "role": "size"},
                {"text": "Pivoine", "role": "color"},
            ],
            "material": None,
            "model": None,
            "color": None,
        }
    )
    assert result.model == "Graceful MM"
    assert result.color == "Pivoine"


def test_text_cache_reuses_parse_for_same_brand_title(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SEMANTIC_PARSE_CACHE_PATH", str(tmp_path / "cache.db"))
    reset_semantic_parse_cache_stats()

    calls: list[tuple[str | None, str | None, str | None]] = []

    def fake_llm(*, brand, text, color, condition):
        calls.append((brand, text, color))
        return {
            "tokens": [{"text": "Birkin", "role": "model"}, {"text": "35", "role": "size"}],
            "material": "taurillon",
            "model": "birkin 35",
            "color": "noir",
        }

    monkeypatch.setattr("src.model_semantics._call_llm", fake_llm)

    first = semantic_parse_model(
        "Birkin 35 Taurillon",
        brand="Hermes",
        color=None,
        condition=None,
    )
    second = semantic_parse_model(
        "Birkin 35 Taurillon",
        brand="Hermes",
        color="black",
        condition="A",
    )

    assert first is not None and first.model == "birkin 35"
    assert second is not None and second.model == "birkin 35"
    assert len(calls) == 1
