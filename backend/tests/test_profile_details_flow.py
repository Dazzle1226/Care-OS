from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(client: TestClient, identifier: str = "profile-tester") -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": identifier, "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_onboarding_and_profile_update_should_store_detailed_context() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)

        onboarding_payload = {
            "family_name": "晨晨一家",
            "timezone": "Asia/Shanghai",
            "child_name": "晨晨",
            "child_age": 8,
            "child_gender": "male",
            "primary_caregiver": "parents",
            "diagnosis_status": "asd",
            "diagnosis_notes": "医生提示伴焦虑反应。",
            "communication_level": "short_sentence",
            "coexisting_conditions": ["焦虑"],
            "family_members": ["妈妈", "爸爸", "奶奶"],
            "interests": ["地铁", "拼图"],
            "likes": ["提前预告"],
            "dislikes": ["突然催促"],
            "triggers": ["过渡", "等待"],
            "sensory_flags": ["声音敏感"],
            "soothing_methods": ["视觉倒计时"],
            "sleep_challenges": ["夜醒"],
            "food_preferences": ["偏爱软糯食物"],
            "allergies": ["牛奶过敏"],
            "medical_needs": ["外出随身带药"],
            "medications": ["药物 A 5mg / 晚"],
            "health_conditions": ["便秘"],
            "behavior_patterns": ["遇到变化会僵住"],
            "behavior_risks": ["哭闹"],
            "emotion_patterns": ["焦虑"],
            "learning_needs": ["视觉提示"],
            "school_type": "mainstream",
            "social_training": ["社交小组"],
            "school_notes": "普通小学融合班，和 1 位固定同学关系较好。",
            "high_friction_scenarios": ["transition", "homework"],
            "parent_schedule": ["工作日白天上班"],
            "parent_stressors": ["照护任务"],
            "parent_support_actions": ["家长支持群"],
            "parent_emotional_supports": ["伴侣倾听"],
            "available_supporters": ["配偶"],
            "taboo_behaviors": "不要突然拉走",
        }

        create_response = client.post("/api/onboarding/setup", json=onboarding_payload, headers=headers)
        assert create_response.status_code == 200
        created = create_response.json()
        family_id = created["family"]["family_id"]

        assert created["family"]["name"] == "晨晨一家"
        assert created["profile"]["school_context"]["family_members"] == ["妈妈", "爸爸", "奶奶"]
        assert created["profile"]["school_context"]["medications"] == ["药物 A 5mg / 晚"]
        assert created["snapshot"]["health_summary"]
        assert created["snapshot"]["behavior_summary"]
        assert created["snapshot"]["parent_support_summary"]

        update_payload = onboarding_payload | {
            "family_id": family_id,
            "family_name": "晨晨一家（更新）",
            "interests": ["地铁", "拼图", "画画"],
            "available_supporters": ["配偶", "外婆"],
            "parent_support_actions": ["家长支持群", "周末有人接手"],
        }
        update_response = client.post("/api/profile", json=update_payload, headers=headers)
        assert update_response.status_code == 200

        family_response = client.get(f"/api/onboarding/family/{family_id}", headers=headers)
        assert family_response.status_code == 200
        refreshed = family_response.json()

        assert refreshed["family"]["name"] == "晨晨一家（更新）"
        assert refreshed["profile"]["school_context"]["interests"] == ["地铁", "拼图", "画画"]
        assert refreshed["profile"]["school_context"]["available_supporters"] == ["配偶", "外婆"]
        assert refreshed["snapshot"]["supporter_summary"] == ["配偶", "外婆"]
