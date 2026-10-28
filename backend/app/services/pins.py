from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PointPin, User


def apply_pins(session: Session, user: User, pack: dict) -> None:
    cards = pack.get("cards") or []
    qa_ids = [card.get("qa_id") for card in cards if card.get("qa_id")]
    if not qa_ids:
        return
    pins = session.scalars(
        select(PointPin).where(
            PointPin.user_id == user.id,
            PointPin.qa_id.in_(qa_ids),
        )
    ).all()
    if not pins:
        return
    by_key = {(pin.qa_id, pin.point_index): pin for pin in pins}
    for card in cards:
        qa_id = card.get("qa_id") or ""
        for point in card.get("points") or []:
            try:
                index = int(point.get("index"))
            except (TypeError, ValueError):
                continue
            pin = by_key.get((qa_id, index))
            if pin is None:
                continue
            if pin.summary.strip():
                point["summary"] = pin.summary
            if pin.detail.strip():
                point["detail"] = pin.detail
            point["pinned"] = True
            point["pin_updated_at"] = pin.updated_at.isoformat()
