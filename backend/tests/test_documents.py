from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "page.frontmatter.schema.json"

SAMPLE = (
    "林舟｜后端工程师｜8 年经验\n\n"
    "第二段：账务平台年度可用性 99.99%。\n对账延迟 P95 从 45 分钟降至 8 分钟。\n\n"
    "主导账务平台分库分表迁移，覆盖 12 个服务、日均 2.3 亿笔交易。"
)


def _upload(client, headers, *, name="resume.txt", text=SAMPLE, doc_type="resume", trust="high"):
    return client.post(
        "/v1/documents",
        headers=headers,
        files={"file": (name, text.encode("utf-8"), "text/plain")},
        data={"doc_type": doc_type, "trust": trust},
    )


def test_upload_txt_creates_source_page(api, auth):
    client, settings = api
    headers, user_id = auth

    response = _upload(client, headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "parsed"
    assert body["block_count"] == 3
    assert body["source_id"] == f"source:{body['id']}"
    assert body["duplicate"] is False

    source_path = (
        Path(settings.data_dir) / "users" / user_id / "wiki" / "sources" / f"{body['id']}.md"
    )
    assert source_path.exists()
    raw = source_path.read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    front_text = raw.split("---", 2)[1]
    front = yaml.safe_load(front_text)
    assert front["id"] == body["source_id"]
    assert front["type"] == "source"
    assert front["schema_version"] == "1.0"
    assert front["trust"] == "high"
    assert front["extraction"]["blocks"] == 3
    assert re.fullmatch(r"[a-f0-9]{64}", front["source"]["sha256"])
    assert "<!-- b-0001 | p.1 | chars:0-" in raw


def test_source_page_matches_contract(api, auth):
    client, settings = api
    headers, user_id = auth
    body = _upload(client, headers).json()

    raw = (
        Path(settings.data_dir)
        / "users"
        / user_id
        / "wiki"
        / "sources"
        / f"{body['id']}.md"
    ).read_text(encoding="utf-8")
    front = yaml.safe_load(raw.split("---", 2)[1])

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(front)


def test_blocks_and_quotes(api, auth):
    client, _ = api
    headers, _ = auth
    doc = _upload(client, headers).json()

    blocks = client.get(f"/v1/documents/{doc['id']}/blocks", headers=headers)
    assert blocks.status_code == 200
    assert len(blocks.json()) == 3
    assert blocks.json()[0]["block_id"] == "b-0001"

    exact = client.post(
        f"/v1/documents/{doc['id']}/quote",
        headers=headers,
        json={"block_id": "b-0002", "quote": "账务平台年度可用性 99.99%"},
    )
    assert exact.status_code == 200
    assert exact.json()["matched"] is True
    assert exact.json()["match_type"] == "exact"

    normalized = client.post(
        f"/v1/documents/{doc['id']}/quote",
        headers=headers,
        json={"block_id": "b-0002", "quote": "账务平台年度可用性 99.99%。 对账延迟"},
    )
    assert normalized.status_code == 200
    assert normalized.json()["matched"] is True
    assert normalized.json()["match_type"] == "normalized"

    missing = client.post(
        f"/v1/documents/{doc['id']}/quote",
        headers=headers,
        json={"block_id": "b-0002", "quote": "绝对不存在的句子"},
    )
    assert missing.status_code == 200
    assert missing.json()["matched"] is False

    source_block = client.get(
        f"/v1/sources/{doc['source_id']}/blocks/b-0001", headers=headers
    )
    assert source_block.status_code == 200
    assert source_block.json()["block_id"] == "b-0001"


def test_duplicate_upload_returns_existing_document(api, auth):
    client, _ = api
    headers, _ = auth
    first = _upload(client, headers).json()
    second = _upload(client, headers).json()
    assert second["id"] == first["id"]
    assert second["duplicate"] is True


def test_user_isolation(api, auth):
    client, _ = api
    headers, _ = auth
    doc = _upload(client, headers).json()

    other = client.post(
        "/v1/auth/device",
        json={"device_id": "dev-other-0001", "invite_code": "OTHER-CODE"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}

    assert client.get(f"/v1/documents/{doc['id']}", headers=other_headers).status_code == 404
    assert client.get(f"/v1/documents/{doc['id']}/blocks", headers=other_headers).status_code == 404


def test_reject_unsupported_type(api, auth):
    client, _ = api
    headers, _ = auth
    response = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        data={"doc_type": "other", "trust": "medium"},
    )
    assert response.status_code == 415


def test_reject_empty_file(api, auth):
    client, _ = api
    headers, _ = auth
    response = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"doc_type": "other", "trust": "medium"},
    )
    assert response.status_code == 422


def test_delete_then_reupload(api, auth):
    client, _ = api
    headers, _ = auth
    first = _upload(client, headers).json()

    deleted = client.delete(f"/v1/documents/{first['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/v1/documents/{first['id']}", headers=headers).status_code == 404

    second = _upload(client, headers).json()
    assert second["id"] != first["id"]
    assert second["status"] == "parsed"
