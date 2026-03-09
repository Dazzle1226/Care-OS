from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import ChildProfile, Family, User
from app.schemas.domain import SupportCardExportRequest, SupportCardExportResponse

router = APIRouter(prefix="/supportcard", tags=["supportcard"])


@router.post("/export", response_model=SupportCardExportResponse)
def export_support_card(
    payload: SupportCardExportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SupportCardExportResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    profile = db.scalar(select(ChildProfile).where(ChildProfile.family_id == payload.family_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    content = {
        "triggers_top3": profile.triggers[:3],
        "soothing_top3": profile.soothing_methods[:3],
        "donts_top3": profile.donts[:3],
        "scenario_focus": profile.high_friction_scenarios[:1],
        "script_hint": "先描述观察，再给两个选择。",
    }

    return SupportCardExportResponse(family_id=payload.family_id, format=payload.format, content=content)
