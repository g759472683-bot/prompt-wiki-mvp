from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import User
from ..schemas import PackSummaryOut
from ..services.calibration import apply_calibration
from ..services.pins import apply_pins

router = APIRouter(tags=["packs"])

PACK_ID_RE = re.compile(r"^pack-\d{8}-\d{2}$")


def _packs_dir(request: Request, user: User):
    return (
        request.app.state.settings.data_dir
        / "users"
        / user.id
        / "wiki"
        / "packs"
    )


@router.get("/packs", response_model=list[PackSummaryOut])
def list_packs(
    request: Request,
    user: User = Depends(get_current_user),
) -> list[PackSummaryOut]:
    directory = _packs_dir(request, user)
    if not directory.exists():
        return []
    out: list[PackSummaryOut] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pack_id = data.get("pack_id")
        if not pack_id:
            continue
        out.append(
            PackSummaryOut(
                pack_id=pack_id,
                approved_at=data.get("approved_at"),
                card_count=len(data.get("cards") or []),
                pack_path=f"packs/{path.name}",
            )
        )
    out.sort(key=lambda item: item.approved_at or "", reverse=True)
    return out


@router.get("/packs/{pack_id}")
def get_pack(
    pack_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    if not PACK_ID_RE.match(pack_id):
        raise HTTPException(status_code=404, detail="pack not found")
    path = _packs_dir(request, user) / f"{pack_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="pack not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="pack is corrupted") from exc
    apply_pins(session, user, data)
    apply_calibration(session, user, data)
    return JSONResponse(content=data)
