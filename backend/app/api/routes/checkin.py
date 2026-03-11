from __future__ import annotations

from datetime import date as date_type
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.coach import CoachAgent, TodayFocusContext
from app.agents.plan import PlanAgent, PlanContext
from app.agents.signal import SignalAgent
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import DailyCheckin, Family, IncidentLog, User
from app.schemas.domain import (
    CheckinCreate,
    CheckinRead,
    CheckinResponse,
    CheckinTodayResponse,
    DailyActionPlan,
    RiskResponse,
    SignalOutput,
)

router = APIRouter(tags=["checkin"])
OPTIONAL_SCORE_FALLBACK = 6.0


def _read_optional_score(details: dict[str, object], key: str, fallback: float | None) -> float | None:
    if key not in details:
        return fallback
    value = details.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _serialize_checkin(checkin: DailyCheckin) -> CheckinRead:
    details = checkin.details_json or {}
    child_sleep_quality = _read_optional_score(details, "child_sleep_quality", OPTIONAL_SCORE_FALLBACK)
    transition_difficulty = _read_optional_score(details, "transition_difficulty", checkin.transition_difficulty)
    return CheckinRead(
        checkin_id=checkin.id,
        date=checkin.date,
        child_sleep_hours=checkin.child_sleep_hours,
        child_sleep_quality=child_sleep_quality,
        sleep_issues=list(details.get("sleep_issues", [])),
        meltdown_count=checkin.meltdown_count,
        child_mood_state=cast(str, details.get("child_mood_state", "stable")),
        physical_discomforts=list(details.get("physical_discomforts", [])),
        aggressive_behaviors=list(details.get("aggressive_behaviors", [])),
        negative_emotions=list(details.get("negative_emotions", [])),
        transition_difficulty=transition_difficulty,
        sensory_overload_level=cast(str, checkin.sensory_overload_level),
        caregiver_stress=checkin.caregiver_stress,
        caregiver_sleep_quality=checkin.caregiver_sleep_hours,
        support_available=cast(str, checkin.support_available),
        today_activities=list(details.get("today_activities", [])),
        today_learning_tasks=list(details.get("today_learning_tasks", [])),
    )


def _resolve_priority_scenario(checkin: DailyCheckin, recent_scenario: str | None) -> str | None:
    details = checkin.details_json or {}
    transition_difficulty = _read_optional_score(details, "transition_difficulty", checkin.transition_difficulty)
    today_activities = set(details.get("today_activities", []))
    negative_emotions = set(details.get("negative_emotions", []))
    learning_tasks = set(details.get("today_learning_tasks", []))
    if (transition_difficulty is not None and transition_difficulty >= 7) or checkin.meltdown_count >= 2:
        return "transition"
    if any(item in today_activities for item in ["医生预约", "社交活动", "外出安排", "学校活动"]):
        return "outing"
    if any(item in negative_emotions for item in ["焦虑", "恐惧", "社交回避"]):
        return "outing"
    if learning_tasks:
        return "homework"
    if checkin.sensory_overload_level in {"medium", "heavy"}:
        return "outing"
    if checkin.child_sleep_hours <= 5 or checkin.caregiver_sleep_hours <= 4:
        return "bedtime"
    return recent_scenario


