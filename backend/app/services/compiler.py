from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from ..config import Settings
from ..llm.client import LLMClient, LLMError, LLMResult
from .quote import find_quote

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CLAIM_KINDS = {
    "experience", "capability", "technical", "commercial", "customer", "market",
}

SYSTEM_PROMPT = """你是个人知识库编译器。把给定的简历/项目材料编译成可审计的 claim 与 metric 页面。

只输出 JSON，不要解释，不要 Markdown 代码块。

硬规则：
1. 只能使用给定 blocks；evidence.quote 必须逐字来自 block.text 的连续片段（允许跨行）。
2. 每个页面 1-3 条 evidence；页面中的数字必须出现在 quote 里。
3. claim 是一条可判真假的断言，不超过 60 字，只讲一个断言，且必须包含“我的动作”或“可验证结果”；只描述事件本身不算 claim。
4. metric 只在原文明确给出数字时创建；method 只写原文明确的计算口径，没写就写“原文未说明”，不要编造。同一句里的多个数字不要拆成多个 metric。
5. 不写营销词、绝对化表述（如“零故障”“行业第一”“保证”）。
6. 输出 3-6 个页面（claim 2-4 个，metric 0-2 个）；证据不足就少写，不要为了凑数编造。
7. sections 必须使用给定标题，值为字符串或字符串数组。
8. 不要生成 story/qa/entity 页面。

JSON 形状：
{
  "pages": [
    {
      "type": "claim",
      "slug": "lowercase-kebab-slug",
      "title": "短标题",
      "summary": "一句话摘要",
      "statement": "一句可判真假的陈述",
      "claim_kind": "experience|capability|technical|commercial|customer|market",
      "scope": "适用边界，以及不适用于什么",
      "evidence": [{"block": "b-0001", "quote": "原文片段"}],
      "sections": {"一句话说法": "...", "成立条件": ["..."], "可能的反驳": ["..."]}
    },
    {
      "type": "metric",
      "slug": "lowercase-kebab-slug",
      "title": "指标名",
      "summary": "值 + 口径",
      "value": "99.95%",
      "value_num": 99.95,
      "unit": "%",
      "direction": "higher|lower",
      "period": "2025",
      "method": "怎么算的",
      "scope": "统计范围",
      "evidence": [{"block": "b-0002", "quote": "原文片段"}],
      "sections": {"口径": "...", "计算方式": "...", "为什么可信": "...", "常见追问": ["..."]}
    }
  ]
}
"""


@dataclass
class SourceDoc:
    id: str
    source_id: str
    filename: str
    doc_type: str
    created_at: datetime


@dataclass
class SourceBlock:
    block_id: str
    page: int
    text: str


class EvidenceDraft(BaseModel):
    block: str
    quote: str = Field(min_length=2, max_length=300)


class ClaimDraft(BaseModel):
    type: Literal["claim"]
    slug: str
    title: str
    summary: str
    statement: str
    claim_kind: str = "experience"
    scope: str
    evidence: list[EvidenceDraft]
    sections: dict[str, Any] = Field(default_factory=dict)


class MetricDraft(BaseModel):
    type: Literal["metric"]
    slug: str
    title: str
    summary: str
    value: str
    value_num: float
    unit: str
    direction: str = "higher"
    period: str
    method: str
    scope: str
    evidence: list[EvidenceDraft]
    sections: dict[str, Any] = Field(default_factory=dict)


@dataclass
class CompiledPage:
    id: str
    type: str
    title: str
    path: str
    confidence: str
    evidence_count: int


