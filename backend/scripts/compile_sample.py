"""Compile a sample resume with the real DeepSeek provider.

Run from backend/ with DEEPSEEK_API_KEY set (or backend/.env):
    python scripts/compile_sample.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.llm.client import DeepSeekClient, LLMError  # noqa: E402
from app.services.cards import compile_cards  # noqa: E402
from app.services.compiler import SourceBlock, SourceDoc, compile_document  # noqa: E402
from app.services.parsing import parse_document  # noqa: E402


def main() -> int:
    settings = Settings()
    if not settings.deepseek_api_key:
        print("DEEPSEEK_API_KEY is not set")
        return 2

    sample = Path(__file__).with_name("sample_resume.txt")
    parsed = parse_document(sample, sample.name)
    doc = SourceDoc(
        id="doc-sample",
        source_id="source:doc-sample",
        filename=sample.name,
        doc_type="resume",
        created_at=datetime.now(timezone.utc),
    )
    blocks = [
        SourceBlock(block_id=f"b-{index:04d}", page=block.page, text=block.text)
        for index, block in enumerate(parsed.blocks, start=1)
    ]
    llm = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    try:
        result = compile_document(llm, settings, "usr-smoke", doc, blocks)
    except LLMError as exc:
        print("LLM error:", exc)
        return 1

    print("run_id", result.run_id)
    print("model", result.model)
    print("tokens", result.prompt_tokens, result.completion_tokens)
    print("latency_ms", result.latency_ms)
    print("pages", len(result.pages))
    for page in result.pages:
        print("-", page.id, page.confidence, page.evidence_count, page.path)
    for warning in result.warnings:
        print("WARN", warning)

    try:
        cards = compile_cards(llm, settings, "usr-smoke", doc, result.run_id)
    except LLMError as exc:
        print("CARD ERROR", exc)
        return 1
    print("cards", len(cards.cards))
    for card in cards.cards:
        print("*", card.id, card.evidence_count, card.path)
    for warning in cards.warnings:
        print("CARD WARN", warning)
    print("pack", cards.pack_path)
    return 0 if result.pages and cards.cards else 1


if __name__ == "__main__":
    raise SystemExit(main())
