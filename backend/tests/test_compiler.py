from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import yaml
from jsonschema import Draft202012Validator

from app.config import Settings
from app.llm.client import DeepSeekClient, LLMError, LLMResult
from app.services.cards import CardDraft, _validate_card
from app.services.compiler import SourceBlock, SourceDoc, compile_document

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schema" / "page.frontmatter.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

CLAIM = {
    "type": "claim",
    "slug": "ledger-migration-led",
    "title": "分库迁移由我牵头",
    "summary": "账务分库迁移覆盖 12 个服务，由我牵头。",
    "statement": "账务平台分库迁移由我牵头，覆盖 12 个服务。",
    "claim_kind": "experience",
    "scope": "适用于项目经历；不用于证明迁移零故障。",
    "evidence": [
        {
            "block": "b-0001",
            "quote": "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易",
        }
    ],
    "sections": {
        "一句话说法": "迁移由我牵头，覆盖 12 个服务。",
        "成立条件": ["有简历与复盘两份材料"],
        "可能的反驳": ["规模这么大是不是团队做的"],
    },
}

METRIC = {
    "type": "metric",
    "slug": "availability-2025",
    "title": "2025 年度可用性",
    "summary": "复盘口径 99.95%",
    "value": "99.95%",
    "value_num": 99.95,
    "unit": "%",
    "direction": "higher",
    "period": "2025",
    "method": "按分钟不可用时长 / 全年分钟数",
    "scope": "账务平台",
    "evidence": [{"block": "b-0002", "quote": "账务平台年度可用性 99.95%"}],
    "sections": {
        "口径": "年度核心接口可用性",
        "计算方式": "不可用分钟 / 全年分钟",
        "为什么可信": "来自复盘材料",
        "常见追问": ["和 99.99% 的冲突怎么解释"],
    },
}

CARD = {
    "slug": "why-ledger-migration",
    "question": "为什么账务迁移由你牵头？",
    "variants": ["这个迁移为什么是你负责", "你在大迁移里做了什么"],
    "intent": "behavioral",
    "target_sec": 60,
    "l1": ["分片迁移", "12 个服务", "灰度放量"],
    "l2": [
        "账务 12 个服务迁移由我牵头",
        "按商户 ID 分片、双写 6 周",
        "灰度放量，覆盖 2.3 亿笔/日",
    ],
    "fallback": "细节我按复盘口径说，不夸大。",
    "evidence_refs": ["claim:ledger-migration-led"],
    "do_not_say": ["零故障"],
}


class FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def chat_json(self, system: str, user: str) -> LLMResult:
        self.calls += 1
        return LLMResult(
            content=self.content,
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=10,
            model="fake",
        )


class SequenceLLM:
    def __init__(self, *contents: str):
        self.contents = list(contents)

    def chat_json(self, system: str, user: str) -> LLMResult:
        content = self.contents.pop(0)
        return LLMResult(
            content=content,
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=10,
            model="fake",
        )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        secret_key="test-secret-0123456789abcdef0123456789",
        invite_codes="TEST",
        data_dir=tmp_path / "data",
    )


def _doc() -> SourceDoc:
    return SourceDoc(
        id="doc-test",
        source_id="source:doc-test",
        filename="resume.txt",
        doc_type="resume",
        created_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
    )


def _blocks() -> list[SourceBlock]:
    return [
        SourceBlock(
            "b-0001",
            1,
            "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，"
            "覆盖 12 个服务、日均 2.3 亿笔交易。",
        ),
        SourceBlock(
            "b-0002",
            2,
            "账务平台年度可用性 99.95%，对账延迟 P95 从 45 分钟降至 8 分钟。",
        ),
    ]


def test_compile_writes_contract_pages(tmp_path):
    settings = _settings(tmp_path)
    content = json.dumps({"pages": [CLAIM, METRIC]}, ensure_ascii=False)
    result = compile_document(
        FakeLLM(content),
        settings,
        "usr-test",
        _doc(),
        _blocks(),
        run_id="run-20261025-01",
    )

    assert len(result.pages) == 2
    assert result.run_id == "run-20261025-01"
    assert result.prompt_tokens == 100
    assert not result.warnings

    for page in result.pages:
        path = settings.data_dir / "users" / "usr-test" / "wiki" / page.path
        assert path.exists()
        raw = path.read_text(encoding="utf-8")
        front = yaml.safe_load(raw.split("---", 2)[1])
        VALIDATOR.validate(front)
        assert front["status"] == "draft"
        assert front["run_id"] == "run-20261025-01"
        assert front["evidence"][0]["source"] == "source:doc-test"
        assert front["evidence"][0]["verified"] is True

    claim = yaml.safe_load(
        (
            settings.data_dir
            / "users"
            / "usr-test"
            / "wiki"
            / ".staging"
            / "run-20261025-01"
            / "pages"
            / "claim"
            / "ledger-migration-led.md"
        )
        .read_text(encoding="utf-8")
        .split("---", 2)[1]
    )
    assert claim["statement"].startswith("账务平台分库迁移")
    assert "## 证据" in (
        settings.data_dir
        / "users"
        / "usr-test"
        / "wiki"
        / ".staging"
        / "run-20261025-01"
        / "pages"
        / "claim"
        / "ledger-migration-led.md"
    ).read_text(encoding="utf-8")

    manifest = settings.data_dir / "users" / "usr-test" / "wiki" / "runs" / "run-20261025-01" / "manifest.yaml"
    assert manifest.exists()
    assert yaml.safe_load(manifest.read_text(encoding="utf-8"))["pages"]