@dataclass
class CompileResult:
    run_id: str
    pages: list[CompiledPage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    model: str = ""


def _clip(text: str, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def next_run_id(settings: Settings, user_id: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    runs_dir = settings.data_dir / "users" / user_id / "wiki" / "runs"
    prefix = f"run-{now:%Y%m%d}-"
    seq = 1
    if runs_dir.exists():
        numbers = []
        for child in runs_dir.iterdir():
            if child.is_dir() and child.name.startswith(prefix):
                suffix = child.name.removeprefix(prefix)
                if suffix.isdigit():
                    numbers.append(int(suffix))
        seq = max(numbers, default=0) + 1
    if seq > 99:
        raise LLMError("当天 run 数量超过 99，无法分配 run_id")
    return f"{prefix}{seq:02d}"


def build_prompt(doc: SourceDoc, blocks: list[SourceBlock]) -> str:
    payload_blocks = [{"block": b.block_id, "page": b.page, "text": b.text} for b in blocks]
    return (
        "文档信息：\n"
        + json.dumps(
            {
                "filename": doc.filename,
                "doc_type": doc.doc_type,
                "blocks": payload_blocks,
            },
            ensure_ascii=False,
        )
        + "\n\n请按系统规则编译页面。"
    )


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM 输出里没有 JSON 对象")
    return json.loads(text[start : end + 1])


def _validate_evidence(
    items: list[EvidenceDraft],
    blocks_by_id: dict[str, SourceBlock],
) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for item in items:
        block = blocks_by_id.get(item.block)
        if block is None:
            continue
        match_type, start, end = find_quote(block.text, item.quote)
        if match_type is None:
            continue
        quote = block.text[start:end].strip()
        if len(quote) < 5 or len(quote) > 200 or quote in seen:
            continue
        seen.add(quote)
        out.append(
            {
                "source": "",  # filled by caller
                "source_version": 1,
                "block": block.block_id,
                "quote": quote,
                "role": "primary" if not out else "supporting",
                "verified": True,
            }
        )
    return out


def _render_section(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(f"- {_clip(str(item), 300)}" for item in value if str(item).strip())
    return _clip(str(value), 1200)


def _evidence_lines(doc: SourceDoc, evidence: list[dict]) -> str:
    lines = []
    for index, ev in enumerate(evidence, start=1):
        lines.append(
            f"- E{index} · [[{doc.source_id}]] · {ev['block']}：「{ev['quote']}」"
        )
    return "\n".join(lines)


def _common_frontmatter(
    *,
    page_id: str,
    page_type: str,
    title: str,
    summary: str,
    doc: SourceDoc,
    run_id: str,
    now: datetime,
    evidence: list[dict],
) -> dict:
    return {
        "schema_version": "1.0",
        "id": page_id,
        "type": page_type,
        "title": title,
        "summary": summary,
        "status": "draft",
        "language": "zh-CN",
        "revision": 1,
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "created_by": "compiler",
        "run_id": run_id,
        "tags": [doc.doc_type] if doc.doc_type and doc.doc_type != "other" else [],
        "confidence": {
            "level": "yellow",
            "reasons": ["single_source", "unreviewed"],
            "rule": "rule_v1",
            "computed_at": _iso(now),
        },
        "evidence": evidence,
        "conflicts": [],
        "conflict_state": "none",
    }


def render_claim_page(
    draft: ClaimDraft,
    doc: SourceDoc,
    run_id: str,
    evidence: list[dict],
    now: datetime,
) -> str:
    title = _clip(draft.title, 40)
    summary = _clip(draft.summary, 80) or title
    statement = _clip(draft.statement, 60)
    front = _common_frontmatter(
        page_id=f"claim:{draft.slug}",
        page_type="claim",
        title=title,
        summary=summary,
        doc=doc,
        run_id=run_id,
        now=now,
        evidence=evidence,
    )
    front.update(
        {
            "statement": statement,
            "claim_kind": draft.claim_kind,
            "scope": _clip(draft.scope, 200),
            "verification": "verified",
        }
    )
    sections = draft.sections
    body = [
        f"# {title}",
        "",
        "## 一句话说法",
        "",
        _render_section(sections.get("一句话说法") or summary),
        "",
        "## 成立条件",
        "",
        _render_section(sections.get("成立条件")),
        "",
        "## 证据",
        "",
        _evidence_lines(doc, evidence),
        "",
        "## 可能的反驳",
        "",
        _render_section(sections.get("可能的反驳")),
        "",
    ]
    yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{yaml_text}---\n\n" + "\n".join(body).rstrip() + "\n"


def render_metric_page(
    draft: MetricDraft,
    doc: SourceDoc,
    run_id: str,
    evidence: list[dict],
    now: datetime,
) -> str:
    title = _clip(draft.title, 40)
    summary = _clip(draft.summary, 80) or title
    key = re.sub(r"[^a-z0-9_]", "_", draft.slug.replace("-", "_"))[:30]
    if not key or not key[0].isalpha():
        key = ("m_" + key)[:30]
    front = _common_frontmatter(
        page_id=f"metric:{draft.slug}",
        page_type="metric",
        title=title,
        summary=summary,
        doc=doc,
        run_id=run_id,
        now=now,
        evidence=evidence,
    )
    front["metric"] = {
        "name": title,
        "key": key,
        "value": _clip(draft.value, 20),
        "value_num": float(draft.value_num),
        "unit": _clip(draft.unit, 10),
        "direction": "lower" if draft.direction == "lower" else "higher",
        "period": _clip(draft.period, 20),
        "method": _clip(draft.method, 200),
        "scope": _clip(draft.scope, 100),
    }
    sections = draft.sections
    body = [
        f"# {title}",
        "",
        "## 口径",
        "",
        _render_section(sections.get("口径") or summary),
        "",
        "## 计算方式",
        "",
        _render_section(sections.get("计算方式") or draft.method),
        "",
        "## 为什么可信",
        "",
        _render_section(sections.get("为什么可信")),
        "",
        "## 常见追问",
        "",
        _render_section(sections.get("常见追问")),
        "",
        "## 证据",
        "",
        _evidence_lines(doc, evidence),
        "",
    ]
    yaml_text = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{yaml_text}---\n\n" + "\n".join(body).rstrip() + "\n"


def compile_document(
    llm: LLMClient,
    settings: Settings,
    user_id: str,
    doc: SourceDoc,
    blocks: list[SourceBlock],
    run_id: str | None = None,
    now: datetime | None = None,
) -> CompileResult:
    now = now or datetime.now(timezone.utc)
    run_id = run_id or next_run_id(settings, user_id, now)
    blocks_by_id = {b.block_id: b for b in blocks}
    if not blocks:
        raise LLMError("没有可编译的 block")

    truncated = len(blocks) > 40
    prompt_blocks = blocks[:40]
    user_prompt = build_prompt(doc, prompt_blocks)
    llm_result: LLMResult = llm.chat_json(SYSTEM_PROMPT, user_prompt)
    result = CompileResult(
        run_id=run_id,
        prompt_tokens=llm_result.prompt_tokens,
        completion_tokens=llm_result.completion_tokens,
        latency_ms=llm_result.latency_ms,
        model=llm_result.model,
    )
    if truncated:
        result.warnings.append("block 超过 40 个，只编译前 40 个")

    try:
        data = _extract_json(llm_result.content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM JSON 解析失败：{exc}") from exc

    raw_pages = data.get("pages")
    if not isinstance(raw_pages, list):
        raise LLMError("LLM 输出缺少 pages 数组")
    if len(raw_pages) > 8:
        result.warnings.append("LLM 返回超过 8 页，只处理前 8 页")
        raw_pages = raw_pages[:8]

    wiki_dir = settings.data_dir / "users" / user_id / "wiki"
    seen_slugs: set[str] = set()

    for raw in raw_pages:
        if not isinstance(raw, dict):
            continue
        page_type = raw.get("type")
        try:
            if page_type == "claim":
                draft = ClaimDraft.model_validate(raw)
            elif page_type == "metric":
                draft = MetricDraft.model_validate(raw)
            else:
                result.warnings.append(f"跳过不支持的类型：{page_type}")
                continue
        except Exception as exc:  # pydantic ValidationError
            result.warnings.append(f"跳过非法页面：{str(exc)[:120]}")
            continue

        if not SLUG_RE.match(draft.slug) or len(draft.slug) > 48:
            result.warnings.append(f"跳过非法 slug：{draft.slug}")
            continue
        if draft.slug in seen_slugs:
            result.warnings.append(f"跳过重复 slug：{draft.slug}")
            continue
        seen_slugs.add(draft.slug)

        evidence = _validate_evidence(draft.evidence, blocks_by_id)
        for ev in evidence:
            ev["source"] = doc.source_id
        if not evidence:
            result.warnings.append(f"跳过无有效证据页面：{draft.slug}")
            continue

        if isinstance(draft, ClaimDraft):
            if not _clip(draft.title, 40):
                result.warnings.append(f"跳过标题为空页面：{draft.slug}")
                continue
            if not (5 <= len(_clip(draft.statement, 400)) <= 60):
                result.warnings.append(f"跳过 statement 长度非法页面：{draft.slug}")
                continue
            if len(_clip(draft.scope, 200)) < 5:
                result.warnings.append(f"跳过 scope 过短页面：{draft.slug}")
                continue
            if draft.claim_kind not in CLAIM_KINDS:
                draft.claim_kind = "experience"
            markdown = render_claim_page(draft, doc, run_id, evidence, now)
            page_id = f"claim:{draft.slug}"
        else:
            if len(_clip(draft.title, 40)) < 2:
                result.warnings.append(f"跳过标题过短 metric：{draft.slug}")
                continue
            if not _clip(draft.value, 20) or not _clip(draft.unit, 10):
                result.warnings.append(f"跳过 value/unit 缺失 metric：{draft.slug}")
                continue
            if not _clip(draft.period, 20):
                result.warnings.append(f"跳过 period 缺失 metric：{draft.slug}")
                continue
            if len(_clip(draft.method, 200)) < 5 or len(_clip(draft.scope, 100)) < 2:
                result.warnings.append(f"跳过 method/scope 缺失 metric：{draft.slug}")
                continue
            markdown = render_metric_page(draft, doc, run_id, evidence, now)
            page_id = f"metric:{draft.slug}"

        relative_path = Path(".staging") / run_id / "pages" / page_type / f"{draft.slug}.md"
        target = wiki_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        result.pages.append(
            CompiledPage(
                id=page_id,
                type=page_type,
                title=_clip(draft.title, 40),
                path=str(relative_path).replace("\\", "/"),
                confidence="yellow",
                evidence_count=len(evidence),
            )
        )

    manifest_dir = wiki_dir / "runs" / run_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "kind": "compile",
        "status": "draft",
        "started_at": _iso(now),
        "finished_at": _iso(datetime.now(timezone.utc)),
        "document": {"id": doc.id, "source_id": doc.source_id, "filename": doc.filename},
        "model": result.model,
        "prompt_version": "compile-1.0.0",
        "tokens": {
            "prompt": result.prompt_tokens,
            "completion": result.completion_tokens,
        },
        "latency_ms": result.latency_ms,
        "pages": [
            {"id": page.id, "type": page.type, "path": page.path, "confidence": page.confidence}
            for page in result.pages
        ],
        "warnings": result.warnings,
    }
    (manifest_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    return result
