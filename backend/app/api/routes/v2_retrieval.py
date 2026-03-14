from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import RetrievalRun, User
from app.schemas.domain import RetrievalTraceCandidateRead, RetrievalTraceRead
from app.services.decision_orchestrator import DecisionOrchestrator

router = APIRouter(prefix="/v2/retrieval", tags=["v2-retrieval"])


@router.get("/traces/{trace_id}", response_model=RetrievalTraceRead)
def get_retrieval_trace(
    trace_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RetrievalTraceRead:
    trace = DecisionOrchestrator().get_trace(db=db, trace_id=trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Decision trace not found")
    bundle = trace.retrieval_bundle
    candidates: list[RetrievalTraceCandidateRead] = []
    if bundle is not None and bundle.retrieval_run_id is not None:
        retrieval_run = db.get(RetrievalRun, bundle.retrieval_run_id)
        if retrieval_run is not None:
            candidates = [
                RetrievalTraceCandidateRead(
                    candidate_id=item.id,
                    source_type=item.source_type,
                    card_id=item.card_id,
                    chunk_id=item.chunk_id,
                    title=item.title,
                    total_score=item.total_score,
                    dense_score=item.dense_score,
                    sparse_score=item.sparse_score,
                    profile_score=item.profile_score,
                    history_score=item.history_score,
                    policy_score=item.policy_score,
                    safety_penalty=item.safety_penalty,
                    selected=item.selected,
                    filter_reason=item.filter_reason,
                    feature_attribution=list(item.feature_attribution_json),
                )
                for item in retrieval_run.candidates
            ]
    return RetrievalTraceRead(
        trace=trace,
        retrieval_run_id=bundle.retrieval_run_id if bundle is not None else None,
        selected_sources=list(bundle.selected_sources if bundle is not None else []),
        hard_filtered_reasons=list(bundle.hard_filtered_reasons if bundle is not None else []),
        feature_attribution=list(bundle.feature_attribution if bundle is not None else []),
        candidates=candidates,
    )
