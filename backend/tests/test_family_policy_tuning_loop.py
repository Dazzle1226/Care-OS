from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import StrategyCard
from app.services.policy_learning import PolicyLearningService
from app.services.retrieval import RetrievalService


def _custom_card(db_session: Session, card_id: str, title: str) -> StrategyCard:
    service = RetrievalService(db_session)
    text = "\n".join([title, "transition", "提前预告 给两个选择", "不要临时加码", "持续升级", "先做一步"])
    return StrategyCard(
        card_id=card_id,
        title=title,
        scenario_tags=["transition"],
        conditions_json={"age_bands": ["7-9"], "language_levels": ["short_sentence"]},
        steps_json=["提前预告", "给两个选择", "切到安静角落"],
        scripts_json={"parent": "我们先做第一步"},
        donts_json=["不要临时加码"],
        escalate_json=["持续升级"],
        cost_level="low",
        risk_level="low",
        evidence_tag="practice",
        embedding=service.embed_text(text),
    )


def test_policy_learning_changes_retrieval_order_without_permanent_kill(db_session: Session, seeded_family) -> None:
    db_session.add(_custom_card(db_session, "POLICY-GOOD", "家庭偏好过渡卡"))
    db_session.add(_custom_card(db_session, "POLICY-ALT", "备用过渡卡"))
    db_session.commit()

    retrieval = RetrievalService(db_session)
    _, before_bundle, _ = retrieval.retrieve_bundle(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        profile=seeded_family.child_profile,
        extra_context="过渡 提前预告",
        max_cards=2,
        top_k=8,
    )

    policy = PolicyLearningService()
    policy.record_review(
        db=db_session,
        family_id=seeded_family.family_id,
        outcome_score=2,
        card_ids=["POLICY-GOOD"],
        scenario="transition",
        response_action="提前预告",
    )
    policy.record_review(
        db=db_session,
        family_id=seeded_family.family_id,
        outcome_score=2,
        card_ids=["POLICY-GOOD"],
        scenario="transition",
        response_action="提前预告",
    )
    policy.record_review(
        db=db_session,
        family_id=seeded_family.family_id,
        outcome_score=-2,
        card_ids=["POLICY-ALT"],
        scenario="transition",
        response_action="备用方案",
    )
    db_session.commit()

    _, after_bundle, _ = retrieval.retrieve_bundle(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        profile=seeded_family.child_profile,
        extra_context="过渡 提前预告",
        max_cards=2,
        top_k=8,
    )

    before_good = next(item for item in before_bundle.candidate_scores if item.card_id == "POLICY-GOOD")
    after_good = next(item for item in after_bundle.candidate_scores if item.card_id == "POLICY-GOOD")
    after_alt = next(item for item in after_bundle.candidate_scores if item.card_id == "POLICY-ALT")
    card_weights = policy.get_weight_map(db=db_session, family_id=seeded_family.family_id, target_kind="card")

    assert after_good.total_score >= before_good.total_score
    assert after_good.policy_weight > 0
    assert card_weights["POLICY-ALT"] < 0
    assert card_weights["POLICY-ALT"] > -1.5
    assert any(item.card_id == "POLICY-ALT" for item in after_bundle.candidate_scores)
