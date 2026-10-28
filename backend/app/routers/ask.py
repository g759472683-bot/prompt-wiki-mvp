from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import User
from ..schemas import AskOut, AskRequest
from ..services.ask import ask_question

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskOut)
def ask(
    payload: AskRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AskOut:
    result = ask_question(
        llm=getattr(request.app.state, "llm", None),
        session=session,
        user=user,
        question=payload.question,
        allow_ungrounded=payload.allow_ungrounded,
    )
    return AskOut(**result)
