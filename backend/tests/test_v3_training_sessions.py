from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import ChildProfile, DailyCheckin, FamilyPolicyWeight


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "v3-training-runner", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _stabilize_checkins(db_session: Session, family_id: int) -> None:
    rows = db_session.scalars(select(DailyCheckin).where(DailyCheckin.family_id == family_id)).all()
    for item in rows:
        item.meltdown_count = 0
        item.transition_difficulty = 4.0
        item.sensory_overload_level = "light"
        item.caregiver_stress = 4.0
        item.caregiver_sleep_hours = 7.5
        item.support_available = "one"
        item.details_json = {
            "child_mood_state": "stable",
            "negative_emotions": [],
            "today_activities": ["学校活动"],
            "today_learning_tasks": ["语言练习"],
            "physical_discomforts": [],
        }


def test_v3_training_session_start_and_replan(db_session: Session, seeded_family) -> None:
    profile = db_session.scalar(select(ChildProfile).where(ChildProfile.family_id == seeded_family.family_id))
    assert profile is not None
    profile.school_context = {
        "child_name": "小雨",
        "child_age": 8,
        "learning_needs": ["表达需求", "任务启动"],
        "behavior_patterns": ["任务开始困难"],
        "emotion_patterns": ["焦虑时会躲起来"],
        "available_supporters": ["爸爸"],
        "school_notes": "最近仍需要更容易开始的任务。",
    }
    _stabilize_checkins(db_session, seeded_family.family_id)
    db_session.commit()

    with TestClient(app) as client:
        headers = _auth_headers(client)
        start = client.post(
            "/api/v3/training-sessions/start",
            json={
                "family_id": seeded_family.family_id,
                "extra_context": "今天想先试一个能容易开始的训练。",
                "ingestion_ids": [],
            },
            headers=headers,
        )
        assert start.status_code == 200
        start_body = start.json()
        assert start_body["session"]["chain"] == "training_support"
        assert start_body["decision_state"]["chain"] == "training_support"
        assert start_body["dashboard"]["summary"]["readiness_status"] in {"ready", "lighter"}
        assert start_body["coordination"]["now_step"]

        event = client.post(
            f"/api/v3/training-sessions/{start_body['session']['session_id']}/events",
            json={
                "source_type": "user_action",
                "event_kind": "request_lighter",
                "raw_text": "今天我比较累，想更轻一点。",
            },
            headers=headers,
        )
        assert event.status_code == 200
        event_body = event.json()
        assert event_body["session"]["current_state_version"] == 2
        assert event_body["decision_state"]["state_version"] == 2
        assert event_body["coordination"]["active_mode"] in {"lighter", "blocked"}


def test_v3_training_session_close_records_learning(db_session: Session, seeded_family) -> None:
    profile = db_session.scalar(select(ChildProfile).where(ChildProfile.family_id == seeded_family.family_id))
    assert profile is not None
    profile.school_context = {
        "child_name": "小雨",
        "child_age": 8,
        "learning_needs": ["表达需求"],
        "behavior_patterns": ["任务开始困难"],
        "available_supporters": ["爸爸"],
    }
    _stabilize_checkins(db_session, seeded_family.family_id)
    db_session.commit()

    with TestClient(app) as client:
        headers = _auth_headers(client)
        start = client.post(
            "/api/v3/training-sessions/start",
            json={
                "family_id": seeded_family.family_id,
                "extra_context": "今天先试一个短练习。",
                "ingestion_ids": [],
            },
            headers=headers,
        )
        session_id = start.json()["session"]["session_id"]
        close = client.post(
            f"/api/v3/training-sessions/{session_id}/close",
            json={
                "effectiveness": "helpful",
                "notes": "压成一步后更容易开始。",
            },
            headers=headers,
        )
        assert close.status_code == 200
        close_body = close.json()
        assert close_body["session"]["status"] == "closed"
        assert close_body["learning_summary"]

    rows = db_session.scalars(
        select(FamilyPolicyWeight).where(
            FamilyPolicyWeight.family_id == seeded_family.family_id,
            FamilyPolicyWeight.target_kind.in_(["emotion_pattern", "successful_adjustment"]),
        )
    ).all()
    assert rows
