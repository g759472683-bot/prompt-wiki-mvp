from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm.client import LLMClient, LLMError
from ..models import Block, Document, User
from .compiler import _extract_json
from .quote import find_quote

ASK_SYSTEM_PROMPT = """你是现场提词器。根据给定的原文块回答用户的问题。

只输出 JSON，不要解释，不要 Markdown 代码块。

硬规则：
1. 只能使用给定原文块；不得引入块外事实、数字或评价。
2. 每个数字/关键断言必须有 citation，quote 必须逐字来自对应块。
3. l1：3-5 个关键词，每个不超过 12 字。
4. l2：3-5 条骨架，每条不超过 28 字，第一条是能直接开口的句子。
5. fallback 不超过 100 字，必须诚实；不知道就说不知道。
6. answer 不超过 600 字，用第一人称，像在面试/路演现场说话。
7. 如果原文块不足以回答，answer 写“资料不足，建议按兜底说”，citations 为空。

JSON 形状：
{
  "answer": "可开口的回答",
  "l1": ["关键词 1", "关键词 2", "关键词 3"],
  "l2": ["开口句", "论据 1", "论据 2"],
  "fallback": "兜底话术",
  "citations": [{"block": "b-0001", "quote": "逐字原文"}]
}
"""

UNGROUNDED_SYSTEM_PROMPT = """你是现场提词器。当前没有可用的原文依据，但用户允许你用通用知识回答。

只输出 JSON，不要解释，不要 Markdown 代码块。

硬规则：
1. 明确这是无原文依据的通用回答；不要编造具体项目、客户、数字、时间、奖项。
2. l1：3-5 个关键词，每个不超过 12 字。
3. l2：3-5 条骨架，每条不超过 28 字，第一条能直接开口。
4. fallback 不超过 100 字，必须提示“这条没有原文依据，先核对”。
5. answer 不超过 300 字，用第一人称，保守、可被追问。
6. 不要输出 citations；不要假装有出处。

JSON 形状：
{
  "answer": "保守的通用回答",
  "l1": ["关键词 1", "关键词 2", "关键词 3"],
  "l2": ["开口句", "论据 1", "论据 2"],
  "fallback": "这条没有原文依据，先按通用理解说，具体口径要核对"
}
"""


@dataclass
class Retrieved:
    block_id: str
    text: str
    page: int
    source_id: str
    label: str


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", text.lower())


def _bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text}
    return {text[i : i + 2] for i in range(len(text) - 1)}


