from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.benchmarking import BenchmarkService
from app.services.retrieval import RetrievalService


def test_benchmark_retrieval_exposes_evidence_level_bundle(db_session: Session, seeded_family) -> None:
    retrieval = RetrievalService(db_session)
    _, bundle, _ = retrieval.retrieve_bundle(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        profile=seeded_family.child_profile,
        extra_context="学校通知说明明天调整流程，需要先预告，再给两个选择，避免突然加码。",
        max_cards=3,
        top_k=10,
    )

    assert bundle.selected_card_ids
    assert bundle.selected_evidence_unit_ids
    assert bundle.coverage_scores
    assert set(bundle.coverage_scores).issuperset({"scenario", "profile", "safety", "execution"})
    assert bundle.counter_evidence
    assert isinstance(bundle.insufficient_evidence, bool)
    assert bundle.ranking_summary

    run = BenchmarkService().run(db_session)
    metric_names = {item.name for item in run.metrics}
    assert "ndcg_at_k" in metric_names
    assert "why_not_coverage" in metric_names
    assert any(item.details_json for item in run.metrics if item.category == "ir_eval")
