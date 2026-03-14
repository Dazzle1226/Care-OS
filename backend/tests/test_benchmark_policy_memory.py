from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.policy_learning import PolicyLearningService


def test_benchmark_policy_memory_builds_layered_snapshot_and_diff(db_session: Session, seeded_family) -> None:
    service = PolicyLearningService()

    service.record_review(
        db=db_session,
        family_id=seeded_family.family_id,
        outcome_score=2,
        card_ids=["CARD-TRANSITION-FOREWARN"],
        scenario="transition",
        response_action="提前预告",
    )
    service.record_review(
        db=db_session,
        family_id=seeded_family.family_id,
        outcome_score=2,
        card_ids=["CARD-TRANSITION-FOREWARN"],
        scenario="transition",
        response_action="提前预告",
    )
    service.record_review(
        db=db_session,
        family_id=seeded_family.family_id,
        outcome_score=-1,
        card_ids=["CARD-TRANSITION-WAIT"],
        scenario="transition",
        response_action="等待",
    )
    db_session.commit()

    snapshot = service.build_snapshot(db_session, seeded_family.family_id)
    diff = service.build_diff(db_session, seeded_family.family_id)

    assert snapshot.segment_key != "unknown"
    assert snapshot.items
    assert any(item.target_kind == "card" for item in snapshot.items)
    assert diff.strongest_positive
    assert all(item.effective_weight > -1.5 for item in diff.strongest_negative)
