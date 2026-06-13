#!/usr/bin/env python3
"""演示 LLM 逐词语义解析（需 .env 中配置 OPENAI_* 或本地 Ollama）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.model_semantics import diagnose_llm, llm_runtime_config, semantic_parse_model, verify_llm_auth


def _print_config() -> None:
    cfg = llm_runtime_config()
    print("当前 LLM 配置:", flush=True)
    for key in (
        "use_llm",
        "provider",
        "base_url",
        "model",
        "api_key_status",
        "local",
        "json_mode",
        "timeout_sec",
    ):
        print(f"  {key}: {cfg[key]}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("title", help="原始型号/标题")
    parser.add_argument("--brand", default="Hermes")
    parser.add_argument("--color")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--check", action="store_true", help="仅检查 LLM 配置与连通性")
    args = parser.parse_args()

    load_config()
    _print_config()

    for line in diagnose_llm():
        print(f"诊断: {line}", flush=True)

    if args.check:
        ok, _ = verify_llm_auth()
        if not ok:
            return 1
        notes = diagnose_llm()
        return 0 if not notes else 1

    errors: list[str] = []
    result = semantic_parse_model(
        args.title,
        brand=args.brand,
        color=args.color,
        use_cache=not args.no_cache,
        error_out=errors,
    )
    if result is None:
        print("\n解析失败。", file=sys.stderr)
        if errors:
            print(f"错误: {errors[0]}", file=sys.stderr)
        print("\n排查步骤:", file=sys.stderr)
        cfg = llm_runtime_config()
        if cfg.get("provider") == "deepseek":
            print("  1. 在 .env 填入有效的 DEEPSEEK_API_KEY（https://platform.deepseek.com/api_keys）", file=sys.stderr)
            print("  2. 运行: python3 scripts/semantic_parse_demo.py --check", file=sys.stderr)
        else:
            print("  1. 检查 .env 中 OPENAI_* / DEEPSEEK_* 配置", file=sys.stderr)
            print("  2. 运行: python3 scripts/semantic_parse_demo.py --check", file=sys.stderr)
        return 1

    print("tokens:")
    for token in result.tokens:
        print(f"  {token.text}\t{token.role}")
    print(f"material: {result.material}")
    print(f"model: {result.model}")
    print(f"color: {result.color}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
