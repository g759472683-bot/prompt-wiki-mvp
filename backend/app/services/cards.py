from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from ..config import Settings
from ..llm.client import LLMClient, LLMError, LLMResult
from .compiler import SourceDoc, _extract_json, _iso
from .quote import find_quote

CARD_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NUM_RE = re.compile(r"(?<![A-Za-z0-9])(\d+(?:\.\d+)?)")
INTENTS = {
    "factual", "behavioral", "technical", "motivation", "risk",
    "commercial", "hr", "other",
}

CARD_SYSTEM_PROMPT = """你是提词卡编译器。根据已编译的 claim/metric 页面，预测用户会被问到的问题，为每个问题生成一张可展开的论证卡。

只输出 JSON，不要解释，不要 Markdown 代码块。

硬规则：
1. 生成 10-15 张卡，按“最可能被问”的顺序排列。
2. 只能使用给定页面里的信息；不得引入页面外的事实、数字或架构。
3. L1：3-5 个关键词/短语，每个不超过 12 字。
4. L2：3-5 条摘要，每条不超过 28 字，第一条必须是能直接开口的句子。
5. 每个 L2 对应一个 point：summary 与 L2 同序同义；detail 80-180 字，按“结论 → 机制/架构/流程 → 证据 → 取舍/边界”展开，不能只复述摘要；资料不足就写边界，不要编。
6. 每个 point 给 2-3 个 followups：question 像面试官追问，answer 不超过 80 字，必须能落回同一组证据。
7. L1/L2/point.detail/followups/fallback 里出现的每个数字，必须能在 point.evidence_refs 指向页面的 quote 中找到。
8. evidence_refs 只能引用给定页面 id（claim: 或 metric:），1-4 个。
9. fallback 不超过 100 字，必须诚实：先限定，再给一个你确定的事实；不要复述 L2。
10. 不写“零故障”“行业第一”“保证”等绝对化表述。
11. do_not_say 只放实际禁说的短语；没有就 []。
12. 不要写 Wiki/知识库/页面这类词；用户只看到卡。

JSON 形状：
{
  "cards": [
    {
      "slug": "lowercase-kebab",
      "question": "问题，不超过 40 字",
      "variants": ["口语问法 1", "口语问法 2"],
      "intent": "behavioral|technical|factual|motivation|risk|commercial|hr|other",
      "target_sec": 60,
      "l1": ["关键词 1", "关键词 2", "关键词 3"],
      "l2": ["开口句", "论据 1", "论据 2"],
      "points": [
        {
          "summary": "与 L2 第一条同义",
          "detail": "结论 → 机制/架构/流程 → 证据 → 取舍或边界，80-180 字",
          "evidence_refs": ["claim:xxx"],
          "followups": [
            {"question": "如果被追问……", "answer": "不超过 80 字的回答"}
          ]
        }
      ],
      "fallback": "兜底话术",
      "evidence_refs": ["claim:xxx", "metric:yyy"],
      "do_not_say": ["绝对化表述"]
    }
  ]
}
"""


class FollowupDraft(BaseModel):
    question: str
    answer: str = ""


class PointDraft(BaseModel):
    summary: str
    detail: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    followups: list[FollowupDraft] = Field(default_factory=list)


class CardDraft(BaseModel):
    slug: str
    question: str
    variants: list[str] = Field(default_factory=list)
    intent: str = "behavioral"
    target_sec: int = 60
    l1: list[str]
    l2: list[str]
    points: list[PointDraft] = Field(default_factory=list)
    fallback: str
    evidence_refs: list[str]
    do_not_say: list[str] = Field(default_factory=list)


@dataclass
class CompiledCard:
    id: str
    question: str
    confidence: str
    evidence_count: int
    path: str
    body: str


@dataclass
class CardResult:
    cards: list[CompiledCard] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    pack_path: str = ""


