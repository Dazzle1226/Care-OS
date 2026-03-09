from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import DailyCheckin


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_daily_checkin_status_and_same_day_update(db_session: Session, seeded_family) -> None:
    target_date = date.today() + timedelta(days=1)

    with TestClient(app) as client:
        headers = _auth_headers(client)

        status_response = client.get(
            f"/api/checkin/today/{seeded_family.family_id}",
            params={"date": target_date.isoformat()},
            headers=headers,
        )
        assert status_response.status_code == 200
        assert status_response.json()["needs_checkin"] is True

        payload = {
            "family_id": seeded_family.family_id,
            "date": target_date.isoformat(),
            "child_sleep_hours": 7,
            "child_sleep_quality": 4,
            "sleep_issues": ["夜醒"],
            "sensory_overload_level": "medium",
            "meltdown_count": 2,
            "child_mood_state": "anxious",
            "physical_discomforts": ["肠胃不适"],
            "aggressive_behaviors": ["哭闹"],
            "negative_emotions": ["焦虑"],
            "transition_difficulty": 8,
            "caregiver_stress": 8,
            "support_available": "one",
            "caregiver_sleep_quality": 4,
            "today_activities": ["医生预约"],
            "today_learning_tasks": ["行为训练"],
        }
        create_response = client.post("/api/checkin", json=payload, headers=headers)
        assert create_response.status_code == 200

        created = create_response.json()
        assert created["checkin"]["date"] == target_date.isoformat()
        assert created["checkin"]["child_sleep_quality"] == 4
        assert created["checkin"]["caregiver_sleep_quality"] == 4
        assert created["checkin"]["child_mood_state"] == "anxious"
        assert created["checkin"]["today_activities"] == ["医生预约"]
        assert len(created["action_plan"]["three_step_action"]) == 3
        assert len(created["action_plan"]["meltdown_fallback"]) == 3
        assert created["action_plan"]["parent_phrase"]

        ready_response = client.get(
            f"/api/checkin/today/{seeded_family.family_id}",
            params={"date": target_date.isoformat()},
            headers=headers,
        )
        assert ready_response.status_code == 200
        ready = ready_response.json()
        assert ready["needs_checkin"] is False
        assert ready["checkin"]["checkin_id"] == created["checkin_id"]
        assert ready["action_plan"]["headline"]

        update_payload = payload | {
            "caregiver_stress": 6,
            "caregiver_sleep_quality": 7,
            "meltdown_count": 1,
            "today_learning_tasks": ["语言练习"],
        }
        update_response = client.post("/api/checkin", json=update_payload, headers=headers)
        assert update_response.status_code == 200

        updated = update_response.json()
        assert updated["checkin_id"] == created["checkin_id"]
        assert updated["checkin"]["caregiver_stress"] == 6
        assert updated["checkin"]["caregiver_sleep_quality"] == 7
        assert updated["checkin"]["today_learning_tasks"] == ["语言练习"]

    same_day_checkins = db_session.scalars(
        select(DailyCheckin).where(
            DailyCheckin.family_id == seeded_family.family_id,
            DailyCheckin.date == target_date,
        )
    ).all()
    assert len(same_day_checkins) == 1
    assert same_day_checkins[0].caregiver_stress == 6
    assert same_day_checkins[0].caregiver_sleep_hours == 7
    assert same_day_checkins[0].details_json["today_learning_tasks"] == ["语言练习"]
