from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.domain import KnowledgeIngestionRequest
from app.services.knowledge_corpus import KnowledgeCorpusService
from app.services.retrieval import RetrievalService


def test_retrieval_bundle_exposes_query_plan_and_personalization(db_session: Session, seeded_family) -> None:
    KnowledgeCorpusService().ingest_manual_knowledge(
        db_session,
        KnowledgeIngestionRequest(
            family_id=seeded_family.family_id,
            source_type="review_summary",
            title="过渡复盘",
            body="孩子在放学回家过渡时更容易升级，提前预告和先给两个选择会更稳。",
            scope="family",
            scope_key="transition-review",
            metadata={"tag": "transition"},
        ),
    )
    db_session.commit()

    retrieval = RetrievalService(db_session)
    _, bundle, _ = retrieval.retrieve_bundle(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        profile=seeded_family.child_profile,
        extra_context="学校通知说明今天过渡更难，需要先预告，再给两个选择。",
        intent="plan",
        context_signal_keys=["schedule_change", "school_signal"],
    )

    assert bundle.query_plan is not None
    assert bundle.query_plan.intent == "plan"
    assert bundle.selected_sources
    assert bundle.selected_chunk_ids
    assert bundle.personalization_applied
    assert any(source.scope == "family" for source in bundle.selected_sources)
    assert bundle.retrieval_latency_ms >= 0
    assert bundle.retrieval_run_id is not None
