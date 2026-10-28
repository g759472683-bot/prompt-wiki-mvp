from __future__ import annotations

import json

from app.llm.client import LLMResult

TEXT = (
    "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，"
    "覆盖 12 个服务、日均 2.3 亿笔交易。\n\n"
    "账务平台年度可用性 99.95%，对账延迟 P95 从 45 分钟降至 8 分钟。"
)

ANSWER = {
    "answer": "账务平台 2025 年度可用性是 99.95%。",
    "l1": ["年度可用性", "99.95%", "复盘口径"],
    "l2": [
        "账务平台 2025 年度可用性是 99.95%。",
        "这个数字来自我的复盘材料。",
        "如果追问口径，我会按原文说明。",
    ],
    "fallback": "具体口径我按复盘确认，不把它说成 99.99%。",
    "citations": [{"block": "b-0002", "quote": "账务平台年度可用性 99.95%"}],
}


class FakeLLM:
    def __init__(self, content: str):
        self.content = content

    def chat_json(self, system: str, user: str, max_tokens: int | None = None) -> LLMResult:
        return LLMResult(
            content=self.content,
            prompt_tokens=20,
            completion_tokens=10,
            latency_ms=5,
            model="fake",
        )


def test_ask_uses_retrieved_blocks_and_citations(api, auth):
    client, _ = api
    headers, _ = auth
    upload = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("resume.txt", TEXT.encode("utf-8"), "text/plain")},
        data={"doc_type": "resume", "trust": "high"},
    )
    assert upload.status_code == 201

    client.app.state.llm = FakeLLM(json.dumps(ANSWER, ensure_ascii=False))
    response = client.post(
        "/v1/ask",
        headers=headers,
        json={"question": "账务平台年度可用性是多少？"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is True
    assert body["hit_path"] == "bm25"
    assert body["card"]["citations"]
    assert body["card"]["confidence"]["level"] == "yellow"
    assert body["card"]["l1"][0] == "年度可用性"


def test_ask_falls_back_without_valid_citations(api, auth):
    client, _ = api
    headers, _ = auth
    upload = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("resume.txt", TEXT.encode("utf-8"), "text/plain")},
        data={"doc_type": "resume", "trust": "high"},
    )
    assert upload.status_code == 201

    bad = dict(ANSWER)
    bad["answer"] = "资料不足，建议按兜底说。"
    bad["citations"] = [{"block": "b-0002", "quote": "不存在的句子"}]
    client.app.state.llm = FakeLLM(json.dumps(bad, ensure_ascii=False))
    response = client.post(
        "/v1/ask",
        headers=headers,
        json={"question": "账务平台年度可用性是多少？"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["card"]["confidence"]["level"] == "red"
    assert body["card"]["must_show_fallback_first"] is True


def test_ask_with_no_documents(api, auth):
    client, _ = api
    headers, _ = auth
    client.app.state.llm = FakeLLM(json.dumps(ANSWER, ensure_ascii=False))
    response = client.post(
        "/v1/ask",
        headers=headers,
        json={"question": "你最大的失败是什么？"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hit_path"] == "none"
    assert body["card"]["confidence"]["level"] == "red"


def test_ask_ungrounded_switch(api, auth):
    client, _ = api
    headers, _ = auth
    ungrounded = {
        "answer": "我最大的失败是一次上线前没有做回滚演练，之后补了预案。",
        "l1": ["回滚演练", "上线预案", "复盘"],
        "l2": [
            "我最大的失败是一次上线前没做回滚演练。",
            "后来我把回滚预案加进了发布清单。",
            "这条没有原文依据，具体细节要核对。",
        ],
        "fallback": "这条没有原文依据，先按通用理解说，具体口径要核对。",
    }
    client.app.state.llm = FakeLLM(json.dumps(ungrounded, ensure_ascii=False))
    response = client.post(
        "/v1/ask",
        headers=headers,
        json={
            "question": "你最大的失败是什么？",
            "allow_ungrounded": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ungrounded"] is True
    assert body["hit_path"] == "ungrounded"
    assert body["card"]["citations"] == []
    assert body["card"]["confidence"]["level"] == "red"
    assert body["card"]["l2"][0].startswith("我最大的失败")
