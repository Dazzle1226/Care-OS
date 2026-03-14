from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import MultimodalIngestion
from app.services.multimodal_file_parser import ExtractedMultimodalInput, MultimodalExtractionError, MultimodalFileParser
from app.services.llm_client import LLMClient, LLMUnavailableError


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "multimodal-files", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_document_file_upload_returns_ingestion_response(
    db_session: Session,
    seeded_family,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MultimodalFileParser,
        "extract_document",
        lambda self, **_: ExtractedMultimodalInput(
            family_id=seeded_family.family_id,
            source_type="document",
            content_name="校方通知.png",
            raw_text="学校通知：明天改到操场活动，需要家长签字。",
            confidence=0.82,
            manual_review_required=False,
            meta={"source": "vision_model", "filename": "notice.png"},
        ),
    )

    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/v2/ingestions/document-file",
            headers=headers,
            data={"family_id": str(seeded_family.family_id), "content_name": "校方通知"},
            files={"file": ("notice.png", b"fake-image", "image/png")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "document"
    assert body["content_name"] == "校方通知.png"
    row = db_session.scalar(select(MultimodalIngestion).where(MultimodalIngestion.id == body["ingestion_id"]))
    assert row is not None
    assert row.raw_excerpt == "学校通知：明天改到操场活动，需要家长签字。"
    assert "fake-image" not in row.raw_excerpt


def test_audio_file_upload_returns_clear_error_on_parse_failure(
    db_session: Session,
    seeded_family,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MultimodalFileParser,
        "extract_audio",
        lambda self, **_: (_ for _ in ()).throw(MultimodalExtractionError("音频解析失败，请改用手动粘贴语音摘要。")),
    )

    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/v2/ingestions/audio-file",
            headers=headers,
            data={"family_id": str(seeded_family.family_id)},
            files={"file": ("scene.m4a", b"fake-audio", "audio/m4a")},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "音频解析失败，请改用手动粘贴语音摘要。"


def test_audio_file_upload_returns_ingestion_response(
    db_session: Session,
    seeded_family,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MultimodalFileParser,
        "extract_audio",
        lambda self, **_: ExtractedMultimodalInput(
            family_id=seeded_family.family_id,
            source_type="audio",
            content_name="现场语音.m4a",
            raw_text="现场太吵，我很累，他一直说不要走。",
            confidence=0.71,
            manual_review_required=False,
            meta={"source": "audio_model", "filename": "scene.m4a"},
        ),
    )

    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/v2/ingestions/audio-file",
            headers=headers,
            data={"family_id": str(seeded_family.family_id), "content_name": "现场语音"},
            files={"file": ("scene.m4a", b"fake-audio", "audio/m4a")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "audio"
    assert body["content_name"] == "现场语音.m4a"


def test_document_image_upload_degrades_gracefully_when_vision_parse_fails(
    db_session: Session,
    seeded_family,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        LLMClient,
        "generate_multimodal_json",
        lambda self, **_: (_ for _ in ()).throw(LLMUnavailableError("vision provider rejected image payload")),
    )

    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/v2/ingestions/document-file",
            headers=headers,
            data={"family_id": str(seeded_family.family_id), "content_name": "校方通知"},
            files={"file": ("notice.png", b"fake-image", "image/png")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "document"
    assert body["manual_review_required"] is True
    assert body["confidence"] == 0.2
    assert "已上传图片文档《校方通知》" in body["raw_excerpt"]


def test_llm_client_extracts_json_from_markdown_wrapped_multimodal_output() -> None:
    payload = LLMClient._extract_json_payload(
        """```json
{"raw_text":"学校通知：明天改到操场活动。","confidence":0.84,"manual_review_required":false}
```"""
    )

    assert payload["raw_text"] == "学校通知：明天改到操场活动。"
    assert payload["confidence"] == 0.84


def test_v2_friction_support_trace_keeps_uploaded_ingestion_ids(
    db_session: Session,
    seeded_family,
) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        ingestion = client.post(
            "/api/v2/ingestions/document",
            json={
                "family_id": seeded_family.family_id,
                "source_type": "document",
                "content_name": "学校通知",
                "raw_text": "学校通知：今天临时改教室，下午还有额外作业。",
            },
            headers=headers,
        )
        assert ingestion.status_code == 200
        ingestion_id = ingestion.json()["ingestion_id"]

        response = client.post(
            "/api/v2/scripts/friction-support",
            json={
                "family_id": seeded_family.family_id,
                "quick_preset": "transition_now",
                "ingestion_ids": [ingestion_id],
            },
            headers=headers,
        )

        assert response.status_code == 200
        body = response.json()
        trace = client.get(f"/api/decision-trace/{body['trace_id']}", headers=headers)
        assert trace.status_code == 200
        assert trace.json()["entry_signal_ids"] == [ingestion_id]
