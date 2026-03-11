from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.agents.signal import SignalAgent
from app.models import DailyCheckin, Family, IncidentLog, User


def _make_family(db_session: Session, suffix: str) -> Family:
    user = User(identifier=f"signal-{suffix}", role="caregiver", locale="zh-CN")
    db_session.add(user)
    db_session.flush()

    family = Family(name=f"Signal {suffix}", timezone="Asia/Shanghai", owner_user_id=user.user_id)
    db_session.add(family)
    db_session.flush()
    return family


def _add_checkins(db_session: Session, family_id: int, items: list[dict[str, object]]) -> None:
    today = date.today()
    for offset, payload in enumerate(items):
        db_session.add(
            DailyCheckin(
                family_id=family_id,
                date=today - timedelta(days=offset),
                child_sleep_hours=float(payload.get("child_sleep_hours", 8.0)),
                meltdown_count=int(payload.get("meltdown_count", 0)),
                transition_difficulty=float(payload.get("transition_difficulty", 3.0)),
                sensory_overload_level=str(payload.get("sensory_overload_level", "none")),
                caregiver_stress=float(payload.get("caregiver_stress", 4.0)),
                caregiver_sleep_hours=float(payload.get("caregiver_sleep_hours", 7.5)),
                support_available=str(payload.get("support_available", "one")),
                env_changes=list(payload.get("env_changes", [])),
            )
        )
    db_session.commit()


def test_signal_should_trigger_48h(db_session: Session, seeded_family) -> None:
    signal = SignalAgent().evaluate(db=db_session, family_id=seeded_family.family_id)
    assert signal.trigger_48h is True
    assert signal.risk_level == "red"
    assert signal.confidence >= 0.6


def test_signal_should_stay_green_with_protection_factors(db_session: Session) -> None:
    family = _make_family(db_session, "green")
    _add_checkins(
        db_session,
        family.family_id,
        [
            {
                "caregiver_stress": 4.0,
                "caregiver_sleep_hours": 7.5,
                "child_sleep_hours": 8.0,
                "meltdown_count": 0,
                "transition_difficulty": 3.0,
                "support_available": "two_plus",
            },
            {
                "caregiver_stress": 4.5,
                "caregiver_sleep_hours": 7.0,
                "child_sleep_hours": 7.5,
                "meltdown_count": 1,
                "transition_difficulty": 4.0,
                "support_available": "two_plus",
            },
        ],
    )

    signal = SignalAgent().evaluate(db=db_session, family_id=family.family_id)

    assert signal.risk_level == "green"
    assert signal.trigger_48h is False
    assert any("可接手支持" in reason or "稳定" in reason for reason in signal.reasons)


def test_signal_should_drop_from_red_to_yellow_with_support_buffer(db_session: Session) -> None:
    family = _make_family(db_session, "yellow")
    _add_checkins(
        db_session,
        family.family_id,
        [
            {
                "caregiver_stress": 7.2,
                "caregiver_sleep_hours": 7.0,
                "child_sleep_hours": 6.5,
                "meltdown_count": 2,
                "transition_difficulty": 8.0,
                "sensory_overload_level": "light",
                "support_available": "two_plus",
            },
            {
                "caregiver_stress": 7.1,
                "caregiver_sleep_hours": 7.2,
                "child_sleep_hours": 7.0,
                "meltdown_count": 1,
                "transition_difficulty": 6.0,
                "support_available": "two_plus",
            },
        ],
    )

    signal = SignalAgent().evaluate(db=db_session, family_id=family.family_id)

    assert signal.risk_level == "yellow"
    assert signal.trigger_48h is True
    assert any("过渡" in reason or "压力" in reason for reason in signal.reasons)


def test_signal_should_use_cautious_default_when_missing_history(db_session: Session) -> None:
    family = _make_family(db_session, "empty")

    signal = SignalAgent().evaluate(db=db_session, family_id=family.family_id)

    assert signal.risk_level == "yellow"
    assert signal.trigger_48h is False
    assert signal.confidence == 0.35
    assert signal.reasons == ["缺少近7天签到，默认进入谨慎模式"]


def test_signal_should_trigger_on_recent_heavy_incident(db_session: Session) -> None:
    family = _make_family(db_session, "incident")
    _add_checkins(
        db_session,
        family.family_id,
        [
            {
                "caregiver_stress": 5.5,
                "caregiver_sleep_hours": 6.5,
                "child_sleep_hours": 7.0,
                "meltdown_count": 1,
                "transition_difficulty": 5.0,
                "support_available": "one",
            }
        ],
    )
    db_session.add(
        IncidentLog(
            family_id=family.family_id,
            scenario="transition",
            intensity="heavy",
            triggers=["临时变更"],
            selected_resources={},
            high_risk_flag=False,
            notes="升级明显",
        )
    )
    db_session.commit()

    signal = SignalAgent().evaluate(db=db_session, family_id=family.family_id)

    assert signal.risk_level == "yellow"
    assert signal.trigger_48h is True
    assert "近期发生重度事件" in signal.reasons
