from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import DailyCheckin
from app.schemas.domain import CheckinCreate


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
        assert created["today_one_thing"] == "今天只保一个关键过渡"
        assert created["action_plan"]["headline"] == "先把最难的那个过渡单独做完"
        assert len(created["action_plan"]["reminders"]) == 2
        assert created["action_plan"]["reminders"][0]["title"] == "不要连续催促或临时加码"
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
        assert len(ready["action_plan"]["reminders"]) == 2

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


def test_daily_checkin_schema_accepts_legacy_payload_without_optional_defaults() -> None:
    legacy_payload = {
        "family_id": 3,
        "date": (date.today() + timedelta(days=2)).isoformat(),
        "child_sleep_hours": 8,
        "sensory_overload_level": "light",
        "meltdown_count": 0,
        "caregiver_stress": 4,
        "support_available": "one",
        "caregiver_sleep_quality": 6,
    }

    parsed = CheckinCreate.model_validate(legacy_payload)
    assert parsed.child_sleep_quality is None
    assert parsed.transition_difficulty is None
    assert parsed.child_mood_state == "stable"


def test_daily_checkin_optional_scores_can_be_skipped(db_session: Session, seeded_family) -> None:
    target_date = date.today() + timedelta(days=3)

    with TestClient(app) as client:
        headers = _auth_headers(client)
        payload = {
            "family_id": seeded_family.family_id,
            "date": target_date.isoformat(),
            "child_sleep_hours": 7,
            "sensory_overload_level": "light",
            "meltdown_count": 0,
            "child_mood_state": "stable",
            "caregiver_stress": 5,
            "support_available": "one",
            "caregiver_sleep_quality": 6,
        }

        response = client.post("/api/checkin", json=payload, headers=headers)
        assert response.status_code == 200

        created = response.json()
        assert created["checkin"]["child_sleep_quality"] is None
        assert created["checkin"]["transition_difficulty"] is None

    stored = db_session.scalar(
        select(DailyCheckin).where(
            DailyCheckin.family_id == seeded_family.family_id,
            DailyCheckin.date == target_date,
        )
    )
    assert stored is not None
    assert stored.transition_difficulty == 6
    assert stored.details_json["child_sleep_quality"] is None
    assert stored.details_json["transition_difficulty"] is None


def test_daily_checkin_focus_copy_uses_low_capacity_fallback(db_session: Session, seeded_family) -> None:
    target_date = date.today() + timedelta(days=4)

    with TestClient(app) as client:
        headers = _auth_headers(client)
        payload = {
            "family_id": seeded_family.family_id,
            "date": target_date.isoformat(),
            "child_sleep_hours": 4,
            "sensory_overload_level": "light",
            "meltdown_count": 0,
            "child_mood_state": "low_energy",
            "caregiver_stress": 8,
            "support_available": "none",
            "caregiver_sleep_quality": 3,
        }

        response = client.post("/api/checkin", json=payload, headers=headers)
        assert response.status_code == 200

        created = response.json()
        assert created["today_one_thing"] == "今天先减负，只保最低目标"
        assert created["action_plan"]["headline"] == "先砍掉非必要任务，保住配合"
        assert len(created["action_plan"]["reminders"]) == 2
        assert created["action_plan"]["reminders"][1]["body"] == "支持不足时先停一项任务，换成安静短流程。"