def test_compile_skips_pages_without_valid_evidence(tmp_path):
    bad = json.loads(json.dumps(CLAIM, ensure_ascii=False))
    bad["evidence"] = [{"block": "b-0001", "quote": "这句话不在原文里"}]
    result = compile_document(
        FakeLLM(json.dumps({"pages": [bad]}, ensure_ascii=False)),
        _settings(tmp_path),
        "usr-test",
        _doc(),
        _blocks(),
    )
    assert result.pages == []
    assert any("无有效证据" in warning for warning in result.warnings)


def test_compile_raises_on_invalid_json(tmp_path):
    with pytest.raises(LLMError):
        compile_document(
            FakeLLM("not json"),
            _settings(tmp_path),
            "usr-test",
            _doc(),
            _blocks(),
        )


def test_deepseek_client_success_and_auth_error():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.headers.get("Authorization") == "Bearer bad":
            return httpx.Response(401, json={"error": "bad key"})
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = DeepSeekClient(
        api_key="good",
        base_url="https://api.deepseek.com",
        client=http_client,
    )
    result = client.chat_json("system", "user")
    assert result.content == '{"ok": true}'
    assert result.prompt_tokens == 12
    assert calls["n"] == 1

    bad = DeepSeekClient(
        api_key="bad",
        base_url="https://api.deepseek.com",
        client=http_client,
    )
    with pytest.raises(LLMError, match="authentication"):
        bad.chat_json("system", "user")


def test_card_validation_filters_overlong_bullets():
    page = {
        "id": "claim:ledger-migration-led",
        "title": "分库迁移由我牵头",
        "evidence": [{"quote": CLAIM["evidence"][0]["quote"], "source": "source:doc-test"}],
    }
    draft = CardDraft(
        **{
            **CARD,
            "l2": CARD["l2"]
            + ["这是一条明显超过二十八字的骨架用来验证过长条目会被整张卡丢弃"],
        }
    )
    data, error = _validate_card(draft, {page["id"]: page}, set(), 1)
    assert error is None
    assert data is not None
    assert len(data["l2"]) == 3

    bad_slug = CardDraft(**{**CARD, "slug": "中文-slug"})
    data, error = _validate_card(bad_slug, {page["id"]: page}, set(), 7)
    assert error is None
    assert data is not None
    assert data["slug"] == "qa-07"


def test_compile_endpoint_and_503_without_llm(api, auth):
    client, _ = api
    headers, _ = auth
    text = (
        "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，"
        "覆盖 12 个服务、日均 2.3 亿笔交易。\n\n"
        "账务平台年度可用性 99.95%，对账延迟 P95 从 45 分钟降至 8 分钟。"
    )
    upload = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("resume.txt", text.encode("utf-8"), "text/plain")},
        data={"doc_type": "resume", "trust": "high"},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    client.app.state.llm = FakeLLM(
        json.dumps({"pages": [CLAIM, METRIC]}, ensure_ascii=False)
    )
    compiled = client.post(
        f"/v1/documents/{doc_id}/compile",
        headers=headers,
        params={"with_cards": False},
    )
    assert compiled.status_code == 200, compiled.text
    body = compiled.json()
    assert len(body["pages"]) == 2
    assert body["cards"] == []
    assert body["run_id"].startswith("run-")

    client.app.state.llm = None
    blocked = client.post(
        f"/v1/documents/{doc_id}/compile",
        headers=headers,
        params={"with_cards": False},
    )
    assert blocked.status_code == 503


def test_compile_endpoint_generates_cards_and_pack(api, auth):
    client, settings = api
    headers, user_id = auth
    text = (
        "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，"
        "覆盖 12 个服务、日均 2.3 亿笔交易。\n\n"
        "账务平台年度可用性 99.95%，对账延迟 P95 从 45 分钟降至 8 分钟。"
    )
    upload = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("resume.txt", text.encode("utf-8"), "text/plain")},
        data={"doc_type": "resume", "trust": "high"},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    client.app.state.llm = SequenceLLM(
        json.dumps({"pages": [CLAIM, METRIC]}, ensure_ascii=False),
        json.dumps({"cards": [CARD]}, ensure_ascii=False),
    )
    response = client.post(f"/v1/documents/{doc_id}/compile", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["cards"]) == 1
    card = body["cards"][0]
    assert card["question"] == CARD["question"]

    wiki = settings.data_dir / "users" / user_id / "wiki"
    qa_path = wiki / card["path"]
    assert qa_path.exists()
    raw = qa_path.read_text(encoding="utf-8")
    front = yaml.safe_load(raw.split("---", 2)[1])
    VALIDATOR.validate(front)
    assert front["type"] == "qa"
    assert front["card"]["l1"] == CARD["l1"]
    assert "## 一句话回答" in raw

    pack = json.loads(
        (wiki / ".staging" / body["run_id"] / "pack.json").read_text(encoding="utf-8")
    )
    assert pack["cards"][0]["qa_id"] == card["id"]
    assert pack["cards"][0]["citations"]
    first = pack["cards"][0]
    assert len(first["points"]) == len(first["l2"])
    assert first["points"][0]["summary"] == first["l2"][0]
    assert first["confidence"]["score"] in {30, 60, 85}
    assert first["points"][0]["confidence"]["score"] in {30, 60, 85}


