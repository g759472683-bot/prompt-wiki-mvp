from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from app.llm.client import LLMError, LLMResult
from app.services.jobs import process_next_job

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schema" / "page.frontmatter.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

PAGES = {
    "pages": [
        {
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
        },
        {
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
        },
    ]
}

CARDS = {
    "cards": [
        {
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
            "fallback": "具体细节我按复盘口径说，不夸大。",
            "evidence_refs": ["claim:ledger-migration-led"],
            "do_not_say": ["零故障"],
        }
    ]
}


class SequenceLLM:
    def __init__(self, *contents: str):
        self.contents = list(contents)

    def chat_json(self, system: str, user: str) -> LLMResult:
        content = self.contents.pop(0)
        return LLMResult(
            content=content,
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=1,
            model="fake",
        )


class FailingLLM:
    def chat_json(self, system: str, user: str) -> LLMResult:
        raise RuntimeError("boom")


def _upload(client, headers) -> str:
    text = (
        "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，"
        "覆盖 12 个服务、日均 2.3 亿笔交易。\n\n"
        "账务平台年度可用性 99.95%，对账延迟 P95 从 45 分钟降至 8 分钟。"
    )
    response = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("resume.txt", text.encode("utf-8"), "text/plain")},
        data={"doc_type": "resume", "trust": "high"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_job_compile_review_and_approve(api, auth):
    client, settings = api
    headers, user_id = auth
    doc_id = _upload(client, headers)

    llm = SequenceLLM(
        json.dumps(PAGES, ensure_ascii=False),
        json.dumps(CARDS, ensure_ascii=False),
    )
    client.app.state.llm = llm

    response = client.post(
        "/v1/compile-jobs",
        headers=headers,
        json={"document_id": doc_id, "with_cards": True},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    assert response.json()["status"] == "queued"

    processed = process_next_job(
        client.app.state.sessionmaker, settings, llm
    )
    assert processed == job_id

    job = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
    assert job["status"] == "succeeded", job
    assert len(job["result"]["pages"]) == 2
    assert len(job["result"]["cards"]) == 1
    run_id = job["result"]["run_id"]

    review = client.get(f"/v1/runs/{run_id}/review", headers=headers)
    assert review.status_code == 200, review.text
    assert len(review.json()["pages"]) == 3
    assert review.json()["collisions"] == []

    approved = client.post(f"/v1/runs/{run_id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert len(approved.json()["approved_pages"]) == 3

    wiki = settings.data_dir / "users" / user_id / "wiki"
    claim_path = wiki / "pages" / "claim" / "ledger-migration-led.md"
    assert claim_path.exists()
    front = yaml.safe_load(claim_path.read_text(encoding="utf-8").split("---", 2)[1])
    VALIDATOR.validate(front)
    assert front["status"] == "active"
    assert front["review"]["reviewed_by"].startswith("human:")
    assert "unreviewed" not in front["confidence"]["reasons"]

    pack_path = wiki / approved.json()["pack_path"]
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    assert pack["approved"] is True
    assert pack["cards"][0]["citations"]

    packs = client.get("/v1/packs", headers=headers)
    assert packs.status_code == 200
    assert packs.json()[0]["pack_id"] == pack["pack_id"]

    fetched = client.get(f"/v1/packs/{pack['pack_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["cards"][0]["question"] == CARDS["cards"][0]["question"]

    qa_id = pack["cards"][0]["qa_id"]
    pinned = client.put(
        "/v1/pins/point",
        headers=headers,
        json={
            "qa_id": qa_id,
            "point_index": 1,
            "summary": "人工固定摘要",
            "detail": "人工固定的展开说明，保留原有依据和追问。",
        },
    )
    assert pinned.status_code == 200, pinned.text
    after_pin = client.get(f"/v1/packs/{pack['pack_id']}", headers=headers).json()
    point = after_pin["cards"][0]["points"][0]
    assert point["pinned"] is True
    assert point["detail"].startswith("人工固定")

    for _ in range(5):
        feedback = client.post(
            "/v1/feedback",
            headers=headers,
            json={
                "pack_id": pack["pack_id"],
                "qa_id": qa_id,
                "question": CARDS["cards"][0]["question"],
                "label": "useful",
                "confidence": "yellow",
            },
        )
        assert feedback.status_code == 200
    calibration = client.get("/v1/calibration", headers=headers).json()
    yellow = next(
        item for item in calibration["buckets"] if item["confidence"] == "yellow"
    )
    assert yellow["samples"] == 5
    assert yellow["accuracy"] == 1.0
    calibrated_pack = client.get(
        f"/v1/packs/{pack['pack_id']}", headers=headers
    ).json()
    assert calibrated_pack["cards"][0]["confidence"]["calibrated"] is True
    assert calibrated_pack["cards"][0]["confidence"]["score"] == 100

    assert (wiki / "runs" / run_id / "review.yaml").exists()

    again = client.post(f"/v1/runs/{run_id}/approve", headers=headers)
    assert again.status_code == 409

    replaced = client.post(
        f"/v1/runs/{run_id}/approve?replace=true", headers=headers
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["approved_pages"]

    again = client.post(f"/v1/runs/{run_id}/approve", headers=headers)
    assert again.status_code == 409


def test_job_failure_is_persisted(api, auth):
    client, settings = api
    headers, _ = auth
    doc_id = _upload(client, headers)
    client.app.state.llm = FailingLLM()

    response = client.post(
        "/v1/compile-jobs",
        headers=headers,
        json={"document_id": doc_id, "with_cards": True},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    process_next_job(client.app.state.sessionmaker, settings, client.app.state.llm)
    job = client.get(f"/v1/jobs/{job_id}", headers=headers).json()
    assert job["status"] == "failed"
    assert "boom" in job["error"]


def test_enqueue_requires_llm(api, auth):
    client, _ = api
    headers, _ = auth
    doc_id = _upload(client, headers)
    client.app.state.llm = None
    response = client.post(
        "/v1/compile-jobs",
        headers=headers,
        json={"document_id": doc_id},
    )
    assert response.status_code == 503
