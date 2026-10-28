from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..llm.client import LLMError
from ..models import Block, User
from ..schemas import CompiledCardOut, CompiledPageOut, CompileOut
from ..services.cards import compile_cards
from ..services.compiler import SourceBlock, SourceDoc, compile_document
from .documents import _get_owned_document

router = APIRouter(tags=["compile"])


@router.post("/documents/{doc_id}/compile", response_model=CompileOut)
def compile_document_endpoint(
    doc_id: str,
    request: Request,
    with_cards: bool = Query(True, description="是否继续生成 10-15 张提词卡"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CompileOut:
    doc = _get_owned_document(session, user, doc_id)
    if doc.status != "parsed":
        raise HTTPException(status_code=422, detail="document is not parsed")
    llm = getattr(request.app.state, "llm", None)
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="LLM is not configured (set DEEPSEEK_API_KEY on the server)",
        )

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
        result = compile_document(
            llm=llm,
            settings=request.app.state.settings,
            user_id=user.id,
            doc=source_doc,
            blocks=source_blocks,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not result.pages:
        raise HTTPException(
            status_code=422,
            detail={"message": "编译没有产出可用页面", "warnings": result.warnings},
        )

    cards = []
    warnings = list(result.warnings)
    prompt_tokens = result.prompt_tokens
    completion_tokens = result.completion_tokens
    latency_ms = result.latency_ms
    if with_cards:
        try:
            card_result = compile_cards(
                llm=llm,
                settings=request.app.state.settings,
                user_id=user.id,
                doc=source_doc,
                run_id=result.run_id,
            )
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        warnings.extend(card_result.warnings)
        prompt_tokens += card_result.prompt_tokens
        completion_tokens += card_result.completion_tokens
        latency_ms += card_result.latency_ms
        cards = [
            CompiledCardOut(
                id=card.id,
                question=card.question,
                confidence=card.confidence,
                evidence_count=card.evidence_count,
                path=card.path,
            )
            for card in card_result.cards
        ]
        if not cards:
            warnings.append("CARD_BUILD_EMPTY：没有卡片通过校验")

    return CompileOut(
        run_id=result.run_id,
        pages=[
            CompiledPageOut(
                id=page.id,
                type=page.type,
                title=page.title,
                path=page.path,
                confidence=page.confidence,
                evidence_count=page.evidence_count,
            )
            for page in result.pages
        ],
        cards=cards,
        warnings=warnings,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        model=result.model,
    )
