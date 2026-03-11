from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.coach import CoachAgent
from app.models import IncidentLog, Review


def test_coach_updates_positive_weight(db_session: Session, seeded_family) -> None:
    incident = IncidentLog(
        family_id=seeded_family.family_id,
        ts=datetime.utcnow(),
        scenario="transition",
        intensity="medium",
        triggers=["等待"],
        selected_resources={},
        high_risk_flag=False,
        notes="",
    )
    db_session.add(incident)
    db_session.flush()

    db_session.add(
        Review(
            incident_id=incident.id,
            family_id=seeded_family.family_id,
            card_ids=["CARD-0001"],
            outcome_score=2,
            notes="有效",
            followup_action="继续",
        )
    )
    db_session.add(
        Review(
            incident_id=incident.id,
            family_id=seeded_family.family_id,
            card_ids=["CARD-0001"],
            outcome_score=1,
            notes="有效",
            followup_action="继续",
        )
    )

    weights = CoachAgent().update_preference_weights(db=db_session, family_id=seeded_family.family_id)
    db_session.commit()

    assert "CARD-0001" in weights
    assert weights["CARD-0001"] > 0


def test_coach_ignores_manual_review_placeholders(db_session: Session, seeded_family) -> None:
    incident = IncidentLog(
        family_id=seeded_family.family_id,
        ts=datetime.utcnow(),
        scenario="transition",
        intensity="medium",
        triggers=["等待"],
        selected_resources={},
        high_risk_flag=False,
        notes="",
    )
    db_session.add(incident)
    db_session.flush()

    db_session.add(
        Review(
            incident_id=incident.id,
            family_id=seeded_family.family_id,
            card_ids=["manual:transition", "CARD-0002"],
            outcome_score=1,
            notes="只绑定了一张真实卡",
            followup_action="继续",
        )
    )

    weights = CoachAgent().update_preference_weights(db=db_session, family_id=seeded_family.family_id)
    db_session.commit()

    assert "manual:transition" not in weights
    assert "CARD-0002" in weights
