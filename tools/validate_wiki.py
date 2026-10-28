#!/usr/bin/env python3
"""LLM Wiki Schema 契约的参考校验器（MVP）。

用法:
    python tools/validate_wiki.py examples/wiki
    python tools/validate_wiki.py examples/wiki --json

只依赖标准库 + PyYAML。校验的是契约中最容易出错、代价最高的不变量：
ID/链接、证据逐字命中、置信度红线、卡片上限与数字追溯、Pin 锚点、冲突未决状态。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML：pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
BLOCK_RE = re.compile(r"<!--\s*(b-\d{4})\s*\|([^>]*)-->")
NUM_RE = re.compile(r"(?<![A-Za-z0-9])(\d+(?:\.\d+)?)")
E_RE = re.compile(r"(?<![A-Za-z])E(\d+)")

HEADINGS = {
    "claim": ["一句话说法", "成立条件", "证据", "可能的反驳"],
    "story": ["情境 S", "任务 T", "行动 A", "结果 R", "复盘与边界", "追问预案"],
    "metric": ["口径", "计算方式", "为什么可信", "常见追问"],
    "qa": ["一句话回答", "展开", "证据", "边界与不知道", "追问预案"],
    "entity": ["一句话定义", "关键事实", "与我的关系", "关联页面"],
    "scenario": ["会前简报", "对方关注点", "我的三个目标", "风险与禁区", "问题清单"],
}

TYPE_REQUIRED = {
    "index": ["index_scope"],
    "source": ["source", "trust", "version", "supersedes", "archived_at", "extraction"],
    "entity": ["entity_kind", "confidence", "evidence"],
    "claim": ["statement", "claim_kind", "scope", "verification", "confidence", "evidence"],
    "story": ["story_kind", "role", "period", "confidence", "evidence"],
    "metric": ["metric", "confidence", "evidence"],
    "qa": [
        "question", "question_variants", "intent", "scenario_kinds",
        "answer", "card", "evidence_refs", "confidence",
    ],
    "scenario": [
        "scenario_kind", "counterparty", "scheduled_at", "duration_min",
        "goal", "questions", "prepared_at", "prep_run",
    ],
}

ID_RE = re.compile(
    r"^(index|source|entity|claim|story|metric|qa|scenario):"
    r"[a-z0-9]+(-[a-z0-9]+)*$"
)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def pointer_get(obj, path: str):
    if path == "":
        return obj
    parts = [p.replace("~1", "/").replace("~0", "~") for p in path.split("/")[1:]]
    cur = obj
    for part in parts:
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.pages: dict[str, dict] = {}
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.conflicts: dict[str, dict] = {}

    # ---------- 基础 ----------
    def err(self, where: str, msg: str):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str):
        self.warnings.append(f"{where}: {msg}")

    def load(self):
        for path in sorted(self.root.rglob("*.md")):
            rel = path.relative_to(self.root).as_posix()
            parts = Path(rel).parts
            # 只加载 Wiki 页面；runs/lint/query 等是报告，不是页面
            is_page = rel == "index.md" or (
                bool(parts) and parts[0] in {"indexes", "pages", "sources"}
            )
            if not is_page:
                continue
            text = path.read_text(encoding="utf-8")
            m = FM_RE.match(text)
            if not m:
                self.err(str(path), "缺少 frontmatter（--- 包裹）")
                continue
            try:
                front = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError as exc:
                self.err(str(path), f"frontmatter YAML 解析失败：{exc}")
                continue
            body = m.group(2)
            pid = front.get("id")
            rec = {"path": path, "rel": rel, "front": front, "body": body}
            if not pid:
                self.err(rel, "缺少 id")
                continue
            if pid in self.pages:
                self.err(rel, f"id 重复：{pid}（另见 {self.pages[pid]['rel']}）")
                continue
            self.pages[pid] = rec

        for path in sorted((self.root / "conflicts").glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                self.err(path.as_posix(), f"冲突 YAML 解析失败：{exc}")
                continue
            cid = data.get("conflict_id")
            if cid:
                self.conflicts[cid] = data
            if cid and path.stem != cid:
                self.warn(path.as_posix(), f"文件名与 conflict_id 不一致：{cid}")

    # ---------- 通用字段 ----------
    def check_common(self):
        common = [
            "schema_version", "id", "type", "title", "summary", "status",
            "language", "revision", "created_at", "updated_at", "created_by", "run_id",
        ]
        for pid, rec in self.pages.items():
            f, rel = rec["front"], rec["rel"]
            for key in common:
                if key not in f:
                    self.err(rel, f"缺少必填字段 {key}")
            if not ID_RE.match(pid):
                self.err(rel, f"id 不符合规范：{pid}")
            if f.get("type") not in TYPE_REQUIRED:
                self.err(rel, f"未知 type：{f.get('type')}")
                continue
            if len(str(f.get("title", ""))) > 40:
                self.err(rel, "title 超过 40 字")
            if len(str(f.get("summary", ""))) > 80:
                self.err(rel, "summary 超过 80 字")
            if f.get("status") not in {"draft", "active", "stale", "retired"}:
                self.err(rel, f"status 非法：{f.get('status')}")
            if not isinstance(f.get("revision"), int) or f.get("revision", 0) < 1:
                self.err(rel, "revision 必须是 >=1 的整数")
            for key in TYPE_REQUIRED.get(f.get("type"), []):
                if key not in f:
                    self.err(rel, f"{f.get('type')} 缺少字段 {key}")

            # 目录与类型一致性
            parts = Path(rel).parts
            t = f.get("type")
            if parts and parts[0] == "pages":
                if len(parts) < 3 or parts[1] != t:
                    self.err(rel, f"页面路径与 type={t} 不一致")
            elif parts and parts[0] == "sources":
                if t != "source":
                    self.err(rel, "sources/ 下必须是 source 类型")
            elif parts and parts[0] == "indexes":
                if t != "index":
                    self.err(rel, "indexes/ 下必须是 index 类型")
            elif rel == "index.md":
                if t != "index":
                    self.err(rel, "根 index.md 必须是 index 类型")

    # ---------- 来源 block ----------
    def check_sources(self):
        for pid, rec in self.pages.items():
            f = rec["front"]
            if f.get("type") != "source":
                continue
            rel = rec["rel"]
            meta = f.get("source") or {}
            sha = str(meta.get("sha256", ""))
            if not re.fullmatch(r"[a-f0-9]{64}", sha):
                self.err(rel, "source.sha256 必须是 64 位小写十六进制")
            blocks = self.source_blocks(rec)
            extract = f.get("extraction") or {}
            if extract.get("blocks") != len(blocks):
                self.err(rel, f"extraction.blocks={extract.get('blocks')} 与实际 {len(blocks)} 不符")
            if not blocks:
                self.err(rel, "source 页没有任何 block")
            for bid in blocks:
                if not re.fullmatch(r"b-\d{4}", bid):
                    self.err(rel, f"block id 非法：{bid}")

    def source_blocks(self, rec: dict) -> dict[str, str]:
        body = rec["body"]
        found = list(BLOCK_RE.finditer(body))
        blocks: dict[str, str] = {}
        for idx, m in enumerate(found):
            bid = m.group(1)
            start = m.end()
            end = found[idx + 1].start() if idx + 1 < len(found) else len(body)
            chunk = body[start:end]
            lines = [ln for ln in chunk.splitlines() if not ln.lstrip().startswith("#")]
            blocks[bid] = "\n".join(lines).strip()
        return blocks

    # ---------- 证据 ----------
    def check_evidence(self):
        for pid, rec in self.pages.items():
            f = rec["front"]
            evidence = f.get("evidence") or []
            if not isinstance(evidence, list):
                self.err(rec["rel"], "evidence 必须是数组")
                continue
            for i, ev in enumerate(evidence):
                self.check_one_evidence(rec, ev, f"evidence[{i}]")

    def check_one_evidence(self, rec: dict, ev: dict, where: str):
        rel = rec["rel"]
        if not isinstance(ev, dict):
            self.err(rel, f"{where} 不是对象")
            return
        src_id = ev.get("source")
        src = self.pages.get(src_id)
        if not src:
            self.err(rel, f"{where} 指向不存在的 source：{src_id}")
            return
        if src["front"].get("type") != "source":
            self.err(rel, f"{where} 的 source 不是 source 页：{src_id}")
            return
        version = ev.get("source_version")
        if version != src["front"].get("version"):
            self.err(rel, f"{where} 版本 {version} 与 source 当前版本 {src['front'].get('version')} 不符")
        block_id = ev.get("block")
        blocks = self.source_blocks(src)
        if block_id not in blocks:
            self.err(rel, f"{where} 引用不存在的 block：{src_id}#{block_id}")
            return
        quote = ev.get("quote", "")
        if not isinstance(quote, str) or len(quote) < 5:
            self.err(rel, f"{where} quote 过短")
            return
        if len(quote) > 200:
            self.err(rel, f"{where} quote 超过 200 字")
        if norm(quote) not in norm(blocks[block_id]):
            self.err(rel, f"{where} quote 未逐字命中 {src_id}#{block_id}：{quote[:40]}")
        if "verified" in ev and not isinstance(ev.get("verified"), bool):
            self.err(rel, f"{where} verified 必须是布尔值")

    # ---------- 置信度 ----------
    def check_confidence(self):
        for pid, rec in self.pages.items():
            f = rec["front"]
            conf = f.get("confidence")
            if not conf:
                continue
            rel = rec["rel"]
            level = conf.get("level")
            if level not in {"green", "yellow", "red"}:
                self.err(rel, f"confidence.level 非法：{level}")
                continue
            if conf.get("rule") != "rule_v1":
                self.err(rel, "confidence.rule 必须是 rule_v1")
            open_conflicts = {
                cid for cid in (f.get("conflicts") or [])
                if self.conflicts.get(cid, {}).get("status") == "open"
            }
            qa_blocked = f.get("type") == "qa" and bool(open_conflicts)
            if level != "red" and (f.get("conflict_state") == "open" or qa_blocked):
                self.err(rel, "存在未决冲突但置信度不是 red")
            evidence = f.get("evidence") or []
            if evidence and all(ev.get("verified") is False for ev in evidence) and level != "red":
                self.err(rel, "全部证据未核验，置信度必须为 red")
            if level != "green":
                continue
            # qa 的证据在 evidence_refs 指向的页面里，需要展开后再判独立来源
            green_evidence = list(evidence)
            if f.get("type") == "qa":
                green_evidence = []
                for ref in f.get("evidence_refs") or []:
                    ref_page = self.pages.get(ref)
                    if ref_page:
                        green_evidence.extend(ref_page["front"].get("evidence") or [])
            sources = {ev.get("source") for ev in green_evidence}
            if len(sources) < 2:
                self.err(rel, "green 需要 >=2 个独立来源")
            if any(ev.get("verified") is not True for ev in green_evidence):
                self.err(rel, "green 要求全部证据 verified=true")
            review = f.get("review") or {}
            if not str(review.get("reviewed_by", "")).startswith("human:"):
                self.err(rel, "green 需要人工审核（review.reviewed_by=human:*）")
            if f.get("conflict_state") == "open" or open_conflicts:
                self.err(rel, "green 不允许存在未决冲突")
            if f.get("type") == "qa":
                for ref in f.get("evidence_refs") or []:
                    ref_page = self.pages.get(ref)
                    if not ref_page:
                        self.err(rel, f"evidence_refs 指向不存在页面：{ref}")
                        continue
                    if (ref_page["front"].get("confidence") or {}).get("level") != "green":
                        self.err(rel, f"green 卡片的引用页 {ref} 不是 green")

    # ---------- 卡片 ----------
    def check_cards(self):
        for pid, rec in self.pages.items():
            f = rec["front"]
            if f.get("type") != "qa":
                continue
            rel = rec["rel"]
            card = f.get("card") or {}
            l1 = card.get("l1") or []
            l2 = card.get("l2") or []
            if not (3 <= len(l1) <= 5):
                self.err(rel, f"card.l1 条数 {len(l1)} 不在 3..5")
            if not (3 <= len(l2) <= 5):
                self.err(rel, f"card.l2 条数 {len(l2)} 不在 3..5")
            for i, item in enumerate(l1):
                if len(item) > 12:
                    self.err(rel, f"card.l1[{i}] 超过 12 字：{item}")
            for i, item in enumerate(l2):
                if len(item) > 28:
                    self.err(rel, f"card.l2[{i}] 超过 28 字：{item}")
            if len(card.get("fallback", "")) > 100:
                self.err(rel, "card.fallback 超过 100 字")
            if card.get("confidence", {}).get("level") != (f.get("confidence") or {}).get("level"):
                self.err(rel, "card.confidence 与页面 confidence 不一致")
            refs = card.get("evidence_refs") or []
            if not refs:
                self.err(rel, "card.evidence_refs 为空")
            for ref in refs:
                if ref not in self.pages:
                    self.err(rel, f"card.evidence_refs 指向不存在页面：{ref}")
            for item in card.get("built_from") or []:
                target = self.pages.get(item.get("id"))
                if not target:
                    self.err(rel, f"built_from 指向不存在页面：{item.get('id')}")
                elif target["front"].get("revision") != item.get("revision"):
                    self.err(
                        rel,
                        f"卡片过期：{item.get('id')} built_from={item.get('revision')} "
                        f"当前={target['front'].get('revision')}",
                    )
            for phrase in card.get("do_not_say") or []:
                haystack = " ".join(l1 + l2 + [card.get("fallback", ""), rec["body"]])
                if phrase and phrase in haystack:
                    self.err(rel, f"出现禁用表述：{phrase}")
            self.check_numeric_trace(rec, card)

    def check_numeric_trace(self, rec: dict, card: dict):
        rel = rec["rel"]
        quotes = []
        for ev in rec["front"].get("evidence") or []:
            quotes.append(ev.get("quote", ""))
        for ref in card.get("evidence_refs") or []:
            ref_page = self.pages.get(ref)
            if ref_page:
                for ev in ref_page["front"].get("evidence") or []:
                    quotes.append(ev.get("quote", ""))
        haystack = norm(" ".join(quotes))
        texts = list(card.get("l1") or []) + list(card.get("l2") or []) + [card.get("fallback", "")]
        for text in texts:
            for number in NUM_RE.findall(text):
                if number not in haystack:
                    self.err(rel, f"卡片数字无法追溯：{number}（{text[:24]}）")

    # ---------- 链接 / 标题 / E 编号 ----------
    def check_links(self):
        for pid, rec in self.pages.items():
            for target in LINK_RE.findall(rec["body"]):
                target = target.strip()
                if target.startswith(("#", "http")):
                    continue
                if target not in self.pages:
                    self.err(rec["rel"], f"断链：[[{target}]]")

    def check_headings(self):
        for pid, rec in self.pages.items():
            t = rec["front"].get("type")
            for heading in HEADINGS.get(t, []):
                if f"## {heading}" not in rec["body"]:
                    self.err(rec["rel"], f"缺少固定标题：## {heading}")

    def check_enumbers(self):
        for pid, rec in self.pages.items():
            if rec["front"].get("type") == "qa":
                continue
            count = len(rec["front"].get("evidence") or [])
            for n in E_RE.findall(rec["body"]):
                if int(n) > count:
                    self.err(rec["rel"], f"正文引用 E{n}，但只有 {count} 条证据")

    # ---------- Pin ----------
    def check_pins(self):
        pin_dir = self.root / "pins"
        if not pin_dir.exists():
            return
        for path in sorted(pin_dir.glob("*.yaml")):
            rel = path.relative_to(self.root).as_posix()
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                self.err(rel, f"Pin YAML 解析失败：{exc}")
                continue
            page = self.pages.get(data.get("page"))
            if not page:
                self.err(rel, f"Pin 指向不存在的页面：{data.get('page')}")
                continue
            seen_replace: set[str] = set()
            for pin in data.get("pins") or []:
                if pin.get("status") != "active":
                    continue
                anchor = pin.get("anchor") or {}
                mode = pin.get("mode")
                value = pin.get("value")
                if mode == "replace":
                    key = anchor.get("path") or anchor.get("heading", "")
                    if key in seen_replace:
                        self.err(rel, f"同一锚点存在多条 active replace Pin：{key}")
                    seen_replace.add(key)
                if anchor.get("kind") == "field":
                    path_expr = anchor.get("path", "")
                    if path_expr == "/body":
                        if mode == "must_exclude" and value and value in page["body"]:
                            self.err(rel, f"页面正文出现禁用表述：{value}")
                        elif mode == "replace":
                            self.warn(rel, "不支持对 /body 做 replace Pin（建议用 section 锚点）")
                        continue
                    current = pointer_get(page["front"], path_expr)
                    if current is None:
                        self.err(rel, f"Pin 锚点不存在：{path_expr}")
                        continue
                    if mode == "replace" and current != value:
                        self.err(rel, f"Pin 未生效：{path_expr} 当前值 != Pin 值")
                    if mode == "must_include" and value not in str(current):
                        self.err(rel, f"Pin must_include 未满足：{path_expr}")
                    if mode == "must_exclude" and value in str(current):
                        self.err(rel, f"禁用表述出现在 {path_expr}：{value}")
                elif anchor.get("kind") == "section":
                    heading = anchor.get("heading", "")
                    if f"## {heading}" not in page["body"]:
                        self.err(rel, f"Pin 的 section 不存在：{heading}")

    # ---------- 冲突 ----------
    def check_conflicts(self):
        for cid, data in self.conflicts.items():
            rel = f"conflicts/{cid}.yaml"
            if data.get("schema_version") != "1.0":
                self.err(rel, "schema_version 必须是 1.0")
            status = data.get("status")
            if status not in {"open", "resolved", "dismissed"}:
                self.err(rel, f"status 非法：{status}")
            for page_id in (data.get("subject") or {}).get("pages") or []:
                page = self.pages.get(page_id)
                if not page:
                    self.err(rel, f"subject 页不存在：{page_id}")
                    continue
                if cid not in (page["front"].get("conflicts") or []):
                    self.err(rel, f"{page_id} 的 conflicts 未登记 {cid}")
                if status == "open" and page["front"].get("conflict_state") != "open":
                    self.err(rel, f"未决冲突的主体页 {page_id} 必须 conflict_state=open")
            variants = data.get("variants") or []
            if len(variants) < 2:
                self.err(rel, "至少需要两个 variant")
            for v in variants:
                ev = v.get("evidence") or {}
                fake = {"rel": rel, "front": {}}
                self.check_one_evidence(fake, ev, f"variant {v.get('variant_id')}")
            resolution = data.get("resolution") or {}
            if status in {"resolved", "dismissed"}:
                if not str(resolution.get("resolved_by", "")).startswith("human:"):
                    self.err(rel, "已解决冲突必须由 human:* 裁决")
                if resolution.get("mode") in {None, "null"}:
                    self.err(rel, "已解决冲突缺少 resolution.mode")
                if not resolution.get("rationale"):
                    self.err(rel, "已解决冲突缺少 rationale")
            else:
                if resolution.get("mode") or resolution.get("resolved_by"):
                    self.err(rel, "未决冲突不得写 resolution")

        for pid, rec in self.pages.items():
            refs = rec["front"].get("conflicts") or []
            for cid in refs:
                if cid not in self.conflicts:
                    self.err(rec["rel"], f"conflicts 引用了不存在的冲突：{cid}")
            if rec["front"].get("conflict_state") == "open":
                has_open = any(
                    self.conflicts.get(cid, {}).get("status") == "open" for cid in refs
                )
                if not has_open:
                    self.err(rec["rel"], "conflict_state=open 但没有对应的未决冲突记录")

    # ---------- 查询快照 / Lint ----------
    def check_queries(self):
        query_dir = self.root / "query"
        if not query_dir.exists():
            return
        for path in sorted(query_dir.glob("*.json")):
            rel = path.relative_to(self.root).as_posix()
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.err(rel, f"JSON 解析失败：{exc}")
                continue
            matched = data.get("matched") or {}
            qa = matched.get("qa")
            if qa and qa not in self.pages:
                self.err(rel, f"matched.qa 不存在：{qa}")
            card = data.get("card") or {}
            conf = (card.get("confidence") or {}).get("level")
            if conf == "red" and not card.get("must_show_fallback_first"):
                self.err(rel, "红色卡片必须 must_show_fallback_first=true")
            if data.get("degraded") and conf == "green":
                self.err(rel, "降级卡片不允许 green")
            l2_len = len(card.get("l2") or [])
            for c in card.get("citations") or []:
                self.check_one_evidence({"rel": rel, "front": {}}, {
                    "source": c.get("source"),
                    "source_version": c.get("source_version"),
                    "block": c.get("block"),
                    "quote": c.get("quote"),
                    "verified": True,
                }, "citation")
                for support in c.get("supports") or []:
                    m = re.fullmatch(r"l2:(\d+)", support)
                    if not m or int(m.group(1)) >= l2_len:
                        self.err(rel, f"citation.supports 越界：{support}")
            t = data.get("timings_ms") or {}
            if all(k in t for k in ("l1", "l2", "l3", "total")):
                if not (t["l1"] <= t["l2"] <= t["l3"] <= t["total"]):
                    self.err(rel, "timings_ms 不是单调递增")

    def check_lint(self):
        lint_dir = self.root / "lint"
        if not lint_dir.exists():
            return
        for path in sorted(lint_dir.glob("*.yaml")):
            rel = path.relative_to(self.root).as_posix()
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            issues = data.get("issues") or []
            blockers = [i for i in issues if i.get("severity") == "blocker"]
            summary = data.get("summary") or {}
            if summary.get("blocker") != len(blockers):
                self.err(rel, "summary.blocker 与 issues 不一致")
            gate = data.get("gate") or {}
            if blockers and gate.get("publish_allowed"):
                self.err(rel, "存在 blocker 却 publish_allowed=true")

    def run(self) -> int:
        self.load()
        self.check_common()
        self.check_sources()
        self.check_evidence()
        self.check_confidence()
        self.check_cards()
        self.check_links()
        self.check_headings()
        self.check_enumbers()
        self.check_pins()
        self.check_conflicts()
        self.check_queries()
        self.check_lint()
        print(f"页面 {len(self.pages)} · 冲突 {len(self.conflicts)}")
        for w in self.warnings:
            print(f"WARN  {w}")
        for e in self.errors:
            print(f"ERROR {e}")
        if self.errors:
            print(f"\nFAILED：{len(self.errors)} 个错误，{len(self.warnings)} 个警告")
            return 1
        print(f"\nOK：0 个错误，{len(self.warnings)} 个警告")
        return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="校验 LLM Wiki 示例库是否满足 Schema 契约")
    parser.add_argument("wiki", nargs="?", default="examples/wiki", help="wiki 根目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()
    checker = Checker(Path(args.wiki))
    code = checker.run()
    if args.json:
        print(json.dumps(
            {"errors": checker.errors, "warnings": checker.warnings},
            ensure_ascii=False, indent=2,
        ))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
