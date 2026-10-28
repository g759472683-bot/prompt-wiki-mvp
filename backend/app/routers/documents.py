from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import Block, Document, User, utcnow
from ..schemas import BlockOut, DocumentOut, QuoteOut, QuoteRequest
from ..services.documents import ALLOWED_SUFFIXES, block_count, create_document
from ..services.quote import find_quote

router = APIRouter(tags=["documents"])

DOC_TYPES = {"resume", "jd", "project", "notes", "other"}
TRUST_LEVELS = {"high", "medium", "low"}


def _document_out(doc: Document, count: int, duplicate: bool = False) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        source_id=doc.source_id,
        block_count=count,
        doc_type=doc.doc_type,
        trust=doc.trust,
        error=doc.error,
        duplicate=duplicate,
        created_at=doc.created_at or utcnow(),
    )


def _get_owned_document(session: Session, user: User, doc_id: str) -> Document:
    doc = session.get(Document, doc_id)
    if doc is None or doc.user_id != user.id or doc.status == "deleted":
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    doc_type: str = Form("other"),
    trust: str = Form("medium"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DocumentOut:
    settings = request.app.state.settings
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=422, detail=f"doc_type must be one of {sorted(DOC_TYPES)}")
    if trust not in TRUST_LEVELS:
        raise HTTPException(status_code=422, detail=f"trust must be one of {sorted(TRUST_LEVELS)}")

    filename = file.filename or "upload"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported file type: {suffix or '(none)'}",
        )

    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if not data:
        raise HTTPException(status_code=422, detail="empty file")
    if len(data) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds {settings.max_upload_mb}MB",
        )

    doc, count, duplicate = create_document(
        session=session,
        settings=settings,
        user=user,
        filename=filename,
        content_type=file.content_type,
        data=data,
        doc_type=doc_type,
        trust=trust,
    )
    return _document_out(doc, count, duplicate)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[DocumentOut]:
    docs = session.scalars(
        select(Document)
        .where(Document.user_id == user.id, Document.status != "deleted")
        .order_by(Document.created_at.desc())
    ).all()
    return [_document_out(doc, block_count(session, doc.id)) for doc in docs]


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DocumentOut:
    doc = _get_owned_document(session, user, doc_id)
    return _document_out(doc, block_count(session, doc.id))


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    doc = _get_owned_document(session, user, doc_id)
    doc.status = "deleted"
    doc.deleted_at = utcnow()
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/documents/{doc_id}/blocks", response_model=list[BlockOut])
def list_blocks(
    doc_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[BlockOut]:
    _get_owned_document(session, user, doc_id)
    blocks = session.scalars(
        select(Block).where(Block.document_id == doc_id).order_by(Block.position)
    ).all()
    return [
        BlockOut(
            block_id=block.block_id,
            page=block.page,
            chars_start=block.char_start,
            chars_end=block.char_end,
            text=block.text,
        )
        for block in blocks
    ]


@router.get("/documents/{doc_id}/blocks/{block_id}", response_model=BlockOut)
def get_block(
    doc_id: str,
    block_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BlockOut:
    _get_owned_document(session, user, doc_id)
    block = session.scalar(
        select(Block).where(Block.document_id == doc_id, Block.block_id == block_id)
    )
    if block is None:
        raise HTTPException(status_code=404, detail="block not found")
    return BlockOut(
        block_id=block.block_id,
        page=block.page,
        chars_start=block.char_start,
        chars_end=block.char_end,
        text=block.text,
    )


@router.post("/documents/{doc_id}/quote", response_model=QuoteOut)
def check_quote(
    doc_id: str,
    payload: QuoteRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> QuoteOut:
    _get_owned_document(session, user, doc_id)
    block = session.scalar(
        select(Block).where(
            Block.document_id == doc_id,
            Block.block_id == payload.block_id,
        )
    )
    if block is None:
        raise HTTPException(status_code=404, detail="block not found")

    match_type, start, end = find_quote(block.text, payload.quote)
    if match_type is None:
        return QuoteOut(
            matched=False,
            block_id=block.block_id,
            page=block.page,
            quote=payload.quote,
        )
    return QuoteOut(
        matched=True,
        match_type=match_type,
        block_id=block.block_id,
        page=block.page,
        quote=payload.quote,
        start=start,
        end=end,
        context_before=block.text[max(0, start - 60) : start],
        context_after=block.text[end : end + 60],
    )


sources_router = APIRouter(tags=["sources"])


@sources_router.get("/sources/{source_id}/blocks/{block_id}", response_model=BlockOut)
def get_source_block(
    source_id: str,
    block_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BlockOut:
    doc = session.scalar(
        select(Document).where(
            Document.source_id == source_id,
            Document.user_id == user.id,
            Document.status != "deleted",
        )
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="source not found")
    block = session.scalar(
        select(Block).where(Block.document_id == doc.id, Block.block_id == block_id)
    )
    if block is None:
        raise HTTPException(status_code=404, detail="block not found")
    return BlockOut(
        block_id=block.block_id,
        page=block.page,
        chars_start=block.char_start,
        chars_end=block.char_end,
        text=block.text,
    )
