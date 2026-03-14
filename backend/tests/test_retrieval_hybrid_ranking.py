from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import StrategyCard
from app.services.evidence_units import sync_evidence_units
from app.services.retrieval import RetrievalService


def _build_card(
    db_session: Session,
    card_id: str,
    title: str,
    steps: list[str],
    *,
    risk_level: str = "low",
) -> StrategyCard:
    service = RetrievalService(db_session)
    text = "\n".join([title, "transition", " ".join(steps), " ".join(["不要突然加码"]), " ".join(["持续升级"]), "先做一步"])
    embedding = service.embed_text(text)
    return StrategyCard(
        card_id=card_id,
        title=title,
        scenario_tags=["transition"],
        conditions_json={"age_bands": ["7-9"], "language_levels": ["short_sentence"]},
        steps_json=steps,
        scripts_json={"parent": "先做一步"},
        donts_json=["不要突然加码"],
        escalate_json=["持续升级"],
        cost_level="low",
        risk_level=risk_level,
        evidence_tag="practice",
        embedding=embedding,
    )


def test_retrieval_bundle_penalizes_taboo_conflicts(db_session: Session, seeded_family) -> None:
    db_session.add(
        _build_card(
            db_session,
            "SAFE-CARD",
            "提前预告过渡",
            ["提前预告下一步", "给两个选择", "转去安静角落"],
        )
    )
    db_session.add(
        _build_card(
            db_session,
            "CONFLICT-CARD",
            "强拉推进过渡",
            ["直接强拉孩子完成过渡", "提高音量催促", "继续追问原因"],
            risk_level="high",
        )
    )
    db_session.commit()

    retrieval = RetrievalService(db_session)
    selected_cards, bundle, _ = retrieval.retrieve_bundle(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        profile=seeded_family.child_profile,
        extra_context="过渡 等待 提前预告 安静角落",
        max_cards=1,
        top_k=8,
    )

    assert bundle.selected_card_ids
    assert bundle.selection_reasons
    assert bundle.rejected_reasons
    assert selected_cards
    safe_row = next(item for item in bundle.candidate_scores if item.card_id == "SAFE-CARD")
    conflict_row = next(item for item in bundle.candidate_scores if item.card_id == "CONFLICT-CARD")
    assert safe_row.selected is True
    assert conflict_row.taboo_conflict_penalty > 0
    assert conflict_row.selected is False


def test_retrieval_bundle_selects_safety_evidence_units(db_session: Session, seeded_family) -> None:
    db_session.add(
        _build_card(
            db_session,
            "BALANCED-CARD",
            "低刺激过渡",
            ["提前预告下一步", "给两个选择", "转去安静角落"],
        )
    )
    db_session.commit()
    sync_evidence_units(db_session)
    db_session.commit()

    retrieval = RetrievalService(db_session)
    _, bundle, _ = retrieval.retrieve_bundle(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        profile=seeded_family.child_profile,
        extra_context="过渡 等待 提前预告 安静角落 不要突然加码",
        max_cards=1,
        top_k=8,
    )

    assert bundle.selected_evidence_unit_ids
    assert bundle.coverage_scores["safety"] == 1.0
    assert any(":dont_" in unit_id or ":escalate_" in unit_id for unit_id in bundle.selected_evidence_unit_ids)
