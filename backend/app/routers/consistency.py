from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import User
from ..schemas import ConsistencyOut
from ..services.consistency import scan_consistency

router = APIRouter(tags=["consistency"])


@router.get("/consistency", response_model=ConsistencyOut)
def get_consistency(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ConsistencyOut:
    return ConsistencyOut(
        **scan_consistency(request.app.state.settings, user, session)
    )


@router.post("/consistency/scan", response_model=ConsistencyOut)
def scan(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ConsistencyOut:
    return ConsistencyOut(
        **scan_consistency(request.app.state.settings, user, session)
    )
