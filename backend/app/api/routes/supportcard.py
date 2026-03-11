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
        "title": "家庭危机卡",
        "scenario_focus": profile.high_friction_scenarios[:2],
        "first_do": [
            "先停当前要求，只保留安全。",
            "降声音和灯光，只留一位沟通者。",
            f"转去{profile.soothing_methods[0] if profile.soothing_methods else '安静角落'}。",
        ],
        "donts_top3": profile.donts[:3],
        "triggers_top3": profile.triggers[:3],
        "soothing_top3": profile.soothing_methods[:3],
        "say_this": [
            "先停一下，你是安全的，我会陪你。",
            "现在只做一步，别的先暂停。",
        ],
        "exit_plan": [
            "若继续升级，直接退场。",
            "若家长跟不上，马上交接支持者。",
            "若有人身风险，立即求助。",
        ],
    }

    return SupportCardExportResponse(family_id=payload.family_id, format=payload.format, content=content)
