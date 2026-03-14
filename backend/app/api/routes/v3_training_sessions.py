from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import AdaptiveSession, Family, User
from app.schemas.domain import (
    V3TrainingSessionCloseRequest,
    V3TrainingSessionCloseResponse,
    V3TrainingSessionEventRequest,
    V3TrainingSessionEventResponse,
    V3TrainingSessionStartRequest,
    V3TrainingSessionStartResponse,
)
from app.services.adaptive_training_sessions import AdaptiveTrainingSessionService

router = APIRouter(prefix="/v3/training-sessions", tags=["v3-training-sessions"])


def _family_or_404(db: Session, family_id: int) -> Family:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


def _session_or_404(db: Session, session_id: int) -> AdaptiveSession:
    session = db.get(AdaptiveSession, session_id)
    if session is None or session.chain != "training_support":
        raise HTTPException(status_code=404, detail="Training adaptive session not found")
    return session


@router.post("/start", response_model=V3TrainingSessionStartResponse)
def start_training_session(
    payload: V3TrainingSessionStartRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3TrainingSessionStartResponse:
    family = _family_or_404(db, payload.family_id)
    response = AdaptiveTrainingSessionService().start(db=db, family=family, payload=payload)
    db.commit()
    return response


@router.post("/{session_id}/events", response_model=V3TrainingSessionEventResponse)
def add_training_session_event(
    session_id: int,
    payload: V3TrainingSessionEventRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3TrainingSessionEventResponse:
    session = _session_or_404(db, session_id)
    family = _family_or_404(db, session.family_id)
    response = AdaptiveTrainingSessionService().add_event(db=db, family=family, session=session, payload=payload)
    db.commit()
    return response


@router.post("/{session_id}/close", response_model=V3TrainingSessionCloseResponse)
def close_training_session(
    session_id: int,
    payload: V3TrainingSessionCloseRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3TrainingSessionCloseResponse:
    session = _session_or_404(db, session_id)
    family = _family_or_404(db, session.family_id)
    response = AdaptiveTrainingSessionService().close(db=db, family=family, session=session, payload=payload)
    db.commit()
    return response
