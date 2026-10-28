from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..deps import get_current_user
from ..models import User
from ..schemas import ApproveOut, RunCardOut, RunPageOut, RunReviewOut
from ..services.review import RunNotFound, approve_run, load_run

router = APIRouter(tags=["runs"])


@router.get("/runs/{run_id}/review", response_model=RunReviewOut)
def get_run_review(
    run_id: str,
    request: Request,
    user: User = Depends(get_current_user),
) -> RunReviewOut:
    try:
        data = load_run(request.app.state.settings, user.id, run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc

    return RunReviewOut(
        run_id=data["run_id"],
        document_id=data["document_id"],
        pages=[
            RunPageOut(
                id=page["id"],
                type=page["type"],
                title=page["title"],
                status=page["status"],
                confidence=page["confidence"],
                evidence_count=page["evidence_count"],
                path=page["path"],
            )
            for page in data["pages"]
        ],
        cards=[RunCardOut(**card) for card in data["cards"]],
        warnings=data["warnings"],
        collisions=data["collisions"],
    )


@router.post("/runs/{run_id}/approve", response_model=ApproveOut)
def approve_run_endpoint(
    run_id: str,
    request: Request,
    replace: bool = False,
    user: User = Depends(get_current_user),
) -> ApproveOut:
    try:
        data = load_run(request.app.state.settings, user.id, run_id)
        if not data["pages"]:
            raise HTTPException(status_code=404, detail="run has no pages")
        if data["collisions"] and not replace:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "some pages already exist; approve aborted",
                    "collisions": data["collisions"],
                },
            )
        result = approve_run(
            request.app.state.settings,
            user,
            run_id,
            replace=replace,
        )
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc

    return ApproveOut(**result)
