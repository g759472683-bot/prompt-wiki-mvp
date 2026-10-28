from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def api(tmp_path) -> Iterator[tuple[TestClient, Settings]]:
    settings = Settings(
        env="test",
        secret_key="test-secret-0123456789abcdef0123456789",
        invite_codes="TEST-CODE,OTHER-CODE",
        data_dir=tmp_path / "data",
        database_url=None,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, settings


@pytest.fixture()
def auth(api) -> tuple[dict[str, str], str]:
    client, _ = api
    response = client.post(
        "/v1/auth/device",
        json={"device_id": "dev-test-0001", "invite_code": "TEST-CODE", "name": "林舟"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user_id"]
