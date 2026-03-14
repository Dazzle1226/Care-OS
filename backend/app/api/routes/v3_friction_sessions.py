from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import AdaptiveSession, Family, User
from app.schemas.domain import (
    V3FrictionSessionCloseRequest,
    V3FrictionSessionCloseResponse,
    V3FrictionSessionConfirmRequest,
    V3FrictionSessionConfirmResponse,
    V3FrictionSessionEventRequest,
    V3FrictionSessionEventResponse,
    V3FrictionSessionStartRequest,
    V3FrictionSessionStartResponse,
    V3FrictionSessionTraceResponse,
)
from app.services.adaptive_friction_sessions import AdaptiveFrictionSessionService

router = APIRouter(prefix="/v3/friction-sessions", tags=["v3-friction-sessions"])


def _family_or_404(db: Session, family_id: int) -> Family:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


def _session_or_404(db: Session, session_id: int) -> AdaptiveSession:
    session = db.get(AdaptiveSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Adaptive session not found")
    return session


@router.post("/start", response_model=V3FrictionSessionStartResponse)
def start_friction_session(
    payload: V3FrictionSessionStartRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3FrictionSessionStartResponse:
    family = _family_or_404(db, payload.family_id)
    response = AdaptiveFrictionSessionService().start(db=db, family=family, payload=payload)
    db.commit()
    return response


@router.post("/{session_id}/events", response_model=V3FrictionSessionEventResponse)
def add_friction_session_event(
    session_id: int,
    payload: V3FrictionSessionEventRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3FrictionSessionEventResponse:
    session = _session_or_404(db, session_id)
    family = _family_or_404(db, session.family_id)
    response = AdaptiveFrictionSessionService().add_event(db=db, family=family, session=session, payload=payload)
    db.commit()
    return response


@router.post("/{session_id}/confirm", response_model=V3FrictionSessionConfirmResponse)
def confirm_friction_session(
    session_id: int,
    payload: V3FrictionSessionConfirmRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3FrictionSessionConfirmResponse:
    session = _session_or_404(db, session_id)
    family = _family_or_404(db, session.family_id)
    response = AdaptiveFrictionSessionService().confirm(db=db, family=family, session=session, payload=payload)
    db.commit()
    return response


@router.post("/{session_id}/close", response_model=V3FrictionSessionCloseResponse)
def close_friction_session(
    session_id: int,
    payload: V3FrictionSessionCloseRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3FrictionSessionCloseResponse:
    session = _session_or_404(db, session_id)
    family = _family_or_404(db, session.family_id)
    response = AdaptiveFrictionSessionService().close(db=db, family=family, session=session, payload=payload)
    db.commit()
    return response


@router.get("/{session_id}/trace", response_model=V3FrictionSessionTraceResponse)
def get_friction_session_trace(
    session_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V3FrictionSessionTraceResponse:
    session = _session_or_404(db, session_id)
    return AdaptiveFrictionSessionService().get_trace(db=db, session=session)
