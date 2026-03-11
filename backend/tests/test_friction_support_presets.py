from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("quick_preset", "preset_label"),
    [
        ("transition_now", "过渡"),
        ("bedtime_push", "睡前"),
        ("homework_push", "作业"),
        ("outing_exit", "外出"),
        ("meltdown_now", "崩溃"),
        ("wakeup_stall", "起床"),
        ("meal_conflict", "吃饭"),
        ("screen_off", "关屏"),
        ("bath_resistance", "洗澡"),
        ("waiting_public", "等待"),
    ],
)
def test_friction_support_quick_presets_return_action_card(
    seeded_family,
    quick_preset: str,
    preset_label: str,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/scripts/friction-support",
            json={
                "family_id": seeded_family.family_id,
                "quick_preset": quick_preset,
                "free_text": "现场先给我最短可执行动作。",
            },
            headers=_auth_headers(client),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["blocked"] is False
    assert body["support"]["preset_label"] == preset_label
    assert len(body["support"]["action_plan"]) == 3
    assert len(body["support"]["donts"]) >= 3
    assert len(body["support"]["say_this"]) >= 2
    assert len(body["support"]["crisis_card"]["first_do"]) == 3
    assert len(body["support"]["crisis_card"]["donts"]) == 3
    assert len(body["support"]["crisis_card"]["exit_plan"]) == 3
    assert len(body["support"]["crisis_card"]["help_now"]) >= 1


def test_friction_support_low_stim_request_forces_low_stim_card(seeded_family) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/scripts/friction-support",
            json={
                "family_id": seeded_family.family_id,
                "quick_preset": "transition_now",
                "low_stim_mode_requested": True,
            },
            headers=_auth_headers(client),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["blocked"] is False
    assert body["support"]["low_stim_mode"]["active"] is True
    assert body["support"]["crisis_card"]["badges"]
