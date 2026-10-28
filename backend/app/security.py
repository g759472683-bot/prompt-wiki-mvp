from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from .config import Settings


def create_token(user_id: str, settings: Settings) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.token_ttl_days)
    token = jwt.encode(
        {
            "sub": user_id,
            "exp": expires_at,
            "jti": uuid.uuid4().hex,
        },
        settings.secret_key,
        algorithm="HS256",
    )
    return token, expires_at


def decode_token(token: str, settings: Settings) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