def _checkin_context_text(checkin: DailyCheckin) -> str:
    details = checkin.details_json or {}
    child_sleep_quality = _read_optional_score(details, "child_sleep_quality", OPTIONAL_SCORE_FALLBACK)
    transition_difficulty = _read_optional_score(details, "transition_difficulty", checkin.transition_difficulty)
    sensory_label = {
        "none": "无",
        "light": "轻微",
        "medium": "中等",
        "heavy": "严重",
    }.get(checkin.sensory_overload_level, "未知")
    support_label = {
        "none": "无",
        "one": "有 1 人",
        "two_plus": "有 2 人以上",
    }.get(checkin.support_available, "未知")
    meltdown_label = "3+ 次" if checkin.meltdown_count >= 3 else f"{checkin.meltdown_count} 次"
    mood_label = {
        "stable": "稳定",
        "sensitive": "敏感",
        "anxious": "焦虑",
        "low_energy": "低能量",
        "irritable": "烦躁",
    }.get(str(details.get("child_mood_state", "stable")), "稳定")
    sleep_issues = "、".join(details.get("sleep_issues", [])) or "无明显困扰"
    physical_discomforts = "、".join(details.get("physical_discomforts", [])) or "无明显身体不适"
    aggressive_behaviors = "、".join(details.get("aggressive_behaviors", [])) or "未见明显过激行为"
    negative_emotions = "、".join(details.get("negative_emotions", [])) or "未见明显负面情绪"
    today_activities = "、".join(details.get("today_activities", [])) or "无特殊安排"
    today_learning_tasks = "、".join(details.get("today_learning_tasks", [])) or "无明确训练任务"
    child_sleep_quality_text = f"{child_sleep_quality:g}/10" if child_sleep_quality is not None else "未填写"
    transition_difficulty_text = f"{transition_difficulty:g}/10" if transition_difficulty is not None else "未填写"

    return (
        "请基于今日签到生成中文、极简、立刻可执行的照护行动计划。"
        f"孩子昨晚睡眠 {checkin.child_sleep_hours:g} 小时，感官过载 {sensory_label}，"
        f"睡眠质量 {child_sleep_quality_text}，睡眠困扰：{sleep_issues}；"
        f"当前精神状态 {mood_label}，身体不适：{physical_discomforts}；"
        f"昨日过激行为：{aggressive_behaviors}；负面情绪：{negative_emotions}；"
        f"冲突/崩溃 {meltdown_label}，过渡难度 {transition_difficulty_text}；"
        f"家长压力 {checkin.caregiver_stress:g}/10，可用支持 {support_label}，"
        f"睡眠质量 {checkin.caregiver_sleep_hours:g}/10；"
        f"今日安排：{today_activities}；学习/训练：{today_learning_tasks}。"
    )


def _build_today_focus_context(checkin: DailyCheckin, signal: SignalOutput, recent_scenario: str | None) -> TodayFocusContext:
    details = checkin.details_json or {}
    transition_difficulty = _read_optional_score(details, "transition_difficulty", checkin.transition_difficulty)
    return TodayFocusContext(
        risk_level=signal.risk_level,
        reasons=signal.reasons,
        recent_scenario=recent_scenario,
        sensory_overload_level=cast(str, checkin.sensory_overload_level),
        meltdown_count=checkin.meltdown_count,
        transition_difficulty=transition_difficulty,
        child_sleep_hours=checkin.child_sleep_hours,
        caregiver_sleep_quality=checkin.caregiver_sleep_hours,
        caregiver_stress=checkin.caregiver_stress,
        support_available=cast(str, checkin.support_available),
        child_mood_state=cast(str, details.get("child_mood_state", "stable")),
        negative_emotions=list(details.get("negative_emotions", [])),
        today_activities=list(details.get("today_activities", [])),
        today_learning_tasks=list(details.get("today_learning_tasks", [])),
    )


def _build_daily_action_plan(
    db: Session,
    family: Family,
    checkin: DailyCheckin,
    signal: SignalOutput,
    recent_scenario: str | None,
    today_focus,
) -> DailyActionPlan:
    scenario = _resolve_priority_scenario(checkin, recent_scenario)
    context = PlanContext(
        family_id=family.family_id,
        scenario=scenario,
        intensity="heavy" if signal.risk_level == "red" else "medium",
        support_hint=checkin.support_available,
        free_text=_checkin_context_text(checkin),
    )
    plan = PlanAgent().generate_48h_plan(
        db=db,
        family=family,
        signal=signal,
        context=context,
    )

    three_step_action = [item.step for item in plan.action_steps[:3]]
    for fallback_step in plan.exit_card_3steps:
        if len(three_step_action) >= 3:
            break
        three_step_action.append(fallback_step)

    slot = plan.respite_slots[0]
    summary_bits = signal.reasons[:1] if signal.reasons else ["当前以低刺激和减负为主"]
    return DailyActionPlan(
        headline=today_focus.headline,
        summary=f"{summary_bits[0]}。{today_focus.today_one_thing}",
        reminders=today_focus.reminders,
        three_step_action=three_step_action[:3],
        parent_phrase=plan.action_steps[0].script if plan.action_steps else "我知道你现在有点难，我们先做第一步，我会陪你。",
        meltdown_fallback=plan.exit_card_3steps[:3],
        respite_suggestion=f"建议安排 {slot.duration_minutes} 分钟{slot.resource}，家长只保留一个最小目标。",
        plan_overview=plan.today_cut_list[:3],
    )


