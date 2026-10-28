from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeviceAuthRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=80)


class TokenResponse(BaseModel):
    token: str
    user_id: str
    expires_at: datetime


class DocumentOut(BaseModel):
    id: str
    filename: str
    status: str
    source_id: str | None
    block_count: int
    doc_type: str
    trust: str
    error: str | None = None
    duplicate: bool = False
    created_at: datetime


class BlockOut(BaseModel):
    block_id: str
    page: int
    chars_start: int
    chars_end: int
    text: str


class QuoteRequest(BaseModel):
    block_id: str = Field(pattern=r"^b-\d{4}$")
    quote: str = Field(min_length=1, max_length=200)


class QuoteOut(BaseModel):
    matched: bool
    match_type: str | None = None
    block_id: str
    page: int
    quote: str
    start: int | None = None
    end: int | None = None
    context_before: str = ""
    context_after: str = ""


class CompiledPageOut(BaseModel):
    id: str
    type: str
    title: str
    path: str
    confidence: str
    evidence_count: int


class CompiledCardOut(BaseModel):
    id: str
    question: str
    confidence: str
    evidence_count: int
    path: str


class CompileOut(BaseModel):
    run_id: str
    pages: list[CompiledPageOut]
    cards: list[CompiledCardOut]
    warnings: list[str]
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model: str


class CompileJobCreate(BaseModel):
    document_id: str = Field(min_length=3, max_length=40)
    with_cards: bool = True


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: int
    error: str | None = None
    result: dict | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunPageOut(BaseModel):
    id: str
    type: str
    title: str
    status: str
    confidence: str | None = None
    evidence_count: int
    path: str


class RunCardOut(BaseModel):
    qa_id: str
    question: str
    confidence: str
    citation_count: int


class RunReviewOut(BaseModel):
    run_id: str
    document_id: str | None = None
    pages: list[RunPageOut]
    cards: list[RunCardOut]
    warnings: list[str]
    collisions: list[str]


class ApproveOut(BaseModel):
    run_id: str
    approved_pages: list[str]
    collisions: list[str]
    pack_path: str | None = None


class PackSummaryOut(BaseModel):
    pack_id: str
    approved_at: str | None = None
    card_count: int
    pack_path: str


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=200)
    pack_id: str | None = None
    allow_ungrounded: bool = False


class AskCardOut(BaseModel):
    l1: list[str]
    l2: list[str]
    l3: str
    fallback: str
    confidence: dict
    citations: list[dict]
    do_not_say: list[str]
    must_show_fallback_first: bool


class AskOut(BaseModel):
    matched: bool
    hit_path: str
    question: str
    degraded: bool
    ungrounded: bool = False
    card: AskCardOut
    latency_ms: int
    model: str
    notices: list[str]


class ReleaseOut(BaseModel):
    id: str
    version_code: int
    version_name: str
    notes: str | None
    filename: str
    size_bytes: int
    sha256: str
    active: bool
    download_url: str


class LatestReleaseOut(BaseModel):
    version_code: int
    version_name: str
    notes: str | None
    download_url: str
    sha256: str


class PointPinIn(BaseModel):
    qa_id: str = Field(min_length=2, max_length=120)
    point_index: int = Field(ge=1, le=10)
    summary: str = Field(default="", max_length=60)
    detail: str = Field(default="", max_length=500)


class PointPinOut(BaseModel):
    qa_id: str
    point_index: int
    summary: str
    detail: str
    updated_at: str


class FeedbackIn(BaseModel):
    pack_id: str = Field(default="", max_length=80)
    qa_id: str = Field(default="", max_length=120)
    question: str = Field(default="", max_length=200)
    label: Literal["useful", "not_useful", "fallback"]
    confidence: Literal["green", "yellow", "red"] = "yellow"


class CalibrationBucket(BaseModel):
    confidence: str
    samples: int
    useful: int
    not_useful: int
    accuracy: float | None
    calibrated: bool


class CalibrationOut(BaseModel):
    buckets: list[CalibrationBucket]
    total: int
    calibrated: bool
    note: str


class ConsistencyItem(BaseModel):
    id: str
    type: str
    severity: str
    topic: str
    message: str
    values: list[dict]


class ConsistencyOut(BaseModel):
    generated_at: str
    document_count: int
    high: int
    medium: int
    conflicts: list[ConsistencyItem]
