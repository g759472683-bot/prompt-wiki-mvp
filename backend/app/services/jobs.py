from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..llm.client import LLMClient
from ..models import Block, Document, Job, utcnow
from .cards import compile_cards
from .compiler import SourceBlock, SourceDoc, compile_document


def _job_id() -> str:
    return "job-" + uuid.uuid4().hex[:12]


def create_compile_job(
    session: Session,
    user_id: str,
    document_id: str,
    with_cards: bool,
) -> Job:
    job = Job(
        id=_job_id(),
        user_id=user_id,
        kind="compile",
        status="queued",
        payload={"document_id": document_id, "with_cards": with_cards},
        progress=0,
    )
    session.add(job)
    session.commit()
    return job


def _fail(session: Session, job: Job, message: str) -> Job:
    job.status = "failed"
    job.error = message[:1000]
    job.finished_at = utcnow()
    session.commit()
    return job


def execute_job(
    session: Session,
    settings: Settings,
    llm: LLMClient | None,
    job: Job,
) -> Job:
    job.status = "running"
    job.started_at = utcnow()
    job.attempts += 1
    job.progress = 5
    session.commit()

    if llm is None:
        return _fail(session, job, "LLM is not configured (set DEEPSEEK_API_KEY)")

    payload = job.payload or {}
    document_id = payload.get("document_id")
    with_cards = bool(payload.get("with_cards", True))
    doc = session.get(Document, document_id) if document_id else None
    if doc is None or doc.user_id != job.user_id or doc.status == "deleted":
        return _fail(session, job, "document not found")
    if doc.status != "parsed":
        return _fail(session, job, "document is not parsed")

    blocks = session.scalars(
        select(Block).where(Block.document_id == doc.id).order_by(Block.position)
    ).all()
    source_doc = SourceDoc(
        id=doc.id,
        source_id=doc.source_id or f"source:{doc.id}",
        filename=doc.filename,
        doc_type=doc.doc_type,
        created_at=doc.created_at,
    )
    source_blocks = [
        SourceBlock(block_id=block.block_id, page=block.page, text=block.text)
        for block in blocks
    ]

    try:
        pages = compile_document(
            llm=llm,
            settings=settings,
            user_id=job.user_id,
            doc=source_doc,
            blocks=source_blocks,
        )
        job.progress = 55
        session.commit()

        cards = None
        warnings = list(pages.warnings)
        if with_cards:
            cards = compile_cards(
                llm=llm,
                settings=settings,
                user_id=job.user_id,
                doc=source_doc,
                run_id=pages.run_id,
            )
            warnings.extend(cards.warnings)
        job.progress = 90
        session.commit()
    except Exception as exc:  # noqa: BLE001 - persist any failure to the job
        return _fail(session, job, f"{exc.__class__.__name__}: {exc}")

    if not pages.pages:
        return _fail(session, job, "no pages produced; " + "; ".join(pages.warnings))

    job.result = {
        "run_id": pages.run_id,
        "pages": [
            {
                "id": page.id,
                "type": page.type,
                "title": page.title,
                "path": page.path,
                "confidence": page.confidence,
                "evidence_count": page.evidence_count,
            }
            for page in pages.pages
        ],
        "cards": [
            {
                "id": card.id,
                "question": card.question,
                "confidence": card.confidence,
                "evidence_count": card.evidence_count,
                "path": card.path,
            }
            for card in (cards.cards if cards else [])
        ],
        "warnings": warnings,
        "pack_path": cards.pack_path if cards else "",
        "prompt_tokens": pages.prompt_tokens + (cards.prompt_tokens if cards else 0),
        "completion_tokens": pages.completion_tokens
        + (cards.completion_tokens if cards else 0),
        "latency_ms": pages.latency_ms + (cards.latency_ms if cards else 0),
        "model": pages.model,
    }
    job.status = "succeeded"
    job.progress = 100
    job.finished_at = utcnow()
    job.error = None
    session.commit()
    return job


def process_next_job(
    session_factory: sessionmaker,
    settings: Settings,
    llm: LLMClient | None,
) -> str | None:
    with session_factory() as session:
        job = session.scalar(
            select(Job)
            .where(Job.status == "queued")
            .order_by(Job.created_at)
            .limit(1)
        )
        if job is None:
            return None
        job_id = job.id

    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None
        execute_job(session, settings, llm, job)
        return job_id


def next_wait_seconds(now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    return 2.0
