from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import Family, Plan48h, PlanCardUse, User
from app.schemas.domain import Plan48hGenerateRequest, Plan48hGenerateResponse, Plan48hResponse, PlanRead
from app.services.decision_orchestrator import DecisionOrchestrator

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

    result = DecisionOrchestrator().generate_plan(db=db, family=family, payload=payload)

    if result.safety.blocked:
        db.commit()
        return Plan48hGenerateResponse(
            blocked=True,
            risk=result.signal,
            safety_block=result.safety.block,
            evidence_bundle=result.evidence_bundle if payload.include_debug else None,
            decision_trace_id=result.trace_id if payload.include_debug else None,
            decision_summary=result.safety_review.summary if payload.include_debug else None,
        )
    if result.evidence_review.blocked:
        db.commit()
        raise HTTPException(status_code=422, detail=result.evidence_review.summary)

    entity = Plan48h(
        family_id=payload.family_id,
        risk_level=result.signal.risk_level,
        actions_json={
            "today_cut_list": result.plan.today_cut_list,
            "priority_scenarios": result.plan.priority_scenarios,
            "exit_card_3steps": result.plan.exit_card_3steps,
            "action_steps": [item.model_dump() for item in result.plan.action_steps],
        },
        respite_json={"slots": [slot.model_dump() for slot in result.plan.respite_slots]},
        messages_json={"messages": [msg.model_dump() for msg in result.plan.messages], "tomorrow": result.plan.tomorrow_plan},
        safety_flags=result.plan.safety_flags,
        citations=result.plan.citations,
        blocked=False,
    )
    db.add(entity)
    db.flush()

    for idx, card_id in enumerate(result.plan.citations):
        db.add(PlanCardUse(plan_id=entity.plan_id, card_id=card_id, order_idx=idx + 1))

    db.commit()
    db.refresh(entity)

    return Plan48hGenerateResponse(
        blocked=False,
        plan_id=entity.plan_id,
        risk=result.signal,
        plan=result.plan,
        evidence_bundle=result.evidence_bundle if payload.include_debug else None,
        decision_trace_id=result.trace_id if payload.include_debug else None,
        decision_summary=(
            "规则降级已触发，但证据链和安全审查通过。"
            if payload.include_debug and result.fallback_reason
            else (result.evidence_bundle.ranking_summary if payload.include_debug else None)
        ),
    )


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
