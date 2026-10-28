from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..config import Settings
from ..models import User, utcnow

RUN_ID_RE = re.compile(r"^run-\d{8}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PAGE_TYPES = {"claim", "metric", "qa", "story", "entity", "scenario"}


class RunNotFound(Exception):
    pass


def _run_root(settings: Settings, user_id: str, run_id: str) -> Path:
    if not RUN_ID_RE.match(run_id):
        raise RunNotFound(run_id)
    return settings.data_dir / "users" / user_id / "wiki"


def _read_front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing frontmatter: {path}")
    return yaml.safe_load(text.split("---", 2)[1]) or {}


def _slug(page_id: str) -> str:
    return page_id.split(":", 1)[1]


def load_run(settings: Settings, user_id: str, run_id: str) -> dict:
    wiki = _run_root(settings, user_id, run_id)
    staging = wiki / ".staging" / run_id
    manifest_path = wiki / "runs" / run_id / "manifest.yaml"
    if not staging.exists() or not manifest_path.exists():
        raise RunNotFound(run_id)

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    pages = []
    for path in sorted((staging / "pages").rglob("*.md")):
        front = _read_front(path)
        page_id = front.get("id")
        page_type = front.get("type")
        if not page_id or not page_type:
            continue
        if page_type not in PAGE_TYPES or not SLUG_RE.match(_slug(page_id)):
            continue
        target = wiki / "pages" / page_type / f"{_slug(page_id)}.md"
        pages.append(
            {
                "id": page_id,
                "type": page_type,
                "title": front.get("title", ""),
                "status": front.get("status", "draft"),
                "confidence": (front.get("confidence") or {}).get("level"),
                "evidence_count": len(front.get("evidence") or []),
                "path": str(path.relative_to(wiki)).replace("\\", "/"),
                "target": str(target.relative_to(wiki)).replace("\\", "/"),
                "collision": target.exists(),
                "_front": front,
                "_path": path,
            }
        )

    pack = None
    pack_path = staging / "pack.json"
    if pack_path.exists():
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
    cards = []
    if pack:
        for card in pack.get("cards", []):
            cards.append(
                {
                    "qa_id": card.get("qa_id", ""),
                    "question": card.get("question", ""),
                    "confidence": (card.get("confidence") or {}).get("level", "yellow"),
                    "citation_count": len(card.get("citations") or []),
                }
            )

    return {
        "run_id": run_id,
        "document_id": (manifest.get("document") or {}).get("id"),
        "pages": pages,
        "cards": cards,
        "warnings": manifest.get("warnings") or [],
        "collisions": [page["id"] for page in pages if page["collision"]],
        "pack": pack,
        "wiki": wiki,
    }


def approve_run(
    settings: Settings,
    user: User,
    run_id: str,
    replace: bool = False,
) -> dict:
    data = load_run(settings, user.id, run_id)
    wiki: Path = data["wiki"]
    now = utcnow()
    reviewer = f"human:{user.name or user.id}"
    approved: list[str] = []

    for page in data["pages"]:
        if page["collision"] and not replace:
            continue
        front = dict(page["_front"])
        front["status"] = "active"
        front["updated_at"] = now.astimezone(timezone.utc).isoformat()
        front["review"] = {
            "reviewed_by": reviewer,
            "reviewed_at": now.astimezone(timezone.utc).isoformat(),
            "review_run": run_id,
        }
        confidence = dict(front.get("confidence") or {})
        reasons = [r for r in (confidence.get("reasons") or []) if r != "unreviewed"]
        confidence["reasons"] = reasons or ["single_source"]
        front["confidence"] = confidence
        card = front.get("card")
        if isinstance(card, dict):
            card_conf = dict(card.get("confidence") or {})
            card_reasons = [
                r for r in (card_conf.get("reasons") or []) if r != "unreviewed"
            ]
            card_conf["reasons"] = card_reasons or ["single_source"]
            card["confidence"] = card_conf

        target = wiki / page["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=1000)
        body = page["_path"].read_text(encoding="utf-8").split("---", 2)[2].lstrip("\n")
        target.write_text(f"---\n{yaml_text}---\n\n{body}", encoding="utf-8")
        approved.append(page["id"])

    pack_path_rel = None
    pack = data.get("pack")
    if pack:
        pack = dict(pack)
        pack["approved"] = True
        pack["approved_at"] = now.astimezone(timezone.utc).isoformat()
        pack["approved_by"] = reviewer
        pack_id = pack.get("pack_id") or f"pack-{run_id.removeprefix('run-')}"
        pack["pack_id"] = pack_id
        target_pack = wiki / "packs" / f"{pack_id}.json"
        target_pack.parent.mkdir(parents=True, exist_ok=True)
        target_pack.write_text(
            json.dumps(pack, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        pack_path_rel = str(target_pack.relative_to(wiki)).replace("\\", "/")

    run_dir = wiki / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    review_record = {
        "schema_version": "1.0",
        "run_id": run_id,
        "reviewer": reviewer,
        "reviewed_at": now.astimezone(timezone.utc).isoformat(),
        "approved_pages": approved,
        "collisions": data["collisions"],
    }
    (run_dir / "review.yaml").write_text(
        yaml.safe_dump(review_record, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    return {
        "run_id": run_id,
        "approved_pages": approved,
        "collisions": data["collisions"],
        "pack_path": pack_path_rel,
    }
