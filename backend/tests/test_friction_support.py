from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Review


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_friction_support_generate_and_feedback(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        generate_response = client.post(
            "/api/scripts/friction-support",
            json={
                "family_id": seeded_family.family_id,
                "scenario": "transition",
                "child_state": "sensory_overload",
                "sensory_overload_level": "heavy",
                "transition_difficulty": 9,
                "meltdown_count": 2,
                "caregiver_stress": 8,
                "caregiver_fatigue": 7,
                "caregiver_sleep_quality": 4,
                "support_available": "one",
                "confidence_to_follow_plan": 4,
                "env_changes": ["学校临时活动", "刚到家"],
                "free_text": "孩子回家后不愿换衣服，声音一大就开始尖叫。",
                "high_risk_selected": False,
            },
            headers=headers,
        )

        assert generate_response.status_code == 200
        generated = generate_response.json()
        assert generated["blocked"] is False
        assert generated["incident_id"] > 0
        assert generated["risk"]["risk_level"] in {"green", "yellow", "red"}
        assert len(generated["support"]["action_plan"]) == 3
        assert len(generated["support"]["voice_guidance"]) == 3
        assert len(generated["support"]["exit_plan"]) == 3
        assert generated["support"]["school_message"]
        assert len(generated["support"]["source_card_ids"]) >= 1

        feedback_response = client.post(
            "/api/scripts/friction-support/feedback",
            json={
                "family_id": seeded_family.family_id,
                "incident_id": generated["incident_id"],
                "source_card_ids": generated["support"]["source_card_ids"],
                "effectiveness": "somewhat",
                "child_state_after": "partly_settled",
                "caregiver_state_after": "calmer",
                "notes": "孩子愿意进安静角落，但还不太愿意继续过渡。",
            },
            headers=headers,
        )

        assert feedback_response.status_code == 200
        feedback = feedback_response.json()
        assert feedback["incident_id"] == generated["incident_id"]
        assert feedback["outcome_score"] >= -2
        assert feedback["outcome_score"] <= 2
        assert feedback["next_adjustment"]
        assert isinstance(feedback["updated_weights"], dict)

    reviews = db_session.scalars(select(Review).where(Review.incident_id == generated["incident_id"])).all()
    assert len(reviews) == 1
    assert reviews[0].followup_action
