"""Offline smoke test for the parts that do not need FastAPI/SQLAlchemy.

Run from backend/:  python scripts/smoke_source_page.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.parsing import ParsedBlock, ParseResult, _split_paragraphs  # noqa: E402
from app.services.quote import find_quote  # noqa: E402
from app.services.source_page import render_source_page  # noqa: E402


class FakeDoc:
    id = "doc-0123456789ab"
    source_id = "source:doc-0123456789ab"
    filename = "林舟-简历-2026.txt"
    mime = "text/plain"
    sha256 = "a" * 64
    size_bytes = 128
    trust = "high"
    doc_type = "resume"
    created_at = datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc)


class FakeBlock:
    def __init__(self, block_id: str, page: int, start: int, end: int, text: str):
        self.block_id = block_id
        self.page = page
        self.char_start = start
        self.char_end = end
        self.text = text


def main() -> None:
    assert len(_split_paragraphs("a\n\nb\n\nc")) == 3
    assert find_quote("账务平台年度可用性 99.99%。\n对账延迟", "99.99%。 对账")[0] == "normalized"
    assert find_quote("abc", "zzz")[0] is None

    blocks = [
        FakeBlock("b-0001", 1, 0, 12, "林舟｜后端工程师"),
        FakeBlock("b-0002", 2, 0, 20, "账务平台年度可用性 99.99%"),
    ]
    parsed = ParseResult(
        blocks=[ParsedBlock(b.page, b.char_start, b.char_end, b.text) for b in blocks],
        pages=2,
        parser="plaintext",
        parser_version="1",
        warnings=[{"code": "EMPTY_PAGE", "message": "第 3 页没有文本"}],
    )
    text = render_source_page(FakeDoc(), blocks, parsed)
    assert text.startswith("---\n")
    assert "<!-- b-0001 | p.1 | chars:0-12 -->" in text
    assert "b-0002" in text

    front = yaml.safe_load(text.split("---", 2)[1])
    assert front["id"] == "source:doc-0123456789ab"
    assert front["source"]["sha256"] == "a" * 64
    assert front["extraction"]["coverage"] == "partial"

    schema_path = ROOT.parent / "schema" / "page.frontmatter.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(front)

    print("smoke-ok")
    print(text[:400])


if __name__ == "__main__":
    main()
