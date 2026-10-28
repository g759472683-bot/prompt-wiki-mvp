from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import PointPin, User, utcnow
from ..schemas import PointPinIn, PointPinOut

router = APIRouter(tags=["pins"])


def _out(pin: PointPin) -> PointPinOut:
    return PointPinOut(
        qa_id=pin.qa_id,
        point_index=pin.point_index,
        summary=pin.summary,
        detail=pin.detail,
        updated_at=pin.updated_at.isoformat(),
    )


@router.put("/pins/point", response_model=PointPinOut)
def pin_point(
    payload: PointPinIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PointPinOut:
    if not payload.summary.strip() and not payload.detail.strip():
        raise HTTPException(status_code=422, detail="summary or detail required")
    pin = session.scalar(
        select(PointPin).where(
            PointPin.user_id == user.id,
            PointPin.qa_id == payload.qa_id,
            PointPin.point_index == payload.point_index,
        )
    )
    if pin is None:
        pin = PointPin(
            id="pin-" + uuid.uuid4().hex[:12],
            user_id=user.id,
            qa_id=payload.qa_id,
            point_index=payload.point_index,
            summary=payload.summary.strip(),
            detail=payload.detail.strip(),
        )
        session.add(pin)
    else:
        pin.summary = payload.summary.strip()
        pin.detail = payload.detail.strip()
        pin.updated_at = utcnow()
    session.commit()
    session.refresh(pin)
    return _out(pin)


@router.get("/pins", response_model=list[PointPinOut])
def list_pins(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[PointPinOut]:
    pins = session.scalars(
        select(PointPin)
        .where(PointPin.user_id == user.id)
        .order_by(PointPin.updated_at.desc())
    ).all()
    return [_out(pin) for pin in pins]


@router.delete("/pins/point")
def delete_pin(
    qa_id: str = Query(..., min_length=2, max_length=120),
    point_index: int = Query(..., ge=1, le=10),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    pin = session.scalar(
        select(PointPin).where(
            PointPin.user_id == user.id,
            PointPin.qa_id == qa_id,
            PointPin.point_index == point_index,
        )
    )
    if pin is None:
        raise HTTPException(status_code=404, detail="pin not found")
    session.delete(pin)
    session.commit()
    return {"deleted": True}