def _clip(text: str, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _scenario_kinds(doc_type: str) -> list[str]:
    if doc_type in {"resume", "jd"}:
        return ["interview"]
    if doc_type in {"project", "notes"}:
        return ["meeting", "interview"]
    return ["interview", "meeting"]


def load_staged_pages(wiki_dir: Path, run_id: str) -> list[dict]:
    pages: list[dict] = []
    for page_type in ("claim", "metric"):
        directory = wiki_dir / ".staging" / run_id / "pages" / page_type
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---\n"):
                continue
            front = yaml.safe_load(text.split("---", 2)[1])
            if not isinstance(front, dict) or not front.get("id"):
                continue
            page = {
                "id": front["id"],
                "type": front.get("type", page_type),
                "title": front.get("title", ""),
                "summary": front.get("summary", ""),
                "evidence": front.get("evidence", []),
            }
            if page_type == "claim":
                page["statement"] = front.get("statement", "")
            else:
                page["value"] = (front.get("metric") or {}).get("value", "")
            pages.append(page)
    return pages


def _build_card_prompt(doc: SourceDoc, pages: list[dict]) -> str:
    compact = []
    for page in pages:
        item = {
            "id": page["id"],
            "type": page["type"],
            "title": page["title"],
            "summary": page["summary"],
            "evidence": [
                {"block": ev.get("block"), "quote": ev.get("quote")}
                for ev in page.get("evidence", [])
            ],
        }
        if page["type"] == "claim":
            item["statement"] = page.get("statement", "")
        else:
            item["value"] = page.get("value", "")
        compact.append(item)
    return (
        "文档类型："
        + doc.doc_type
        + "\n已编译页面：\n"
        + json.dumps(compact, ensure_ascii=False)
        + "\n\n请生成 10-15 张提词卡。"
    )


def _numeric_untraced(texts: list[str], quotes: list[str]) -> list[str]:
    haystack = " ".join(quotes)
    bad = []
    for text in texts:
        for number in NUM_RE.findall(text):
            if number not in haystack:
                bad.append(number)
    return sorted(set(bad))


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _fallback_l1(l2: list[str]) -> list[str]:
    """Derive short keywords when the model ignores the L1 length limit."""
    out: list[str] = []
    for line in l2:
        for part in re.split(r"[，。；、：,;]", line):
            part = part.strip(" -")
            if 2 <= len(part) <= 12:
                out.append(part)
    text = " ".join(l2)
    for match in re.finditer(
        r"\d+(?:\.\d+)?\s*(?:%|亿元|亿|万元|万|人|个|分钟|秒|ms)?", text
    ):
        token = match.group(0).strip()
        if 2 <= len(token) <= 12:
            out.append(token)
    return _dedupe(out)


def _fit_l2(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) <= 28:
            out.append(line)
            continue
        for part in re.split(r"[，；]", line):
            part = part.strip("，； ")
            if 2 <= len(part) <= 28:
                out.append(part)
    return _dedupe(out)[:5]


def _citations_for_refs(refs: list[str], pages_by_id: dict[str, dict]) -> list[dict]:
    citations: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        page = pages_by_id.get(ref) or {}
        for ev in page.get("evidence", []):
            quote = str(ev.get("quote") or "")
            block = str(ev.get("block") or "")
            if not quote or (block, quote) in seen:
                continue
            seen.add((block, quote))
            citations.append(
                {
                    "source": ev.get("source"),
                    "source_version": ev.get("source_version", 1),
                    "block": block,
                    "quote": quote,
                    "page_label": page.get("title") or block,
                }
            )
    return citations


def _point_confidence(refs: list[str], pages_by_id: dict[str, dict]) -> dict:
    blocks = {
        str(ev.get("block"))
        for ref in refs
        for ev in (pages_by_id.get(ref) or {}).get("evidence", [])
        if ev.get("block")
    }
    count = len(blocks)
    if count >= 2:
        return {
            "level": "green",
            "score": 85,
            "reasons": ["multiple_evidence"],
        }
    if count == 1:
        return {
            "level": "yellow",
            "score": 60,
            "reasons": ["single_evidence"],
        }
    return {"level": "red", "score": 30, "reasons": ["no_evidence"]}


def _build_points(
    draft_points: list[PointDraft],
    l2: list[str],
    refs: list[str],
    pages_by_id: dict[str, dict],
) -> list[dict]:
    points: list[dict] = []
    for index, line in enumerate(l2):
        draft = draft_points[index] if index < len(draft_points) else None
        point_refs = [
            ref for ref in (draft.evidence_refs if draft else []) if ref in refs
        ]
        if not point_refs:
            point_refs = list(refs)
        quotes = [
            str(ev.get("quote") or "")
            for ref in point_refs
            for ev in (pages_by_id.get(ref) or {}).get("evidence", [])
        ]
        detail = _clip(draft.detail if draft else "", 180)
        if len(detail) < 20:
            detail = line
        if _numeric_untraced([detail], quotes):
            detail = line

        followups: list[dict] = []
        for item in (draft.followups if draft else [])[:3]:
            question = _clip(item.question, 40)
            answer = _clip(item.answer, 80)
            if len(question) < 4 or len(answer) < 5:
                continue
            if _numeric_untraced([answer], quotes):
                continue
            followups.append({"question": question, "answer": answer})
        points.append(
            {
                "index": index + 1,
                "summary": line,
                "detail": detail,
                "followups": followups,
                "confidence": _point_confidence(point_refs, pages_by_id),
                "citations": _citations_for_refs(point_refs, pages_by_id),
            }
        )
    return points


def _validate_card(
    draft: CardDraft,
    pages_by_id: dict[str, dict],
    seen_slugs: set[str],
    index: int,
) -> tuple[dict | None, str | None]:
    question = _clip(draft.question, 40)
    if len(question) < 4:
        return None, "问题过短"
    l1 = [str(item) for item in draft.l1 if len(str(item)) <= 12][:5]
    l2 = _fit_l2([str(item) for item in draft.l2])
    if len(l2) < 3:
        return None, "L2 有效条目不足"
    if len(l1) < 3:
        l1 = _dedupe(l1 + _fallback_l1(l2))[:5]
    if len(l1) < 3:
        return None, "L1 有效条目不足"
    if not draft.fallback.strip() or len(draft.fallback) > 100:
        return None, "兜底超限"

    refs = [ref for ref in draft.evidence_refs if ref in pages_by_id]
    if not refs or len(refs) > 4:
        return None, "evidence_refs 无效"
    refs = list(dict.fromkeys(refs))

    quotes = []
    for ref in refs:
        for ev in pages_by_id[ref].get("evidence", []):
            quote = ev.get("quote", "")
            if quote:
                quotes.append(quote)
    if _numeric_untraced(l1 + l2 + [draft.fallback], quotes):
        return None, "数字无法追溯"

    banned = [phrase for phrase in draft.do_not_say if phrase]
    haystack = " ".join(l1 + l2 + [draft.fallback])
    if any(phrase in haystack for phrase in banned):
        return None, "出现禁用表述"

    slug = draft.slug.lower()
    if not CARD_SLUG_RE.match(slug) or len(slug) > 48:
        slug = f"qa-{index:02d}"
    base = slug
    suffix = 2
    while slug in seen_slugs:
        slug = f"{base}-{suffix}"
        suffix += 1
    seen_slugs.add(slug)

    variants = [v.strip() for v in draft.variants if 3 <= len(v.strip()) <= 60]
    if question not in variants:
        variants.insert(0, question)
    if len(variants) < 2:
        variants.append("能展开说说吗")
    variants = list(dict.fromkeys(variants))[:6]

    intent = draft.intent if draft.intent in INTENTS else "behavioral"
    target = draft.target_sec if draft.target_sec in {30, 60, 90} else 60
    do_not_say = [
        p for p in draft.do_not_say
        if 2 <= len(p) <= 20 and p not in {"绝对化表述", "绝对化表述。", "无"}
    ][:5]

    return (
        {
            "slug": slug,
            "question": question,
            "variants": variants,
            "intent": intent,
            "target_sec": target,
            "l1": l1,
            "l2": l2,
            "points": _build_points(draft.points, l2, refs, pages_by_id),
            "fallback": _clip(draft.fallback, 100),
            "evidence_refs": refs,
            "do_not_say": do_not_say,
            "confidence": _point_confidence(refs, pages_by_id),
        },
        None,
    )


def _frontmatter_card(
    data: dict,
    doc: SourceDoc,
    run_id: str,
    now: datetime,
) -> dict:
    refs = data["evidence_refs"]
    level = data["confidence"]["level"]
    return {
        "schema_version": "1.0",
        "id": f"qa:{data['slug']}",
        "type": "qa",
        "title": data["question"],
        "summary": _clip(data["l2"][0], 80),
        "status": "draft",
        "language": "zh-CN",
        "revision": 1,
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "created_by": "compiler",
        "run_id": run_id,
        "question": data["question"],
        "question_variants": data["variants"],
        "intent": data["intent"],
        "scenario_kinds": _scenario_kinds(doc.doc_type),
        "answer": {"target_sec": data["target_sec"], "tone": "honest"},
        "tags": [doc.doc_type] if doc.doc_type != "other" else [],
        "confidence": {
            "level": level,
            "reasons": data["confidence"]["reasons"],
            "rule": "rule_v1",
            "computed_at": _iso(now),
        },
        "evidence_refs": list(refs),
        "conflicts": [],
        "conflict_state": "none",
        "card": {
            "l1": data["l1"],
            "l2": data["l2"],
            "fallback": data["fallback"],
            "evidence_refs": list(refs),
            "confidence": {
                "level": level,
                "reasons": data["confidence"]["reasons"],
                "rule": "rule_v1",
                "computed_at": _iso(now),
            },
            "built_from": [{"id": ref, "revision": 1} for ref in refs],
            "do_not_say": data["do_not_say"],
        },
    }


def _render_qa(
    data: dict,
    front: dict,
    pages_by_id: dict[str, dict],
) -> tuple[str, list[dict]]:
    citations: list[dict] = []
    seen: set[tuple[str, str]] = set()
    evidence_lines = []
    for ref in data["evidence_refs"]:
        page = pages_by_id[ref]
        for ev in page.get("evidence", []):
            key = (str(ev.get("block")), str(ev.get("quote")))
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "source": ev.get("source"),
                    "source_version": ev.get("source_version", 1),
                    "block": ev.get("block"),
                    "quote": ev.get("quote"),
                    "page_label": page["title"],
                }
            )
            evidence_lines.append(
                f"- E{len(citations)} · [[{ref}]] · [[{ev.get('source')}]] · "
                f"{ev.get('block')}：「{ev.get('quote')}」"
            )

    body = [
        f"# {data['question']}",
        "",
        "## 一句话回答",
        "",
        data["l2"][0],
        "",
        "## 展开",
        "",
        "\n".join(f"- {line}" for line in data["l2"]),
        "",
        "## 逐条展开",
        "",
    ]
    for point in data.get("points", []):
        body.extend(
            [
                f"### {point['index']}. {point['summary']}",
                "",
                point["detail"],
                "",
            ]
        )
        if point.get("followups"):
            body.append("追问预案：")
            body.append("")
            for followup in point["followups"]:
                body.append(
                    f"- Q：{followup['question']}  \n  A：{followup['answer']}"
                )
            body.append("")
    body.extend(
        [
            "## 证据",
            "",
            "\n".join(evidence_lines) if evidence_lines else "- 暂无",
            "",
            "## 边界与不知道",
            "",
            data["fallback"],
            "",
        ]
    )
    if data["do_not_say"]:
        body.extend(
            [
                "不要这样说：",
                "",
                "\n".join(f"- {phrase}" for phrase in data["do_not_say"]),
                "",
            ]
        )
    body.extend(
        [
            "## 追问预案",
            "",
            "\n".join(f"- 可能被追问：{variant}" for variant in data["variants"][1:])
            or "- 暂无",
            "",
        ]
    )
    yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=1000)
    markdown = f"---\n{yaml_text}---\n\n" + "\n".join(body).rstrip() + "\n"
    return markdown, citations


