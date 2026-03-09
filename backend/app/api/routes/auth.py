from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.base import get_db
from app.models import User
from app.schemas.domain import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.identifier == payload.identifier))
    if user is None:
        user = User(identifier=payload.identifier, role=payload.role, locale=payload.locale)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(subject=str(user.user_id), extra={"role": user.role})
    return LoginResponse(access_token=token, user_id=user.user_id)