def _build_checkin_result(
    db: Session,
    family: Family,
    checkin: DailyCheckin,
) -> tuple[SignalOutput, str, DailyActionPlan]:
    signal = SignalAgent().evaluate(db=db, family_id=family.family_id, target_date=checkin.date)
    latest_incident = db.scalar(
        select(IncidentLog).where(IncidentLog.family_id == family.family_id).order_by(desc(IncidentLog.ts)).limit(1)
    )
    recent_scenario = latest_incident.scenario if latest_incident else None
    today_focus = CoachAgent().generate_today_focus(_build_today_focus_context(checkin, signal, recent_scenario))
    action_plan = _build_daily_action_plan(
        db=db,
        family=family,
        checkin=checkin,
        signal=signal,
        recent_scenario=recent_scenario,
        today_focus=today_focus,
    )
    return signal, today_focus.today_one_thing, action_plan


@router.post("/checkin", response_model=CheckinResponse)
def create_checkin(
    payload: CheckinCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CheckinResponse:
    family = db.get(Family, payload.family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    target_date = payload.date or date_type.today()
    checkin = db.scalar(
        select(DailyCheckin).where(
            DailyCheckin.family_id == payload.family_id,
            DailyCheckin.date == target_date,
        )
    )
    if checkin is None:
        checkin = DailyCheckin(family_id=payload.family_id, date=target_date)
        db.add(checkin)

    checkin.child_sleep_hours = payload.child_sleep_hours
    checkin.meltdown_count = payload.meltdown_count
    checkin.transition_difficulty = payload.transition_difficulty if payload.transition_difficulty is not None else OPTIONAL_SCORE_FALLBACK
    checkin.sensory_overload_level = payload.sensory_overload_level
    checkin.caregiver_stress = payload.caregiver_stress
    checkin.caregiver_sleep_hours = payload.caregiver_sleep_quality
    checkin.support_available = payload.support_available
    checkin.env_changes = payload.env_changes
    checkin.details_json = {
        "child_sleep_quality": payload.child_sleep_quality,
        "sleep_issues": payload.sleep_issues,
        "child_mood_state": payload.child_mood_state,
        "physical_discomforts": payload.physical_discomforts,
        "aggressive_behaviors": payload.aggressive_behaviors,
        "negative_emotions": payload.negative_emotions,
        "transition_difficulty": payload.transition_difficulty,
        "today_activities": payload.today_activities,
        "today_learning_tasks": payload.today_learning_tasks,
    }

    db.flush()
    signal, today_one_thing, action_plan = _build_checkin_result(db=db, family=family, checkin=checkin)
    db.commit()
    db.refresh(checkin)

    return CheckinResponse(
        checkin_id=checkin.id,
        checkin=_serialize_checkin(checkin),
        risk=signal,
        today_one_thing=today_one_thing,
        action_plan=action_plan,
    )


@router.get("/checkin/today/{family_id}", response_model=CheckinTodayResponse)
def get_today_checkin(
    family_id: int,
    date: date_type | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CheckinTodayResponse:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    target_date = date or date_type.today()
    checkin = db.scalar(
        select(DailyCheckin).where(
            DailyCheckin.family_id == family_id,
            DailyCheckin.date == target_date,
        )
    )
    if checkin is None:
        return CheckinTodayResponse(family_id=family_id, date=target_date, needs_checkin=True)

    signal, today_one_thing, action_plan = _build_checkin_result(db=db, family=family, checkin=checkin)
    return CheckinTodayResponse(
        family_id=family_id,
        date=target_date,
        needs_checkin=False,
        checkin=_serialize_checkin(checkin),
        risk=signal,
        today_one_thing=today_one_thing,
        action_plan=action_plan,
    )


@router.get("/risk/{family_id}", response_model=RiskResponse)
def get_risk(
    family_id: int,
    date: date_type | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RiskResponse:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    risk = SignalAgent().evaluate(db=db, family_id=family_id, target_date=date)
    return RiskResponse(family_id=family_id, date=date or date_type.today(), risk=risk)
