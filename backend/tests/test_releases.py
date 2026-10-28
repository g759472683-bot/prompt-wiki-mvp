from __future__ import annotations


def test_admin_page(api):
    client, _ = api
    response = client.get("/admin")
    assert response.status_code == 200
    assert "运营台" in response.text


def test_release_upload_activate_and_latest(api, auth):
    client, _ = api
    headers, _ = auth

    missing = client.get("/v1/app/latest")
    assert missing.status_code == 404

    upload = client.post(
        "/v1/releases",
        headers=headers,
        files={"file": ("promptwiki.apk", b"PK\x03\x04fake-apk", "application/vnd.android.package-archive")},
        data={"version_code": "2", "version_name": "0.2.0", "notes": "batch + rag"},
    )
    assert upload.status_code == 200, upload.text
    release = upload.json()
    assert release["active"] is False
    assert release["download_url"].startswith("/v1/app/download/")

    activate = client.post(
        f"/v1/releases/{release['id']}/activate", headers=headers
    )
    assert activate.status_code == 200
    assert activate.json()["active"] is True

    latest = client.get("/v1/app/latest")
    assert latest.status_code == 200
    assert latest.json()["version_code"] == 2
    assert latest.json()["version_name"] == "0.2.0"

    download = client.get(f"/v1/app/download/{release['id']}")
    assert download.status_code == 200
    assert download.content.startswith(b"PK")
    assert download.headers["content-type"].startswith(
        "application/vnd.android.package-archive"
    )

    duplicate = client.post(
        "/v1/releases",
        headers=headers,
        files={"file": ("promptwiki.apk", b"PK\x03\x04x", "application/vnd.android.package-archive")},
        data={"version_code": "2", "version_name": "0.2.0"},
    )
    assert duplicate.status_code == 409
