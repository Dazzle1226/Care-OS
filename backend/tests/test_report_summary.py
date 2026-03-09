from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import DailyCheckin, IncidentLog, Review


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _week_start(target: date) -> date:
    return target - timedelta(days=target.isoweekday() - 1)


def _month_start(target: date) -> date:
    return date(target.year, target.month, 1)


def _previous_month_start(target: date) -> date:
    first = _month_start(target)
    return _month_start(first - timedelta(days=1))


def test_weekly_report_includes_summary_and_feedback(db_session: Session, seeded_family) -> None:
    today = date.today()
    week_start = _week_start(today)

    extra_checkins = [
        DailyCheckin(
            family_id=seeded_family.family_id,
            date=week_start + timedelta(days=2),
            child_sleep_hours=6.5,
            meltdown_count=1,
            transition_difficulty=7.0,
            sensory_overload_level="medium",
            caregiver_stress=7.0,
            caregiver_sleep_hours=5.0,
            support_available="one",
            env_changes=["噪音"],
        ),
        DailyCheckin(
            family_id=seeded_family.family_id,
            date=week_start + timedelta(days=3),
            child_sleep_hours=7.0,
            meltdown_count=0,
            transition_difficulty=5.0,
            sensory_overload_level="light",
            caregiver_stress=5.0,
            caregiver_sleep_hours=6.0,
            support_available="two_plus",
            env_changes=["换环境"],
        ),
    ]
    db_session.add_all(extra_checkins)

    incident = IncidentLog(
        family_id=seeded_family.family_id,
        ts=datetime.combine(week_start + timedelta(days=2), time(hour=18)),
        scenario="transition",
        intensity="medium",
        triggers=["等待", "噪音"],
        selected_resources={},
        high_risk_flag=False,
        notes="放学回家后卡住",
    )
    db_session.add(incident)
    db_session.flush()

    review = Review(
        incident_id=incident.id,
        family_id=seeded_family.family_id,
        card_ids=["CARD-0001", "CARD-0002"],
        outcome_score=1,
        notes="提前预告后稍有改善",
        followup_action="保留睡前过渡预告",
        created_at=datetime.combine(week_start + timedelta(days=3), time(hour=9)),
    )
    db_session.add(review)
    db_session.commit()

    with TestClient(app) as client:
        headers = _auth_headers(client)
        weekly_response = client.get(
            f"/api/report/weekly/{seeded_family.family_id}",
            params={"week_start": week_start.isoformat()},
            headers=headers,
        )

        assert weekly_response.status_code == 200
        body = weekly_response.json()
        assert body["trigger_top3"]
        assert body["trigger_summary"]
        assert body["child_emotion_summary"]
        assert len(body["stress_trend"]) == 7
        assert len(body["meltdown_trend"]) == 7
        assert body["task_completion_score"] >= 0
        assert body["strategy_top3"][0]["title"]
        assert body["next_actions"][0]["title"]

        feedback_response = client.post(
            "/api/report/feedback",
            json={
                "family_id": seeded_family.family_id,
                "period_type": "weekly",
                "period_start": week_start.isoformat(),
                "target_kind": "strategy",
                "target_key": body["strategy_top3"][0]["target_key"],
                "target_label": body["strategy_top3"][0]["title"],
                "feedback": "effective",
                "note": "这条策略本周最稳。",
            },
            headers=headers,
        )

        assert feedback_response.status_code == 200
        assert feedback_response.json()["summary"]["effective_count"] == 1

        refreshed_response = client.get(
            f"/api/report/weekly/{seeded_family.family_id}",
            params={"week_start": week_start.isoformat()},
            headers=headers,
        )

    assert refreshed_response.status_code == 200
    refreshed = refreshed_response.json()
    assert refreshed["feedback_summary"]["effective_count"] == 1
    assert refreshed["feedback_states"][0]["feedback"] == "effective"


def test_monthly_report_returns_trends_and_history(db_session: Session, seeded_family) -> None:
    today = date.today()
    month_start = _month_start(today)
    previous_month = _previous_month_start(today)

    db_session.add_all(
        [
            DailyCheckin(
                family_id=seeded_family.family_id,
                date=previous_month + timedelta(days=3),
                child_sleep_hours=5.0,
                meltdown_count=2,
                transition_difficulty=8.0,
                sensory_overload_level="heavy",
                caregiver_stress=8.5,
                caregiver_sleep_hours=4.0,
                support_available="none",
                env_changes=["噪音"],
            ),
            DailyCheckin(
                family_id=seeded_family.family_id,
                date=month_start + timedelta(days=3),
                child_sleep_hours=7.0,
                meltdown_count=1,
                transition_difficulty=6.0,
                sensory_overload_level="medium",
                caregiver_stress=6.0,
                caregiver_sleep_hours=6.0,
                support_available="one",
                env_changes=["过渡"],
            ),
        ]
    )

    previous_incident = IncidentLog(
        family_id=seeded_family.family_id,
        ts=datetime.combine(previous_month + timedelta(days=4), time(hour=17)),
        scenario="homework",
        intensity="heavy",
        triggers=["等待"],
        selected_resources={},
        high_risk_flag=False,
        notes="上月作业冲突",
    )
    current_incident = IncidentLog(
        family_id=seeded_family.family_id,
        ts=datetime.combine(month_start + timedelta(days=5), time(hour=19)),
        scenario="transition",
        intensity="medium",
        triggers=["过渡", "噪音"],
        selected_resources={},
        high_risk_flag=False,
        notes="本月过渡冲突",
    )
    db_session.add_all([previous_incident, current_incident])
    db_session.flush()

    db_session.add_all(
        [
            Review(
                incident_id=previous_incident.id,
                family_id=seeded_family.family_id,
                card_ids=["CARD-0002"],
                outcome_score=-1,
                notes="上月执行效果一般",
                followup_action="缩短作业时长",
                created_at=datetime.combine(previous_month + timedelta(days=5), time(hour=10)),
            ),
            Review(
                incident_id=current_incident.id,
                family_id=seeded_family.family_id,
                card_ids=["CARD-0001"],
                outcome_score=2,
                notes="本月执行效果不错",
                followup_action="继续提前预告",
                created_at=datetime.combine(month_start + timedelta(days=6), time(hour=11)),
            ),
        ]
    )
    db_session.commit()

    with TestClient(app) as client:
        headers = _auth_headers(client)
        monthly_response = client.get(
            f"/api/report/monthly/{seeded_family.family_id}",
            params={"month_start": month_start.isoformat()},
            headers=headers,
        )

    assert monthly_response.status_code == 200
    body = monthly_response.json()
    assert body["overview_summary"]
    assert body["stress_change_summary"]
    assert body["conflict_change_summary"]
    assert body["task_completion_summary"]
    assert len(body["long_term_trends"]) == 4
    assert len(body["history"]) == 3
    assert body["successful_methods"][0]["title"]
    assert body["next_month_plan"][0]["title"]
