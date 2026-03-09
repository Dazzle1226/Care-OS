from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import Family, User
from app.schemas.domain import FamilyCreate, FamilyRead

router = APIRouter(prefix="/family", tags=["family"])


@router.post("", response_model=FamilyRead)
def create_family(
    payload: FamilyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FamilyRead:
    family = Family(name=payload.name, timezone=payload.timezone, owner_user_id=user.user_id)
    db.add(family)
    db.commit()
    db.refresh(family)
    return FamilyRead(
        family_id=family.family_id,
        name=family.name,
        timezone=family.timezone,
        owner_user_id=family.owner_user_id,
    )


@router.get("/{family_id}", response_model=FamilyRead)
def get_family(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FamilyRead:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return FamilyRead(
        family_id=family.family_id,
        name=family.name,
        timezone=family.timezone,
        owner_user_id=family.owner_user_id,
    )
