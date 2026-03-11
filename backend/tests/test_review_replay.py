from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "review-replay", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_review_replay_supports_lightweight_manual_review(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)

        create_response = client.post(
            "/api/review",
            json={
                "family_id": seeded_family.family_id,
                "scenario": "transition",
                "intensity": "medium",
                "triggers": ["等待", "回家"],
                "card_ids": [],
                "outcome_score": 1,
                "child_state_after": "partly_settled",
                "caregiver_state_after": "same",
                "recommendation": "continue",
                "response_action": "先预告两分钟，再把要求缩成一句话。",
                "notes": "这次没记卡片，只先记结果。",
            },
            headers=headers,
        )

        assert create_response.status_code == 200
        created = create_response.json()

        replay_response = client.get(f"/api/replay/{created['incident_id']}", headers=headers)

    assert replay_response.status_code == 200
    body = replay_response.json()
    assert body["incident_id"] == created["incident_id"]
    assert body["strategy_titles"] == ["先预告两分钟，再把要求缩成一句话。", "手动记录（未绑定策略卡）"]
    assert [item["label"] for item in body["timeline"]] == ["触发器", "策略", "结果", "下次改进"]
    assert body["timeline"][1]["value"] == "先预告两分钟，再把要求缩成一句话。"
    assert body["next_improvement"]
