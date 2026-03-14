from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.time import utc_now
from app.db.base import get_db
from app.models import Family, IncidentLog, Plan48h, PlanCardUse, User
from app.schemas.domain import (
    V2FrictionSupportGenerateResponse,
    V2GenerateFrictionSupportRequest,
    V2GeneratePlanRequest,
    V2GenerateScriptRequest,
    V2PlanGenerateResponse,
    V2ScriptGenerateResponse,
)
from app.services.decision_orchestrator import DecisionOrchestrator

router = APIRouter(prefix="/v2", tags=["v2-generation"])


def _friction_incident_scenario(payload: V2GenerateFrictionSupportRequest) -> str:
    return payload.custom_scenario.strip() or payload.scenario


def _friction_intensity(payload: V2GenerateFrictionSupportRequest) -> str:
    if (
        payload.low_stim_mode_requested
        or payload.quick_preset == "meltdown_now"
        or payload.child_state == "meltdown"
        or payload.sensory_overload_level == "heavy"
        or payload.meltdown_count >= 2
        or payload.caregiver_stress >= 8
    ):
        return "heavy"
    if payload.transition_difficulty >= 6 or payload.caregiver_fatigue >= 7:
        return "medium"
    return "light"


@router.post("/plan48h/generate", response_model=V2PlanGenerateResponse)
def generate_plan_v2(
    payload: V2GeneratePlanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V2PlanGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    result = DecisionOrchestrator().generate_plan(db=db, family=family, payload=payload, ingestion_ids=payload.ingestion_ids)
    if result.evidence_review.blocked:
        db.commit()
        raise HTTPException(status_code=422, detail=result.evidence_review.summary)

    if result.safety.blocked:
        db.commit()
        return V2PlanGenerateResponse(
            blocked=True,
            risk=result.signal,
            safety_block=result.safety.block,
            trace_id=result.trace_id,
            stage_summaries=result.stage_runs,
            fallback_summary=result.fallback_reason,
            insufficient_evidence=result.insufficient_evidence,
            evidence_bundle=result.evidence_bundle,
        )

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
    return V2PlanGenerateResponse(
        blocked=False,
        plan_id=entity.plan_id,
        risk=result.signal,
        plan=result.plan,
        trace_id=result.trace_id,
        stage_summaries=result.stage_runs,
        fallback_summary=result.fallback_reason,
        insufficient_evidence=result.insufficient_evidence,
        evidence_bundle=result.evidence_bundle,
    )


@router.post("/scripts/generate", response_model=V2ScriptGenerateResponse)
def generate_script_v2(
    payload: V2GenerateScriptRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V2ScriptGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    result = DecisionOrchestrator().generate_script(db=db, family=family, payload=payload, ingestion_ids=payload.ingestion_ids)
    db.add(
        IncidentLog(
            family_id=payload.family_id,
            ts=utc_now(),
            scenario=payload.scenario,
            intensity=payload.intensity,
            triggers=[],
            selected_resources={"ingestion_ids": payload.ingestion_ids},
            high_risk_flag=payload.high_risk_selected,
            notes=payload.free_text,
        )
    )
    if result.evidence_review.blocked:
        db.commit()
        raise HTTPException(status_code=422, detail=result.evidence_review.summary)
    if result.safety.blocked:
        db.commit()
        return V2ScriptGenerateResponse(
            blocked=True,
            safety_block=result.safety.block,
            trace_id=result.trace_id,
            stage_summaries=result.stage_runs,
            fallback_summary=result.fallback_reason,
            insufficient_evidence=result.insufficient_evidence,
            evidence_bundle=result.evidence_bundle,
        )

    db.commit()
    return V2ScriptGenerateResponse(
        blocked=False,
        script=result.script,
        trace_id=result.trace_id,
        stage_summaries=result.stage_runs,
        fallback_summary=result.fallback_reason,
        insufficient_evidence=result.insufficient_evidence,
        evidence_bundle=result.evidence_bundle,
    )


@router.post("/scripts/friction-support", response_model=V2FrictionSupportGenerateResponse)
def generate_friction_support_v2(
    payload: V2GenerateFrictionSupportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> V2FrictionSupportGenerateResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    result = DecisionOrchestrator().generate_friction_support(
        db=db,
        family=family,
        payload=payload,
        ingestion_ids=payload.ingestion_ids,
    )
    if result.evidence_review.blocked:
        db.commit()
        raise HTTPException(status_code=422, detail=result.evidence_review.summary)
    if result.safety.blocked:
        db.commit()
        return V2FrictionSupportGenerateResponse(
            blocked=True,
            risk=result.signal,
            safety_block=result.safety.block,
            trace_id=result.trace_id,
            stage_summaries=result.stage_runs,
            fallback_summary=None,
            insufficient_evidence=result.insufficient_evidence,
            evidence_bundle=result.evidence_bundle,
        )

    incident = IncidentLog(
        family_id=payload.family_id,
        ts=utc_now(),
        scenario=_friction_incident_scenario(payload),
        intensity=_friction_intensity(payload),
        triggers=[payload.child_state, *payload.env_changes[:2]],
        selected_resources={
            "base_scenario": payload.scenario,
            "source_card_ids": result.support.source_card_ids,
            "ingestion_ids": payload.ingestion_ids,
        },
        high_risk_flag=payload.high_risk_selected,
        notes=payload.free_text,
    )
    db.add(incident)
    db.flush()
    db.commit()
    return V2FrictionSupportGenerateResponse(
        blocked=False,
        incident_id=incident.id,
        risk=result.signal,
        support=result.support,
        trace_id=result.trace_id,
        stage_summaries=result.stage_runs,
        fallback_summary=None,
        insufficient_evidence=result.insufficient_evidence,
        evidence_bundle=result.evidence_bundle,
    )
