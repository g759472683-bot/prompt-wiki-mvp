from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Feedback, User

MIN_SAMPLES = 5
LEVELS = ("green", "yellow", "red")


def calibration_buckets(session: Session, user: User) -> dict:
    rows = session.scalars(
        select(Feedback).where(
            Feedback.user_id == user.id,
            Feedback.label.in_(("useful", "not_useful")),
        )
    ).all()
    buckets = []
    total = len(rows)
    calibrated_any = False
    for level in LEVELS:
        subset = [row for row in rows if row.confidence == level]
        useful = sum(1 for row in subset if row.label == "useful")
        not_useful = sum(1 for row in subset if row.label == "not_useful")
        answered = useful + not_useful
        accuracy = round(useful / answered, 4) if answered else None
        calibrated = answered >= MIN_SAMPLES
        calibrated_any = calibrated_any or calibrated
        buckets.append(
            {
                "confidence": level,
                "samples": answered,
                "useful": useful,
                "not_useful": not_useful,
                "accuracy": accuracy,
                "calibrated": calibrated,
            }
        )
    return {
        "buckets": buckets,
        "total": total,
        "calibrated": calibrated_any,
        "note": (
            f"每个置信档至少 {MIN_SAMPLES} 条反馈才显示实测准确率；"
            "当前是分档经验校准，不是概率模型。"
        ),
    }


def apply_calibration(session: Session, user: User, pack: dict) -> None:
    data = calibration_buckets(session, user)
    by_level = {item["confidence"]: item for item in data["buckets"]}
    for card in pack.get("cards") or []:
        confidence = card.get("confidence") or {}
        level = confidence.get("level") or "yellow"
        bucket = by_level.get(level)
        if not bucket or not bucket["calibrated"] or bucket["accuracy"] is None:
            continue
        confidence["score"] = int(round(bucket["accuracy"] * 100))
        confidence["calibrated"] = True
        confidence["calibration_samples"] = bucket["samples"]
        reasons = list(confidence.get("reasons") or [])
        if "empirical_calibration" not in reasons:
            reasons.append("empirical_calibration")
        confidence["reasons"] = reasons
        card["confidence"] = confidence
