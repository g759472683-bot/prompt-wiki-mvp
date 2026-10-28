"""Compile 5 documents end-to-end (pages + cards) and write a baseline report.

Run from backend/ with DEEPSEEK_API_KEY set:
    python scripts/baseline.py
"""

from __future__ import annotations

import sys
import time
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
    docs_dir = Path(__file__).with_name("baseline_docs")
    files = sorted(docs_dir.glob("*.txt"))
    if not files:
        print("no docs in", docs_dir)
        return 2

    llm = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    rows = []
    for path in files:
        slug = path.stem.replace("_", "-")
        parsed = parse_document(path, path.name)
        doc = SourceDoc(
            id=f"doc-{slug}",
            source_id=f"source:doc-{slug}",
            filename=path.name,
            doc_type="resume" if slug.endswith("resume") else "notes",
            created_at=datetime.now(timezone.utc),
        )
        blocks = [
            SourceBlock(f"b-{index:04d}", block.page, block.text)
            for index, block in enumerate(parsed.blocks, start=1)
        ]
        started = time.perf_counter()
        try:
            pages = compile_document(
                llm, settings, "usr-baseline", doc, blocks
            )
            cards = compile_cards(
                llm, settings, "usr-baseline", doc, pages.run_id
            ) if pages.pages else None
        except LLMError as exc:
            rows.append(
                {
                    "doc": path.name,
                    "blocks": len(blocks),
                    "pages": 0,
                    "cards": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "latency": int((time.perf_counter() - started) * 1000),
                    "warnings": [f"FAILED: {exc}"],
                }
            )
            print(path.name, "FAILED", exc)
            continue

        latency = int((time.perf_counter() - started) * 1000)
        warnings = list(pages.warnings) + (cards.warnings if cards else [])
        rows.append(
            {
                "doc": path.name,
                "blocks": len(blocks),
                "pages": len(pages.pages),
                "cards": len(cards.cards) if cards else 0,
                "tokens_in": pages.prompt_tokens + (cards.prompt_tokens if cards else 0),
                "tokens_out": pages.completion_tokens + (cards.completion_tokens if cards else 0),
                "latency": latency,
                "warnings": warnings,
            }
        )
        print(
            path.name,
            f"blocks={len(blocks)} pages={len(pages.pages)} cards={len(cards.cards) if cards else 0}",
            f"latency={latency}ms warnings={len(warnings)}",
        )

    report_dir = settings.data_dir / "baseline"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# D4 五文档基线",
        "",
        f"- 模型：{settings.deepseek_model}",
        f"- 时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "| 文档 | blocks | pages | cards | tokens in | tokens out | 耗时 | 警告 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['doc']} | {row['blocks']} | {row['pages']} | {row['cards']} | "
            f"{row['tokens_in']} | {row['tokens_out']} | {row['latency'] / 1000:.1f}s | "
            f"{len(row['warnings'])} |"
        )
    lines.append("")
    for row in rows:
        if row["warnings"]:
            lines.append(f"## {row['doc']}")
            lines.extend(f"- {warning}" for warning in row["warnings"])
            lines.append("")

    report_path = report_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("report", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
