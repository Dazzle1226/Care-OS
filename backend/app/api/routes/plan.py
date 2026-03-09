from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.plan import PlanAgent, PlanContext
from app.agents.safety import SafetyAgent
from app.agents.signal import SignalAgent
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import DailyCheckin, Family, Plan48h, PlanCardUse, User
from app.schemas.domain import Plan48hGenerateRequest, Plan48hGenerateResponse, Plan48hResponse, PlanRead

router = APIRouter(prefix="/plan48h", tags=["plan"])


@router.post("/generate", response_model=Plan48hGenerateResponse)
def generate_plan(
    payload: Plan48hGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Plan48hGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    signal = SignalAgent().evaluate(db=db, family_id=payload.family_id, manual_trigger=payload.manual_trigger)
    latest_checkin = db.scalar(
        select(DailyCheckin)
        .where(DailyCheckin.family_id == payload.family_id)
        .order_by(desc(DailyCheckin.date))
        .limit(1)
    )
    support_hint = latest_checkin.support_available if latest_checkin else "none"

    context = PlanContext(
        family_id=payload.family_id,
        scenario=payload.scenario,
        intensity="heavy" if signal.risk_level == "red" else "medium",
        support_hint=support_hint,
        free_text=payload.free_text,
    )

    plan = PlanAgent().generate_48h_plan(db=db, family=family, signal=signal, context=context)

    profile_donts = family.child_profile.donts if family.child_profile else []
    safety = SafetyAgent().validate_plan(
        plan=plan,
        profile_donts=profile_donts,
        explicit_high_risk=payload.high_risk_selected,
        free_text=payload.free_text,
    )

    if safety.blocked:
        return Plan48hGenerateResponse(blocked=True, risk=signal, safety_block=safety.block)

    entity = Plan48h(
        family_id=payload.family_id,
        risk_level=signal.risk_level,
        actions_json={
            "today_cut_list": plan.today_cut_list,
            "priority_scenarios": plan.priority_scenarios,
            "exit_card_3steps": plan.exit_card_3steps,
            "action_steps": [item.model_dump() for item in plan.action_steps],
        },
        respite_json={"slots": [slot.model_dump() for slot in plan.respite_slots]},
        messages_json={"messages": [msg.model_dump() for msg in plan.messages], "tomorrow": plan.tomorrow_plan},
        safety_flags=plan.safety_flags,
        citations=plan.citations,
        blocked=False,
    )
    db.add(entity)
    db.flush()

    for idx, card_id in enumerate(plan.citations):
        db.add(PlanCardUse(plan_id=entity.plan_id, card_id=card_id, order_idx=idx + 1))

    db.commit()
    db.refresh(entity)

    return Plan48hGenerateResponse(blocked=False, plan_id=entity.plan_id, risk=signal, plan=plan)


@router.get("/{plan_id}", response_model=PlanRead)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PlanRead:
    plan = db.get(Plan48h, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    try:
        materialized = Plan48hResponse(
            today_cut_list=plan.actions_json.get("today_cut_list", []),
            priority_scenarios=plan.actions_json.get("priority_scenarios", ["transition"]),
            respite_slots=plan.respite_json.get("slots", []),
            messages=plan.messages_json.get("messages", []),
            exit_card_3steps=plan.actions_json.get(
                "exit_card_3steps",
                ["降刺激", "给选择", "安全退场"],
            ),
            tomorrow_plan=plan.messages_json.get("tomorrow", ["重复低刺激流程"]),
            action_steps=plan.actions_json.get("action_steps", []),
            citations=plan.citations,
            safety_flags=plan.safety_flags,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stored plan invalid schema: {exc}") from exc

    return PlanRead(plan_id=plan.plan_id, family_id=plan.family_id, risk_level=plan.risk_level, plan=materialized)
