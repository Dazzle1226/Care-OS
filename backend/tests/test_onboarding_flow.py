from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import ChildProfile, Family


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_manual_onboarding_creates_family_profile_and_cards(db_session: Session) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post(
            "/api/onboarding/setup",
            json={
                "child_name": "小雨",
                "child_age": 8,
                "child_gender": "female",
                "primary_caregiver": "parents",
                "diagnosis_status": "asd",
                "communication_level": "short_sentence",
                "core_difficulties": ["过渡困难", "感官敏感"],
                "triggers": ["过渡", "等待", "噪音"],
                "sensory_flags": ["声音敏感", "触感敏感"],
                "taboo_behaviors": "不要突然拉走；不要连续追问",
                "parent_stressors": ["工作压力", "睡眠不足"],
                "available_supporters": ["配偶", "外婆"],
                "supporter_availability": ["工作日晚上", "周末"],
                "supporter_independent_care": "can_alone",
            },
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["family"]["name"] == "小雨的家庭"
    assert payload["profile"]["age_band"] == "7-9"
    assert payload["profile"]["school_context"]["parent_stressors"] == ["工作压力", "睡眠不足"]
    assert len(payload["support_cards"]) == 2
    assert payload["support_cards"][0]["title"] == "支持卡"
    assert payload["support_cards"][1]["title"] == "交接卡"
    assert len(payload["support_cards"][0]["quick_actions"]) >= 2
    assert payload["support_cards"][0]["sections"][0]["title"] == "沟通"
    assert payload["support_cards"][1]["sections"][0]["title"] == "当前状态"
    assert "过渡期" in payload["snapshot"]["recommended_focus"]

    db_session.expire_all()
    family = db_session.get(Family, payload["family"]["family_id"])
    profile = db_session.scalar(select(ChildProfile).where(ChildProfile.family_id == payload["family"]["family_id"]))
    assert family is not None
    assert profile is not None
    assert profile.school_context["child_name"] == "小雨"
    assert profile.school_context["core_difficulties"] == ["过渡困难", "感官敏感"]
    assert profile.school_context["available_supporters"] == ["配偶", "外婆"]
    assert profile.school_context["supporter_availability"] == ["工作日晚上", "周末"]


def test_sample_onboarding_returns_prefilled_example() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.post("/api/onboarding/setup", json={"use_sample": True}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["family"]["name"] == "示例家庭"
    assert payload["profile"]["language_level"] == "short_sentence"
    assert payload["snapshot"]["child_overview"][0].startswith("乐乐")
    assert payload["snapshot"]["supporter_summary"] == ["配偶", "外婆", "朋友"]
    assert len(payload["support_cards"]) == 2
    assert payload["support_cards"][0]["icon"] == "support"
    assert payload["support_cards"][1]["icon"] == "handoff"
    assert payload["support_cards"][0]["one_liner"]


def test_get_onboarding_family_supports_existing_profiles(seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        response = client.get(f"/api/onboarding/family/{seeded_family.family_id}", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["family"]["family_id"] == seeded_family.family_id
    assert payload["profile"]["triggers"] == ["过渡", "等待"]
    assert payload["snapshot"]["caregiver_pressure"] == ["暂未填写压力源"]
    assert payload["snapshot"]["supporter_summary"] == ["暂未标记可用支持者"]
    assert len(payload["support_cards"]) == 2
