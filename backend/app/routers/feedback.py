from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import Feedback, User
from ..schemas import CalibrationOut, FeedbackIn
from ..services.calibration import calibration_buckets

router = APIRouter(tags=["feedback"])


@router.post("/feedback")
def create_feedback(
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    session.add(
        Feedback(
            id="fb-" + uuid.uuid4().hex[:12],
            user_id=user.id,
            pack_id=payload.pack_id,
            qa_id=payload.qa_id,
            question=payload.question,
            label=payload.label,
            confidence=payload.confidence,
        )
    )
    session.commit()
    return {"ok": True}


@router.get("/calibration", response_model=CalibrationOut)
def get_calibration(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CalibrationOut:
    return CalibrationOut(**calibration_buckets(session, user))