def retrieve_blocks(session: Session, user: User, question: str, limit: int = 4) -> list[Retrieved]:
    rows = session.execute(
        select(Block, Document)
        .join(Document, Block.document_id == Document.id)
        .where(Document.user_id == user.id, Document.status != "deleted")
    ).all()
    if not rows:
        return []
    query = _normalize(question)
    qgrams = _bigrams(query)
    scored: list[tuple[float, Retrieved]] = []
    for block, document in rows:
        text = _normalize(block.text)
        if not text:
            continue
        if query and query in text:
            score = 1.0
        else:
            grams = _bigrams(text)
            overlap = len(qgrams & grams)
            score = 2.0 * overlap / max(1, len(qgrams) + len(grams))
        if score <= 0:
            continue
        scored.append(
            (
                score,
                Retrieved(
                    block_id=block.block_id,
                    text=block.text,
                    page=block.page,
                    source_id=document.source_id or f"source:{document.id}",
                    label=document.filename,
                ),
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def _prompt(question: str, blocks: list[Retrieved]) -> str:
    payload = [
        {
            "block": block.block_id,
            "page": block.page,
            "file": block.label,
            "text": block.text,
        }
        for block in blocks
    ]
    return (
        "问题："
        + question
        + "\n原文块：\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n请只基于这些块生成提词卡。"
    )


def _fallback_card(question: str) -> dict:
    return {
        "l1": ["没准备", "不编造", "先兜底"],
        "l2": [
            "这个我确实没有准备，先按兜底说。",
            "具体细节我确认后回复，不在这里编。",
            "如果有确定的部分，我只说确定的部分。",
        ],
        "l3": "这个我没有准备，不想现编。我可以按已知的部分回答，具体细节确认后回复。",
        "fallback": "这个我没有准备，不想现编；我确认后回复你。",
        "confidence": {"level": "red", "reasons": ["no_evidence", "degraded"]},
        "citations": [],
        "do_not_say": ["零故障", "行业第一"],
        "must_show_fallback_first": True,
    }


def _auto_anchor(question: str, blocks: list[Retrieved]) -> dict | None:
    if not blocks:
        return None
    top = blocks[0]
    query = _normalize(question)
    qgrams = _bigrams(query)
    pieces = [p.strip() for p in re.split(r"(?<=[。！？；\n])", top.text) if p.strip()]
    best = ""
    best_score = -1.0
    for piece in pieces:
        if not (8 <= len(piece) <= 120):
            continue
        grams = _bigrams(_normalize(piece))
        score = 2.0 * len(qgrams & grams) / max(1, len(qgrams) + len(grams))
        if score > best_score:
            best_score = score
            best = piece
    if not best:
        best = top.text[:120].strip()
    if not best:
        return None
    return {
        "source": top.source_id,
        "source_version": 1,
        "block": top.block_id,
        "quote": best,
        "page_label": f"{top.label} · p.{top.page}",
        "supports": [],
    }


def _validate_card(raw: dict, blocks: list[Retrieved], question: str = "") -> dict:
    by_id = {block.block_id: block for block in blocks}
    l1 = [str(x) for x in (raw.get("l1") or []) if 2 <= len(str(x)) <= 12][:5]
    l2 = [str(x) for x in (raw.get("l2") or []) if 2 <= len(str(x)) <= 28][:5]
    fallback = str(raw.get("fallback") or "").strip()
    answer = str(raw.get("answer") or "").strip()
    if len(l1) < 3 or len(l2) < 3 or not fallback or len(fallback) > 100 or not answer:
        raise ValueError("卡片字段不合规")
    if len(l2) < 3:
        raise ValueError("L2 不足")

    citations: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in (raw.get("citations") or [])[:4]:
        if not isinstance(item, dict):
            continue
        block = by_id.get(str(item.get("block") or ""))
        if block is None:
            continue
        match_type, start, end = find_quote(block.text, str(item.get("quote") or ""))
        if match_type is None:
            continue
        quote = block.text[start:end].strip()
        key = (block.block_id, quote)
        if key in seen or len(quote) < 5 or len(quote) > 200:
            continue
        seen.add(key)
        citations.append(
            {
                "source": block.source_id,
                "source_version": 1,
                "block": block.block_id,
                "quote": quote,
                "page_label": f"{block.label} · p.{block.page}",
                "supports": [],
            }
        )
    auto_anchored = False
    if not citations and "资料不足" not in answer:
        anchor = _auto_anchor(question, blocks)
        if anchor is not None:
            citations = [anchor]
            auto_anchored = True
    reasons = ["bm25_recall", "degraded"] if citations else ["no_evidence", "degraded"]
    if auto_anchored:
        reasons.append("auto_anchor")
    return {
        "l1": l1,
        "l2": l2,
        "l3": answer[:600],
        "fallback": fallback,
        "confidence": {
            "level": "yellow" if citations else "red",
            "reasons": reasons,
        },
        "citations": citations,
        "do_not_say": ["零故障", "行业第一"],
        "must_show_fallback_first": not citations,
    }


def _validate_ungrounded(raw: dict) -> dict:
    l1 = [str(x) for x in (raw.get("l1") or []) if 2 <= len(str(x)) <= 12][:5]
    l2 = [str(x) for x in (raw.get("l2") or []) if 2 <= len(str(x)) <= 28][:5]
    fallback = str(raw.get("fallback") or "").strip()
    answer = str(raw.get("answer") or "").strip()
    if len(l1) < 3 or len(l2) < 3 or not fallback or len(fallback) > 100 or not answer:
        raise ValueError("无依据卡片字段不合规")
    return {
        "l1": l1,
        "l2": l2,
        "l3": answer[:300],
        "fallback": fallback,
        "confidence": {
            "level": "red",
            "score": 30,
            "reasons": ["ungrounded", "degraded"],
        },
        "citations": [],
        "do_not_say": ["具体数字", "具体客户", "保证"],
        "must_show_fallback_first": False,
    }


def ask_question(
    llm: LLMClient | None,
    session: Session,
    user: User,
    question: str,
    allow_ungrounded: bool = False,
) -> dict:
    started = time.perf_counter()
    blocks = retrieve_blocks(session, user, question)
    if not blocks and allow_ungrounded and llm is not None:
        try:
            result = llm.chat_json(
                UNGROUNDED_SYSTEM_PROMPT,
                "问题：" + question + "\n请生成无原文依据的保守回答。",
            )
            raw = _extract_json(result.content)
            card = _validate_ungrounded(raw)
            return {
                "matched": False,
                "hit_path": "ungrounded",
                "question": question,
                "degraded": True,
                "ungrounded": True,
                "card": card,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "model": result.model,
                "notices": ["没有原文依据；这是 LLM 通用回答，已标红"],
            }
        except (LLMError, ValueError, json.JSONDecodeError):
            return {
                "matched": False,
                "hit_path": "none",
                "question": question,
                "degraded": True,
                "ungrounded": False,
                "card": _fallback_card(question),
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "model": "",
                "notices": ["无依据回答失败，已退回兜底卡"],
            }

    if not blocks or llm is None:
        return {
            "matched": False,
            "hit_path": "none" if not blocks else "bm25",
            "question": question,
            "degraded": True,
            "ungrounded": False,
            "card": _fallback_card(question),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": "",
            "notices": ["没有召回可用原文块"] if not blocks else ["LLM 未配置"],
        }

    try:
        result = llm.chat_json(ASK_SYSTEM_PROMPT, _prompt(question, blocks))
        raw = _extract_json(result.content)
        card = _validate_card(raw, blocks, question)
        return {
            "matched": False,
            "hit_path": "bm25",
            "question": question,
            "degraded": True,
            "ungrounded": False,
            "card": card,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": result.model,
            "notices": ["未命中预编译卡片，已用原文块现场组装"],
        }
    except (LLMError, ValueError, json.JSONDecodeError):
        return {
            "matched": False,
            "hit_path": "bm25",
            "question": question,
            "degraded": True,
            "ungrounded": False,
            "card": _fallback_card(question),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": "",
            "notices": ["现场组装失败，已退回兜底卡"],
        }
