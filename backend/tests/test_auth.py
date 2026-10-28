from __future__ import annotations


def test_health(api):
    client, settings = api
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["env"] == "test"
    assert settings.max_upload_mb == 20


def test_invalid_invite(api):
    client, _ = api
    response = client.post(
        "/v1/auth/device",
        json={"device_id": "dev-test-0002", "invite_code": "NOPE"},
    )
    assert response.status_code == 403


def test_auth_is_idempotent_for_same_device(api):
    client, _ = api
    payload = {"device_id": "dev-test-0003", "invite_code": "TEST-CODE"}
    first = client.post("/v1/auth/device", json=payload)
    second = client.post("/v1/auth/device", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["user_id"] == second.json()["user_id"]
    assert first.json()["token"] != second.json()["token"]  # fresh exp/iat


def test_missing_token(api):
    client, _ = api
    response = client.get("/v1/documents")
    assert response.status_code == 401


def test_same_invite_shares_workspace_across_devices(api):
    client, _ = api
    first = client.post(
        "/v1/auth/device",
        json={"device_id": "dev-phone-0001", "invite_code": "TEST-CODE", "name": "手机"},
    ).json()
    second = client.post(
        "/v1/auth/device",
        json={"device_id": "dev-web-0001", "invite_code": "TEST-CODE", "name": "电脑"},
    ).json()
    assert first["user_id"] == second["user_id"]

    headers = {"Authorization": f"Bearer {first['token']}"}
    upload = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("resume.txt", "第一段\n\n第二段".encode(), "text/plain")},
        data={"doc_type": "resume", "trust": "high"},
    )
    assert upload.status_code == 201

    other_headers = {"Authorization": f"Bearer {second['token']}"}
    docs = client.get("/v1/documents", headers=other_headers)
    assert docs.status_code == 200
    assert any(doc["id"] == upload.json()["id"] for doc in docs.json())


def test_different_invite_is_separate_workspace(api):
    client, _ = api
    first = client.post(
        "/v1/auth/device",
        json={"device_id": "dev-a-0001", "invite_code": "TEST-CODE"},
    ).json()
    second = client.post(
        "/v1/auth/device",
        json={"device_id": "dev-b-0001", "invite_code": "OTHER-CODE"},
    ).json()
    assert first["user_id"] != second["user_id"]
