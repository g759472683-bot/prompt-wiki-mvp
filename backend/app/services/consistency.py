from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Document, User

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")
PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+")


def _normalize(text: str) -> str:
    return PUNCT_RE.sub("", (text or "").lower())


def _numbers(text: str) -> set[str]:
    return set(NUMBER_RE.findall(text or ""))


def _front(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            return None
        data = yaml.safe_load(text.split("---", 2)[1]) or {}
        return data if isinstance(data, dict) else None
    except (OSError, yaml.YAMLError):
        return None


def _conflict_id(prefix: str, key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"conf-{prefix}-{digest}"


def scan_consistency(
    settings: Settings,
    user: User,
    session: Session,
) -> dict:
    wiki = settings.data_dir / "users" / user.id / "wiki"
    documents = session.scalars(
        select(Document).where(
            Document.user_id == user.id,
            Document.status != "deleted",
        )
    ).all()
    by_source = {
        (doc.source_id or f"doc:{doc.id}"): doc for doc in documents
    }
    by_id = {f"doc:{doc.id}": doc for doc in documents}

    pages: list[dict] = []
    for page_type in ("metric", "claim"):
        directory = wiki / "pages" / page_type
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            front = _front(path)
            if not front or front.get("status") != "active":
                continue
            evidence = front.get("evidence") or []
            source_ids = {
                str(ev.get("source"))
                for ev in evidence
                if ev.get("source")
            }
            document_ids = set()
            for source_id in source_ids:
                doc = by_source.get(source_id)
                if doc is not None:
                    document_ids.add(doc.id)
                elif source_id.startswith("doc:"):
                    document_ids.add(source_id)
            if not document_ids:
                continue
            quote = ""
            for ev in evidence:
                if ev.get("quote"):
                    quote = str(ev["quote"])
                    break
            pages.append(
                {
                    "id": front.get("id"),
                    "type": front.get("type"),
                    "title": front.get("title") or "",
                    "summary": front.get("summary") or "",
                    "statement": front.get("statement") or "",
                    "metric": front.get("metric") or {},
                    "document_ids": document_ids,
                    "documents": sorted(
                        {
                            (by_id.get(doc_id) or by_source.get(f"source:{doc_id}"))
                            .filename
                            if (by_id.get(doc_id) or by_source.get(f"source:{doc_id}"))
                            else doc_id
                            for doc_id in document_ids
                        }
                    ),
                    "quote": quote,
                }
            )

    conflicts: list[dict] = []
    metric_groups: dict[str, list[dict]] = {}
    claim_groups: dict[str, list[dict]] = {}
    for page in pages:
        if page["type"] == "metric":
            key = (page.get("metric") or {}).get("key") or _normalize(page["title"])
            metric_groups.setdefault(str(key), []).append(page)
        elif page["type"] == "claim":
            claim_groups.setdefault(_normalize(page["title"]), []).append(page)

    for key, group in metric_groups.items():
        doc_ids = {doc for page in group for doc in page["document_ids"]}
        values = {
            str((page.get("metric") or {}).get("value") or "").strip()
            for page in group
        }
        values.discard("")
        if len(doc_ids) < 2 or len(values) < 2:
            continue
        conflicts.append(
            {
                "id": _conflict_id("metric", key),
                "type": "metric_value",
                "severity": "high",
                "topic": group[0]["title"] or key,
                "message": "同一指标在多份材料中数值不一致",
                "values": [
                    {
                        "document": page["documents"][0] if page["documents"] else "",
                        "value": (page.get("metric") or {}).get("value"),
                        "quote": page["quote"],
                    }
                    for page in group
                ],
            }
        )

    for key, group in claim_groups.items():
        doc_ids = {doc for page in group for doc in page["document_ids"]}
        statements = {page["statement"] or page["summary"] for page in group}
        statements.discard("")
        if len(doc_ids) < 2 or len(statements) < 2:
            continue
        numbers = {frozenset(_numbers(item)) for item in statements}
        high = len(numbers) > 1
        conflicts.append(
            {
                "id": _conflict_id("claim", key),
                "type": "claim_statement",
                "severity": "high" if high else "medium",
                "topic": group[0]["title"] or key,
                "message": (
                    "同一结论在多份材料中的数字不一致"
                    if high
                    else "同一结论在多份材料中的表述不一致"
                ),
                "values": [
                    {
                        "document": page["documents"][0] if page["documents"] else "",
                        "value": page["statement"] or page["summary"],
                        "quote": page["quote"],
                    }
                    for page in group
                ],
            }
        )

    conflicts.sort(key=lambda item: (item["severity"] != "high", item["topic"]))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document_count": len(documents),
        "high": sum(1 for item in conflicts if item["severity"] == "high"),
        "medium": sum(1 for item in conflicts if item["severity"] == "medium"),
        "conflicts": conflicts[:50],
    }
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "consistency.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
