from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/healthz")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "env": request.app.state.settings.env}
