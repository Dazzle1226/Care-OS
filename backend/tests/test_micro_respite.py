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


def test_micro_respite_returns_three_low_stim_options(seeded_family) -> None:
    payload = {
        "family_id": seeded_family.family_id,
        "caregiver_stress": 9,
        "caregiver_sleep_quality": 3,
        "support_available": "none",
        "child_emotional_state": "escalating",
        "sensory_overload_level": "heavy",
        "transition_difficulty": 8,
        "meltdown_count": 3,
        "notes": "刚从学校回来，家里噪音比较大",
    }

    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post("/api/respite/generate", json=payload, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["blocked"] is False
    assert body["plan"]["low_stimulation_only"] is True
    assert len(body["plan"]["options"]) == 3
    assert all(option["low_stimulation_only"] for option in body["plan"]["options"])
    assert all(option["duration_minutes"] <= 15 for option in body["plan"]["options"])
    assert all(option["source_card_ids"] for option in body["plan"]["options"])


def test_micro_respite_high_risk_note_blocks(seeded_family) -> None:
    payload = {
        "family_id": seeded_family.family_id,
        "caregiver_stress": 6,
        "caregiver_sleep_quality": 5,
        "support_available": "one",
        "child_emotional_state": "fragile",
        "sensory_overload_level": "medium",
        "transition_difficulty": 6,
        "meltdown_count": 1,
        "notes": "孩子出现自伤风险，需要马上处理",
    }

    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post("/api/respite/generate", json=payload, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["blocked"] is True
    assert "高风险" in body["safety_block"]["block_reason"]


def test_micro_respite_feedback_updates_preference_weights(db_session: Session, seeded_family) -> None:
    generate_payload = {
        "family_id": seeded_family.family_id,
        "caregiver_stress": 5,
        "caregiver_sleep_quality": 6,
        "support_available": "one",
        "child_emotional_state": "fragile",
        "sensory_overload_level": "light",
        "transition_difficulty": 5,
        "meltdown_count": 1,
        "notes": "晚饭前想先喘口气",
    }

    with TestClient(app) as client:
        headers = _auth_headers(client)
        generate_response = client.post("/api/respite/generate", json=generate_payload, headers=headers)
        assert generate_response.status_code == 200
        option = generate_response.json()["plan"]["options"][0]

        feedback_response = client.post(
            "/api/respite/feedback",
            json={
                "family_id": seeded_family.family_id,
                "option_id": option["option_id"],
                "source_card_ids": option["source_card_ids"],
                "effectiveness": "helpful",
                "matched_expectation": True,
                "notes": "交接后状态恢复得不错",
            },
            headers=headers,
        )

    assert feedback_response.status_code == 200
    body = feedback_response.json()
    card_id = option["source_card_ids"][0]
    assert body["outcome_score"] == 2
    assert body["updated_weights"][card_id] > 0

    reviews = db_session.scalars(select(Review).where(Review.family_id == seeded_family.family_id)).all()
    assert len(reviews) == 1
    assert reviews[0].card_ids == option["source_card_ids"]