def compile_cards(
    llm: LLMClient,
    settings: Settings,
    user_id: str,
    doc: SourceDoc,
    run_id: str,
    now: datetime | None = None,
) -> CardResult:
    now = now or datetime.now(timezone.utc)
    wiki_dir = settings.data_dir / "users" / user_id / "wiki"
    pages = load_staged_pages(wiki_dir, run_id)
    if not pages:
        raise LLMError("没有可用的 claim/metric 页面，无法生成卡片")

    llm_result: LLMResult = llm.chat_json(
        CARD_SYSTEM_PROMPT,
        _build_card_prompt(doc, pages),
    )
    result = CardResult(
        prompt_tokens=llm_result.prompt_tokens,
        completion_tokens=llm_result.completion_tokens,
        latency_ms=llm_result.latency_ms,
    )
    try:
        raw = _extract_json(llm_result.content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise LLMError(f"卡片 JSON 解析失败：{exc}") from exc

    raw_cards = raw.get("cards")
    if not isinstance(raw_cards, list):
        raise LLMError("LLM 输出缺少 cards 数组")
    if len(raw_cards) > 20:
        raw_cards = raw_cards[:20]
        result.warnings.append("LLM 返回超过 20 张卡，只处理前 20 张")

    pages_by_id = {page["id"]: page for page in pages}
    seen_slugs: set[str] = set()
    pack_cards: list[dict] = []
    for index, item in enumerate(raw_cards, start=1):
        if not isinstance(item, dict):
            continue
        item.setdefault("slug", f"qa-{index:02d}")
        try:
            draft = CardDraft.model_validate(item)
        except Exception as exc:
            result.warnings.append(f"跳过非法卡片：{str(exc)[:100]}")
            continue
        data, error = _validate_card(draft, pages_by_id, seen_slugs, index)
        if error or data is None:
            result.warnings.append(f"跳过卡片 {draft.slug}：{error}")
            continue

        front = _frontmatter_card(data, doc, run_id, now)
        markdown, citations = _render_qa(data, front, pages_by_id)
        relative = (
            Path(".staging") / run_id / "pages" / "qa" / f"{data['slug']}.md"
        )
        target = wiki_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        body = markdown.split("---", 2)[2].lstrip()
        result.cards.append(
            CompiledCard(
                id=f"qa:{data['slug']}",
                question=data["question"],
                confidence=data["confidence"]["level"],
                evidence_count=len(citations),
                path=str(relative).replace("\\", "/"),
                body=body,
            )
        )
        pack_cards.append(
            {
                "qa_id": f"qa:{data['slug']}",
                "question": data["question"],
                "variants": data["variants"],
                "l1": data["l1"],
                "l2": data["l2"],
                "points": data["points"],
                "l3_markdown": body,
                "fallback": data["fallback"],
                "confidence": data["confidence"],
                "citations": citations,
                "do_not_say": data["do_not_say"],
                "evidence_refs": data["evidence_refs"],
            }
        )

    pack = {
        "schema_version": "1.0",
        "pack_id": f"pack-{run_id.removeprefix('run-')}",
        "document_id": doc.id,
        "run_id": run_id,
        "version": 1,
        "approved": False,
        "cards": pack_cards,
    }
    pack_path = wiki_dir / ".staging" / run_id / "pack.json"
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    result.pack_path = str(pack_path.relative_to(wiki_dir)).replace("\\", "/")
    return result
