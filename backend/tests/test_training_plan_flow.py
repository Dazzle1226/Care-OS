from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import ChildProfile, DailyCheckin, TrainingTaskFeedback


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "training-tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_training_plan_generation_and_feedback_loop(db_session: Session, seeded_family) -> None:
    profile = db_session.scalar(select(ChildProfile).where(ChildProfile.family_id == seeded_family.family_id))
    assert profile is not None
    profile.school_context = {
        "child_name": "小雨",
        "child_age": 8,
        "interests": ["地铁"],
        "likes": ["拼图"],
        "learning_needs": ["表达需求", "作业启动"],
        "social_training": ["轮流游戏"],
        "emotion_patterns": ["焦虑时会躲起来"],
        "behavior_patterns": ["任务开始困难"],
        "available_supporters": ["爸爸"],
        "school_notes": "入园前切换困难，作业开始也容易卡住",
    }

    recent_checkins = db_session.scalars(
        select(DailyCheckin)
        .where(DailyCheckin.family_id == seeded_family.family_id)
        .order_by(DailyCheckin.date.desc())
    ).all()
    assert len(recent_checkins) >= 2
    recent_checkins[0].details_json = {
        "child_mood_state": "anxious",
        "negative_emotions": ["焦虑"],
        "today_activities": ["学校活动"],
        "today_learning_tasks": ["语言练习", "作业训练"],
        "physical_discomforts": [],
    }
    recent_checkins[1].details_json = {
        "child_mood_state": "sensitive",
        "negative_emotions": ["担心"],
        "today_activities": ["学校活动"],
        "today_learning_tasks": ["语言练习"],
        "physical_discomforts": [],
    }
    db_session.commit()

    with TestClient(app) as client:
        headers = _auth_headers(client)

        generate_response = client.post(
            "/api/training/generate",
            json={
                "family_id": seeded_family.family_id,
                "extra_context": "最近入园前会躲到桌下，需要更容易开始的方案。",
            },
            headers=headers,
        )
        assert generate_response.status_code == 200
        generated = generate_response.json()
        assert generated["family_id"] == seeded_family.family_id
        assert generated["child_summary"].startswith("小雨")
        assert "最近入园前会躲到桌下" in generated["plan_summary"]
        assert len(generated["focus_areas"]) == 3
        assert len(generated["daily_tasks"]) == 3
        assert any(
            "地铁" in item
            for task in generated["daily_tasks"]
            for item in task["materials"] + [task["title"]]
        )

        first_task = generated["daily_tasks"][0]
        feedback_response = client.post(
            "/api/training/feedback",
            json={
                "family_id": seeded_family.family_id,
                "task_key": first_task["task_key"],
                "task_title": first_task["title"],
                "area_key": first_task["area_key"],
                "completion_status": "partial",
                "child_response": "overloaded",
                "difficulty_rating": "too_hard",
                "effect_score": 4,
                "parent_confidence": 4,
                "notes": "开始两分钟后就想逃开。",
            },
            headers=headers,
        )
        assert feedback_response.status_code == 200
        feedback_payload = feedback_response.json()
        assert feedback_payload["feedback_id"] > 0
        assert "8 分钟" in feedback_payload["next_adjustment"]
        assert "近 7 天共记录 1 次训练打卡" in feedback_payload["progress_summary"]
        assert feedback_payload["plan"]["recent_feedbacks"][0]["task_key"] == first_task["task_key"]

    stored_feedbacks = db_session.scalars(
        select(TrainingTaskFeedback).where(TrainingTaskFeedback.family_id == seeded_family.family_id)
    ).all()
    assert len(stored_feedbacks) == 1
    assert stored_feedbacks[0].task_key == first_task["task_key"]
    assert stored_feedbacks[0].difficulty_rating == "too_hard"
