from __future__ import annotations

import yaml

from app.models import Document


def _page(title: str, value: str, source: str) -> str:
    front = {
        "id": f"metric:{title.replace(' ', '-').lower()}",
        "type": "metric",
        "title": title,
        "status": "active",
        "metric": {"key": "availability", "name": title, "value": value},
        "evidence": [
            {
                "source": source,
                "source_version": 1,
                "block": "b-0001",
                "quote": f"{title} {value}",
            }
        ],
    }
    return "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n\n# " + title + "\n"


def test_cross_document_metric_conflict(api, auth):
    client, settings = api
    headers, user_id = auth
    wiki = settings.data_dir / "users" / user_id / "wiki"
    metrics = wiki / "pages" / "metric"
    metrics.mkdir(parents=True, exist_ok=True)

    with client.app.state.sessionmaker() as session:
        for index, name in (("a", "doc-a.pdf"), ("b", "doc-b.pdf")):
            session.add(
                Document(
                    id=f"doc-{index}",
                    user_id=user_id,
                    filename=name,
                    mime="text/plain",
                    doc_type="resume",
                    trust="high",
                    sha256="0" * 64,
                    size_bytes=10,
                    status="parsed",
                    source_id=f"source:doc-{index}",
                )
            )
        session.commit()

    (metrics / "availability-a.md").write_text(
        _page("系统可用性 A", "99.95%", "source:doc-a"), encoding="utf-8"
    )
    (metrics / "availability-b.md").write_text(
        _page("系统可用性 B", "99.99%", "source:doc-b"), encoding="utf-8"
    )

    response = client.get("/v1/consistency", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["high"] == 1
    assert body["conflicts"][0]["type"] == "metric_value"
    assert {item["value"] for item in body["conflicts"][0]["values"]} == {
        "99.95%",
        "99.99%",
    }
