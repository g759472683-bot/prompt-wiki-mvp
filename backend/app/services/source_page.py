from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .parsing import ParseResult

if TYPE_CHECKING:
    from ..config import Settings
    from ..models import Block, Document


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text[:limit]


def render_source_page(doc: Document, blocks: list[Block], parsed: ParseResult) -> str:
    title = _clip(Path(doc.filename).stem or "未命名文档", 40)
    warnings = list(parsed.warnings)
    coverage = "partial" if any(w.get("code") == "EMPTY_PAGE" for w in warnings) else "full"
    tags = [doc.doc_type] if doc.doc_type and doc.doc_type != "other" else []

    front = {
        "schema_version": "1.0",
        "id": doc.source_id,
        "type": "source",
        "title": title,
        "summary": _clip(f"导入文档：{doc.filename}", 80),
        "status": "active",
        "language": "zh-CN",
        "revision": 1,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.created_at.isoformat(),
        "created_by": "compiler",
        "run_id": None,
        "source": {
            "doc_id": doc.id,
            "filename": doc.filename,
            "mime": doc.mime,
            "sha256": doc.sha256,
            "bytes": doc.size_bytes,
            "pages": parsed.pages,
            "imported_at": doc.created_at.isoformat(),
            "parser": parsed.parser,
            "parser_version": parsed.parser_version,
            "language": "zh-CN",
        },
        "trust": doc.trust,
        "version": 1,
        "supersedes": None,
        "archived_at": None,
        "extraction": {
            "blocks": len(blocks),
            "warnings": warnings,
            "coverage": coverage,
            "ocr": False,
        },
        "notes": None,
        "tags": tags,
    }

    body = [f"# {title}", ""]
    for block in blocks:
        body.append(
            f"<!-- {block.block_id} | p.{block.page} | "
            f"chars:{block.char_start}-{block.char_end} -->"
        )
        body.append(block.text)
        body.append("")

    yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{yaml_text}---\n\n" + "\n".join(body).rstrip() + "\n"


def source_path(settings: Settings, user_id: str, doc_id: str) -> Path:
    return settings.data_dir / "users" / user_id / "wiki" / "sources" / f"{doc_id}.md"


def write_source_page(
    settings: Settings,
    user_id: str,
    doc: Document,
    blocks: list[Block],
    parsed: ParseResult,
) -> Path:
    path = source_path(settings, user_id, doc.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_source_page(doc, blocks, parsed), encoding="utf-8")
    return path
