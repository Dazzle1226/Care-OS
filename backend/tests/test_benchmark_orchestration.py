from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "benchmark-orchestrator", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_benchmark_orchestration_v2_returns_full_stage_graph(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/v2/plan48h/generate",
            json={
                "family_id": seeded_family.family_id,
                "context": "manual",
                "scenario": "transition",
                "manual_trigger": True,
                "high_risk_selected": False,
                "free_text": "学校通知说明今天过渡更难，需要先预告。",
                "include_debug": True,
                "ingestion_ids": [],
            },
            headers=headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["trace_id"] is not None
        assert len(body["stage_summaries"]) == 8
        assert [item["stage"] for item in body["stage_summaries"]] == [
            "context_ingestion",
            "signal_eval",
            "evidence_recall",
            "candidate_generation",
            "safety_critic",
            "evidence_critic",
            "policy_adjust_hint",
            "finalizer",
        ]

        trace_response = client.get(f"/api/decision-trace/{body['trace_id']}", headers=headers)
        assert trace_response.status_code == 200
        trace_body = trace_response.json()
        assert trace_body["graph_version"] == "v2"
        assert len(trace_body["stage_runs"]) == 8
        assert trace_body["final_status"] in {"success", "fallback"}
