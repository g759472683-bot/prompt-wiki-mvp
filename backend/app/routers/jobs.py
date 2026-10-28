from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import Job, User, utcnow
from ..schemas import CompileJobCreate, JobOut
from ..services.jobs import create_compile_job
from .documents import _get_owned_document

router = APIRouter(tags=["jobs"])


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        progress=job.progress,
        error=job.error,
        result=job.result,
        created_at=job.created_at or utcnow(),
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post(
    "/compile-jobs",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_compile_job_endpoint(
    payload: CompileJobCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobOut:
    doc = _get_owned_document(session, user, payload.document_id)
    if doc.status != "parsed":
        raise HTTPException(status_code=422, detail="document is not parsed")
    if getattr(request.app.state, "llm", None) is None:
        raise HTTPException(
            status_code=503,
            detail="LLM is not configured (set DEEPSEEK_API_KEY on the server)",
        )
    job = create_compile_job(
        session,
        user_id=user.id,
        document_id=doc.id,
        with_cards=payload.with_cards,
    )
    return _job_out(job)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[JobOut]:
    jobs = session.scalars(
        select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(50)
    ).all()
    return [_job_out(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobOut:
    job = session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_out(job)
