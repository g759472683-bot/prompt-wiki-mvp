from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Block, Document, User, utcnow
from .parsing import ParseError, parse_document
from .source_page import write_source_page

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}
MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


def block_count(session: Session, document_id: str) -> int:
    value = session.scalar(
        select(func.count(Block.id)).where(Block.document_id == document_id)
    )
    return int(value or 0)


def _fail(session: Session, doc: Document, message: str) -> Document:
    doc.status = "failed"
    doc.error = message
    session.commit()
    return doc


def create_document(
    session: Session,
    settings: Settings,
    user: User,
    filename: str,
    content_type: str | None,
    data: bytes,
    doc_type: str,
    trust: str,
) -> tuple[Document, int, bool]:
    """Persist + parse a document. Returns (document, block_count, duplicate)."""
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"文件超过 {settings.max_upload_mb}MB")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"不支持的文件类型：{suffix or '(无扩展名)'}")

    sha256 = hashlib.sha256(data).hexdigest()
    existing = session.scalar(
        select(Document).where(
            Document.user_id == user.id,
            Document.sha256 == sha256,
            Document.status != "deleted",
        )
    )
    if existing is not None:
        return existing, block_count(session, existing.id), True

    doc = Document(
        id="doc-" + uuid.uuid4().hex[:12],
        user_id=user.id,
        filename=Path(filename).name[:255],
        mime=content_type or MIME_BY_SUFFIX.get(suffix, "application/octet-stream"),
        doc_type=doc_type,
        trust=trust,
        sha256=sha256,
        size_bytes=len(data),
        status="uploaded",
        created_at=utcnow(),
    )
    session.add(doc)
    session.flush()

    upload_dir = settings.data_dir / "users" / user.id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"{doc.id}{suffix}"
    upload_path.write_bytes(data)

    try:
        parsed = parse_document(upload_path, filename)
    except ParseError as exc:
        return _fail(session, doc, str(exc)), 0, False
    except Exception as exc:  # defensive: never leak a 500 for a bad file
        return _fail(session, doc, f"解析失败：{exc}"), 0, False

    blocks: list[Block] = []
    for position, parsed_block in enumerate(parsed.blocks, start=1):
        if position > 9999:
            return _fail(session, doc, "文档 block 数超过上限（9999）"), 0, False
        block = Block(
            document_id=doc.id,
            block_id=f"b-{position:04d}",
            position=position,
            page=parsed_block.page,
            char_start=parsed_block.start,
            char_end=parsed_block.end,
            text=parsed_block.text,
        )
        session.add(block)
        blocks.append(block)

    doc.source_id = f"source:{doc.id}"
    try:
        write_source_page(settings, user.id, doc, blocks, parsed)
    except OSError as exc:
        return _fail(session, doc, f"写入 source 页失败：{exc}"), 0, False

    doc.status = "parsed"
    doc.error = None
    session.commit()
    return doc, len(blocks), False
