from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import FamilyPolicyWeight


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "v3-friction-runner", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_v3_friction_session_start_and_replan(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        start = client.post(
            "/api/v3/friction-sessions/start",
            json={
                "family_id": seeded_family.family_id,
                "scenario": "transition",
                "child_state": "transition_block",
                "sensory_overload_level": "medium",
                "transition_difficulty": 8,
                "meltdown_count": 2,
                "caregiver_stress": 8,
                "caregiver_fatigue": 8,
                "caregiver_sleep_quality": 4,
                "support_available": "one",
                "confidence_to_follow_plan": 3,
                "env_changes": ["放学", "切换衣服"],
                "free_text": "刚回家就卡住了，我快跟不上了。",
                "ingestion_ids": [],
            },
            headers=headers,
        )

        assert start.status_code == 200
        start_body = start.json()
        assert start_body["blocked"] is False
        assert start_body["session"]["status"] == "active"
        assert start_body["emotion"]["caregiver_overload_level"] in {"medium", "high"}
        assert {item["stage"] for item in start_body["trace_summary"]} >= {
            "emotion_eval",
            "coordination",
            "task_decomposition",
            "critic_reflection",
            "executor",
        }
        assert start_body["plan_revision"]["revision_no"] == 1
        assert start_body["active_task"]["task_id"]
        assert {item["task_id"] for item in start_body["task_tree"]} >= {"task-now", "task-fallback", "task-exit"}
        assert start_body["execution_state"]["active_task_id"] == start_body["active_task"]["task_id"]

        event = client.post(
            f"/api/v3/friction-sessions/{start_body['session']['session_id']}/events",
            json={
                "source_type": "user_action",
                "event_kind": "request_lighter",
                "raw_text": "还是不肯动，我真的撑不住了。",
            },
            headers=headers,
        )

        assert event.status_code == 200
        event_body = event.json()
        assert event_body["replanned"] is True
        assert event_body["session"]["current_state_version"] == 2
        assert event_body["coordination"]["active_mode"] == "lighter"
        assert event_body["trace_id"] != start_body["trace_id"]
        assert event_body["plan_revision"]["revision_no"] == 2
        assert event_body["revision_diff"]["active_task_before"] == start_body["active_task"]["task_id"]
        assert event_body["execution_state"]["active_mode"] == "lighter"
        assert event_body["active_task"]["task_id"] == "task-fallback"

        no_improvement = client.post(
            f"/api/v3/friction-sessions/{start_body['session']['session_id']}/events",
            json={
                "source_type": "user_action",
                "event_kind": "no_improvement",
                "raw_text": "执行后还是没改善。",
            },
            headers=headers,
        )
        assert no_improvement.status_code == 200
        no_improvement_body = no_improvement.json()
        assert no_improvement_body["replanned"] is True
        assert no_improvement_body["revision_diff"]["trigger"]["trigger_type"] == "no_improvement"
        assert no_improvement_body["execution_state"]["failed_task_ids"]


def test_v3_friction_session_support_arrived_switches_to_handoff_branch(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        start = client.post(
            "/api/v3/friction-sessions/start",
            json={
                "family_id": seeded_family.family_id,
                "scenario": "transition",
                "child_state": "transition_block",
                "sensory_overload_level": "medium",
                "transition_difficulty": 7,
                "meltdown_count": 1,
                "caregiver_stress": 7,
                "caregiver_fatigue": 7,
                "caregiver_sleep_quality": 5,
                "support_available": "one",
                "confidence_to_follow_plan": 4,
                "env_changes": ["放学"],
                "free_text": "先试着稳住。",
                "ingestion_ids": [],
            },
            headers=headers,
        )

        session_id = start.json()["session"]["session_id"]
        event = client.post(
            f"/api/v3/friction-sessions/{session_id}/events",
            json={
                "source_type": "user_action",
                "event_kind": "support_arrived",
                "raw_text": "爸爸已经到场，可以接手。",
            },
            headers=headers,
        )

        assert event.status_code == 200
        body = event.json()
        assert body["replanned"] is True
        assert body["coordination"]["active_mode"] == "handoff"
        assert body["revision_diff"]["trigger"]["trigger_type"] == "support_arrived"
        assert body["active_task"]["task_id"] == "task-handoff"


def test_v3_friction_session_close_records_learning(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        start = client.post(
            "/api/v3/friction-sessions/start",
            json={
                "family_id": seeded_family.family_id,
                "scenario": "transition",
                "child_state": "transition_block",
                "sensory_overload_level": "medium",
                "transition_difficulty": 8,
                "meltdown_count": 1,
                "caregiver_stress": 7,
                "caregiver_fatigue": 7,
                "caregiver_sleep_quality": 4,
                "support_available": "one",
                "confidence_to_follow_plan": 4,
                "env_changes": ["放学"],
                "free_text": "先试一版高摩擦支持。",
                "ingestion_ids": [],
            },
            headers=headers,
        )
        session_id = start.json()["session"]["session_id"]

        close = client.post(
            f"/api/v3/friction-sessions/{session_id}/close",
            json={
                "effectiveness": "helpful",
                "child_state_after": "settled",
                "caregiver_state_after": "calmer",
                "notes": "提前压成一步后更容易执行。",
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
                FamilyPolicyWeight.target_kind.in_(
                    ["emotion_pattern", "overload_trigger", "successful_adjustment"]
                ),
            )
        ).all()
        assert rows
