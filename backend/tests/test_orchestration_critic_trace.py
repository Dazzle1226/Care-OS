from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "trace-runner", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_plan_generation_persists_blocked_trace(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/plan48h/generate",
            json={
                "family_id": seeded_family.family_id,
                "context": "manual",
                "scenario": "transition",
                "manual_trigger": True,
                "high_risk_selected": True,
                "free_text": "已经出现自伤风险",
                "include_debug": True,
            },
            headers=headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["blocked"] is True
        assert body["decision_trace_id"] is not None
        assert body["evidence_bundle"]["selected_card_ids"]

        trace = client.get(f"/api/decision-trace/{body['decision_trace_id']}", headers=headers)
        assert trace.status_code == 200
        trace_body = trace.json()
        assert trace_body["final_status"] == "blocked"
        assert trace_body["safety_review"]["blocked"] is True
        assert trace_body["evidence_review"]["blocked"] is False
        assert trace_body["fallback_reason"]

