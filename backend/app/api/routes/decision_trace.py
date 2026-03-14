from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.domain import DecisionTraceRead
from app.services.decision_orchestrator import DecisionOrchestrator

router = APIRouter(prefix="/decision-trace", tags=["decision-trace"])


@router.get("/{trace_id}", response_model=DecisionTraceRead)
def get_decision_trace(
    trace_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DecisionTraceRead:
    trace = DecisionOrchestrator().get_trace(db=db, trace_id=trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Decision trace not found")
    return trace
