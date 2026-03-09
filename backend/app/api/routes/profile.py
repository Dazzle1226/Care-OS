from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import ChildProfile, Family, User
from app.schemas.domain import ChildProfileInput, ChildProfileRead
from app.services.profile_builder import build_profile_fields

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("", response_model=ChildProfileRead)
def upsert_profile(
    payload: ChildProfileInput,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ChildProfileRead:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    profile = db.scalar(select(ChildProfile).where(ChildProfile.family_id == payload.family_id))
    profile_fields = build_profile_fields(payload.model_dump())

    if profile is None:
        profile = ChildProfile(family_id=payload.family_id, **profile_fields)
        db.add(profile)
    else:
        profile.age_band = profile_fields["age_band"]
        profile.language_level = profile_fields["language_level"]
        profile.sensory_flags = profile_fields["sensory_flags"]
        profile.triggers = profile_fields["triggers"]
        profile.soothing_methods = profile_fields["soothing_methods"]
        profile.donts = profile_fields["donts"]
        profile.school_context = profile_fields["school_context"]
        profile.high_friction_scenarios = profile_fields["high_friction_scenarios"]

    family_name = (payload.family_name or "").strip()
    if family_name:
        family.name = family_name
    family.timezone = payload.timezone or family.timezone

    db.commit()
    db.refresh(profile)

    return ChildProfileRead.model_validate(profile, from_attributes=True)


@router.get("/{family_id}", response_model=ChildProfileRead)
def get_profile(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ChildProfileRead:
    profile = db.scalar(select(ChildProfile).where(ChildProfile.family_id == family_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ChildProfileRead.model_validate(profile, from_attributes=True)
