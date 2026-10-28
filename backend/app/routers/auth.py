from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_session
from ..models import Device, User, utcnow
from ..schemas import DeviceAuthRequest, TokenResponse
from ..security import create_token

router = APIRouter(tags=["auth"])


def workspace_key(invite_code: str) -> str:
    digest = hashlib.sha256(invite_code.strip().encode("utf-8")).hexdigest()
    return "ws-" + digest[:32]


def adopt_legacy_workspace(session: Session, settings: Settings) -> None:
    """Bind a single pre-workspace user to the first invite code.

    This keeps the two documents uploaded before the workspace change.
    """
    codes = [c for c in settings.invite_codes.split(",") if c.strip()]
    if not codes:
        return
    key = workspace_key(codes[0])
    if session.scalar(select(User).where(User.workspace_key == key)) is not None:
        return
    legacy = session.scalars(select(User).where(User.workspace_key.is_(None))).all()
    if len(legacy) != 1:
        return
    user = legacy[0]
    user.workspace_key = key
    if session.scalar(select(Device).where(Device.device_id == user.device_id)) is None:
        session.add(
            Device(
                id="dev-" + uuid.uuid4().hex[:12],
                user_id=user.id,
                device_id=user.device_id,
                name=user.name,
            )
        )
    session.commit()


@router.post("/auth/device", response_model=TokenResponse)
def auth_device(
    payload: DeviceAuthRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TokenResponse:
    settings: Settings = request.app.state.settings
    if payload.invite_code not in settings.invite_code_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid invite code",
        )

    key = workspace_key(payload.invite_code)
    now = utcnow()
    user = session.scalar(select(User).where(User.workspace_key == key))

    if user is None:
        # The phone that uploaded before workspaces existed keeps its data.
        legacy = session.scalar(
            select(User).where(
                User.device_id == payload.device_id,
                User.workspace_key.is_(None),
            )
        )
        if legacy is not None:
            legacy.workspace_key = key
            user = legacy
        else:
            user = User(
                id="usr-" + uuid.uuid4().hex[:12],
                device_id=payload.device_id,
                workspace_key=key,
                name=payload.name,
            )
            session.add(user)
            session.flush()
        session.commit()

    if payload.name and user.name != payload.name:
        user.name = payload.name

    device = session.scalar(
        select(Device).where(Device.device_id == payload.device_id)
    )
    if device is None:
        session.add(
            Device(
                id="dev-" + uuid.uuid4().hex[:12],
                user_id=user.id,
                device_id=payload.device_id,
                name=payload.name,
                last_seen_at=now,
            )
        )
    else:
        device.user_id = user.id
        device.last_seen_at = now
        if payload.name:
            device.name = payload.name
    session.commit()

    token, expires_at = create_token(user.id, settings)
    return TokenResponse(token=token, user_id=user.id, expires_at=expires_at)
