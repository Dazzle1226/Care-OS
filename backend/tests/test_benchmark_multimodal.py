from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "benchmark-multimodal", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_benchmark_multimodal_ingestion_and_latest_report(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)

        document = client.post(
            "/api/v2/ingestions/document",
            json={
                "family_id": seeded_family.family_id,
                "source_type": "document",
                "content_name": "学校通知",
                "raw_text": "学校通知：明天调整到操场活动，作业两项，需要家长签字。",
            },
            headers=headers,
        )
        assert document.status_code == 200
        document_body = document.json()
        assert document_body["context_signals"]

        audio = client.post(
            "/api/v2/ingestions/audio",
            json={
                "family_id": seeded_family.family_id,
                "source_type": "audio",
                "content_name": "现场语音",
                "raw_text": "现场太吵，我很累，他一直说不要走，我有点撑不住。",
            },
            headers=headers,
        )
        assert audio.status_code == 200
        audio_body = audio.json()
        assert audio_body["context_signals"]

        benchmark = client.get("/api/v2/benchmarks/latest", headers=headers)
        assert benchmark.status_code == 200
        benchmark_body = benchmark.json()
        categories = {item["category"] for item in benchmark_body["metrics"]}
        assert {"retrieval", "orchestration", "policy_learning", "multimodal"}.issubset(categories)
        assert any(item["name"] == "signal_extraction_accuracy" for item in benchmark_body["metrics"])
