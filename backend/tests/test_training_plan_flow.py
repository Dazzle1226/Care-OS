from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import ChildProfile, DailyCheckin, IncidentLog, Review, TrainingSkillState, TrainingTaskFeedback


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "training-tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_training_dashboard_generation_reminder_and_feedback_loop(db_session: Session, seeded_family) -> None:
    profile = db_session.scalar(select(ChildProfile).where(ChildProfile.family_id == seeded_family.family_id))
    assert profile is not None
    profile.school_context = {
        "child_name": "小雨",
        "child_age": 8,
        "interests": ["地铁"],
        "likes": ["拼图"],
        "learning_needs": ["表达需求", "作业启动", "等待轮流"],
        "social_training": ["轮流游戏"],
        "emotion_patterns": ["焦虑时会躲起来"],
        "behavior_patterns": ["任务开始困难", "关屏时容易升级"],
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
        "today_activities": ["学校活动", "关屏"],
        "today_learning_tasks": ["语言练习", "作业训练"],
        "physical_discomforts": [],
    }
    recent_checkins[1].details_json = {
        "child_mood_state": "sensitive",
        "negative_emotions": ["担心"],
        "today_activities": ["学校活动", "排队"],
        "today_learning_tasks": ["语言练习"],
        "physical_discomforts": [],
    }

    incident = IncidentLog(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        triggers=["关屏", "出门"],
        selected_resources={},
        high_risk_flag=False,
        notes="关屏后切换困难",
    )
    db_session.add(incident)
    db_session.flush()
    db_session.add(
        Review(
            incident_id=incident.id,
            family_id=seeded_family.family_id,
            card_ids=["CARD-1"],
            outcome_score=0,
            child_state_after="partly_settled",
            caregiver_state_after="same",
            recommendation="adjust",
            notes="需要更低负担方案",
            followup_action="下次提前预告",
        )
    )
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
        assert generated["summary"]["priority_domain_count"] == 3
        assert generated["summary"]["current_load_level"] in {"light", "standard", "adaptive"}
        assert len(generated["priority_domains"]) == 3
        assert len(generated["today_tasks"]) >= 1
        assert any(item["area_key"] == "transition_flexibility" for item in generated["priority_domains"])

        first_task = generated["today_tasks"][0]
        assert any("地铁" in item for item in first_task["materials"] + [first_task["title"]])

        current_response = client.get(f"/api/training/current/{seeded_family.family_id}", headers=headers)
        assert current_response.status_code == 200
        current_payload = current_response.json()
        assert current_payload["summary"]["priority_domain_count"] == 3

        domain_response = client.get(
            f"/api/training/domain/{seeded_family.family_id}/{generated['priority_domains'][0]['area_key']}",
            headers=headers,
        )
        assert domain_response.status_code == 200
        domain_payload = domain_response.json()
        assert domain_payload["short_term_goal"]["title"]
        assert domain_payload["script_examples"]

        reminder_response = client.post(
            "/api/training/reminder",
            json={
                "family_id": seeded_family.family_id,
                "task_instance_id": first_task["task_instance_id"],
            },
            headers=headers,
        )
        assert reminder_response.status_code == 200
        reminder_payload = reminder_response.json()
        assert reminder_payload["task_instance_id"] == first_task["task_instance_id"]
        assert reminder_payload["reminder_status"] == "scheduled"

        feedback_response = client.post(
            "/api/training/feedback",
            json={
                "family_id": seeded_family.family_id,
                "task_instance_id": first_task["task_instance_id"],
                "completion_status": "partial",
                "child_response": "overloaded",
                "helpfulness": "not_helpful",
                "obstacle_tag": "too_hard",
                "notes": "开始两分钟后就想逃开。",
            },
            headers=headers,
        )
        assert feedback_response.status_code == 200
        feedback_payload = feedback_response.json()
        assert feedback_payload["feedback_id"] > 0
        assert "降级" in feedback_payload["adjustment_summary"] or "低负担" in feedback_payload["adjustment_summary"]
        assert feedback_payload["dashboard"]["recent_adjustments"]
        assert feedback_payload["dashboard"]["summary"]["priority_domain_count"] == 3

    stored_feedbacks = db_session.scalars(
        select(TrainingTaskFeedback).where(TrainingTaskFeedback.family_id == seeded_family.family_id)
    ).all()
    assert len(stored_feedbacks) == 1
    assert stored_feedbacks[0].task_instance_id == first_task["task_instance_id"]
    assert stored_feedbacks[0].difficulty_rating == "too_hard"
    assert stored_feedbacks[0].helpfulness == "not_helpful"


def test_training_domain_detail_recovers_when_reason_list_has_only_one_item(db_session: Session, seeded_family) -> None:
    profile = db_session.scalar(select(ChildProfile).where(ChildProfile.family_id == seeded_family.family_id))
    assert profile is not None
    profile.language_level = "short_sentence"
    profile.school_context = {
        "child_name": "小雨",
        "child_age": 8,
        "learning_needs": ["表达需求", "理解指令"],
        "behavior_patterns": ["关屏时容易升级"],
        "school_notes": "老师反馈需要更多功能性表达支持。",
    }
    db_session.commit()

    with TestClient(app) as client:
        headers = _auth_headers(client)
        generate_response = client.post(
            "/api/training/generate",
            json={"family_id": seeded_family.family_id, "extra_context": "最近在学校求助表达还是比较少。"},
            headers=headers,
        )
        assert generate_response.status_code == 200

        state = db_session.scalar(
            select(TrainingSkillState).where(
                TrainingSkillState.family_id == seeded_family.family_id,
                TrainingSkillState.area_key == "communication",
            )
        )
        assert state is not None

        state.reason_summary = "虽然已有短句表达，但在高压场景里仍需要更稳定的功能性沟通。"
        state.meta_json = {
            **(state.meta_json or {}),
            "reason_for_priority": [state.reason_summary],
        }
        db_session.commit()

        domain_response = client.get(
            f"/api/training/domain/{seeded_family.family_id}/communication",
            headers=headers,
        )
        assert domain_response.status_code == 200
        payload = domain_response.json()
        assert len(payload["reason_for_priority"]) >= 2
        assert payload["reason_for_priority"][0] == state.reason_summary
        assert any("档案" in item or "学校" in item or "短句" in item for item in payload["reason_for_priority"][1:])
