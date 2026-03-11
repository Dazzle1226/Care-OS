from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date as date_type, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import DailyTrainingTask, Family, TrainingAdjustmentLog, TrainingPlanCycle, TrainingSkillState, TrainingTaskFeedback
from app.schemas.domain import (
    DailyTrainingTaskRead,
    TrainingAdjustmentLogRead,
    TrainingDashboardResponse,
    TrainingDashboardSummary,
    TrainingDomainDetailResponse,
    TrainingDomainProgress,
    TrainingFeedbackRead,
    TrainingMethodInsight,
    TrainingPriorityDomainCard,
    TrainingProgressOverview,
    TrainingTrendPoint,
)
from app.services.training_registry import get_domain


STAGE_LABELS = {
    "stabilize": "稳定期",
    "practice": "练习期",
    "generalize": "泛化期",
    "maintain": "维持期",
}

DIFFICULTY_LABELS = {
    "starter": "起步版",
    "build": "推进版",
    "advance": "进阶版",
}

LANGUAGE_LEVEL_LABELS = {
    "none": "无口语",
    "single_word": "单词",
    "short_sentence": "短句",
    "conversation": "对话",
}


def _serialize_feedback(item: TrainingTaskFeedback) -> TrainingFeedbackRead:
    return TrainingFeedbackRead(
        feedback_id=item.id,
        date=item.date,
        task_instance_id=item.task_instance_id,
        task_key=item.task_key,
        task_title=item.task_title,
        area_key=item.area_key,
        completion_status=item.completion_status,
        child_response=item.child_response,
        difficulty_rating=item.difficulty_rating,
        helpfulness=item.helpfulness,
        obstacle_tag=item.obstacle_tag,
        safety_pause=item.safety_pause,
        effect_score=item.effect_score,
        parent_confidence=item.parent_confidence,
        notes=item.notes,
    )


def _serialize_adjustment(item: TrainingAdjustmentLog) -> TrainingAdjustmentLogRead:
    return TrainingAdjustmentLogRead(
        adjustment_id=item.id,
        area_key=item.area_key,
        title=item.title,
        summary=item.summary,
        trigger=item.trigger,
        before_state=item.before_json,
        after_state=item.after_json,
        created_at=item.created_at,
    )


def _completion_rate(items: list[TrainingTaskFeedback]) -> int:
    if not items:
        return 0
    score = 0.0
    for item in items:
        if item.completion_status == "done":
            score += 1
        elif item.completion_status == "partial":
            score += 0.5
    return round((score / len(items)) * 100)


def _effective_rate(items: list[TrainingTaskFeedback]) -> int:
    if not items:
        return 0
    helpful = sum(1 for item in items if item.helpfulness == "helpful")
    return round((helpful / len(items)) * 100)


def _clean_text_list(values: list[object], *, limit: int) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in cleaned:
            continue
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _contains_keywords(values: list[str], keywords: list[str]) -> bool:
    joined = " ".join(item for item in values if item)
    return any(keyword in joined for keyword in keywords)


def _build_profile_reason(family: Family, area_key: str, state: TrainingSkillState) -> str | None:
    profile = family.child_profile
    if profile is None:
        return None

    context = profile.school_context or {}
    learning_needs = [str(item) for item in context.get("learning_needs", []) if isinstance(item, str)]
    behavior_patterns = [str(item) for item in context.get("behavior_patterns", []) if isinstance(item, str)]
    emotion_patterns = [str(item) for item in context.get("emotion_patterns", []) if isinstance(item, str)]
    social_training = [str(item) for item in context.get("social_training", []) if isinstance(item, str)]
    school_notes = str(context.get("school_notes") or "").strip()
    trigger_text = "、".join(profile.triggers[:2]) if profile.triggers else ""
    sensory_text = "、".join(profile.sensory_flags[:2]) if profile.sensory_flags else ""
    language_label = LANGUAGE_LEVEL_LABELS.get(profile.language_level, profile.language_level)
    base_pool = learning_needs + behavior_patterns + emotion_patterns + social_training + [school_notes]

    if area_key == "communication":
        if _contains_keywords(learning_needs + [school_notes], ["表达", "沟通", "理解", "请求", "语言"]):
            return "档案和学校记录里已经出现表达/理解困难，先把求助和拒绝的表达入口做稳定更贴近当前需要。"
        return f"目前以{language_label}表达为主，先把功能性沟通练稳定，更符合孩子现在的沟通能力。"
    if area_key == "transition_flexibility" and (
        "transition" in profile.high_friction_scenarios or _contains_keywords(profile.triggers + base_pool, ["过渡", "变动", "切换", "关屏", "出门"])
    ):
        return f"最近最容易卡在{trigger_text or state.recommended_scene}这类切换里，先练过渡更贴近孩子的真实高摩擦场景。"
    if area_key == "waiting_tolerance" and _contains_keywords(profile.triggers + base_pool, ["等待", "排队", "轮流"]):
        return "档案里已经反复出现等待/排队/轮流困难，这项训练更能直接降低外出和日常协作时的拉扯。"
    if area_key == "task_initiation" and _contains_keywords(base_pool, ["作业", "启动", "开始困难", "拖延", "坐下"]):
        return "家庭记录里已经多次提到任务开始困难，先把起步这一步做轻，会比一开始追求做完整体更有效。"
    if area_key == "bedtime_routine" and (
        "bedtime" in profile.high_friction_scenarios or _contains_keywords(profile.triggers + base_pool, ["睡前", "洗澡", "刷牙", "上床"])
    ):
        return "睡前流程已经是当前家庭的高摩擦时段，先练固定顺序和收尾动作，更容易减轻每天晚上的冲突。"
    if area_key == "daily_living" and _contains_keywords(base_pool, ["刷牙", "穿衣", "洗澡", "自理", "收拾"]):
        return "档案里已经出现自理流程卡住的问题，先把最常见的一步练顺，更能减轻家庭日常负担。"
    if area_key == "social_interaction" and _contains_keywords(base_pool, ["社交", "同伴", "轮流", "回应", "共同注意"]):
        return "当前档案已经把社交回应和轮流列入训练关注点，先在熟悉的人际场景里练这项更合适。"
    if area_key == "sensory_regulation" and profile.sensory_flags:
        return f"档案里记录了{sensory_text}等感官敏感，优先练降刺激和前兆识别，更符合孩子近期状态。"
    if area_key == "simple_compliance" and _contains_keywords(base_pool, ["听指令", "遵从", "配合", "指令"]):
        return "家庭记录里已经出现简单指令难进入，先把“一句一事”练稳，更容易提升日常协作。"
    if area_key == "emotion_regulation" and (emotion_patterns or _contains_keywords(profile.triggers + base_pool, ["焦虑", "崩溃", "情绪"])):
        return "档案里已经出现明显情绪波动线索，先练提前识别和降温动作，更能减少升级。"
    return None


def _build_feedback_reason(feedbacks: list[TrainingTaskFeedback]) -> str | None:
    if len(feedbacks) < 2:
        return None

    recent = feedbacks[:6]
    resistant_count = sum(1 for item in recent if item.child_response in {"resistant", "overloaded"})
    helpful_count = sum(1 for item in recent if item.helpfulness == "helpful")
    completion_rate = _completion_rate(recent)
    effective_rate = _effective_rate(recent)

    if resistant_count >= 2:
        return f"最近 {len(recent)} 次相关训练里有 {resistant_count} 次出现抗拒或过载，说明这项能力还需要继续优先并降低门槛。"
    if completion_rate <= 40:
        return f"最近 {len(recent)} 次相关训练完成率约 {completion_rate}%，继续优先这项更容易把训练重新带起来。"
    if helpful_count >= 2 and effective_rate >= 50:
        return f"最近 {len(recent)} 次相关训练里已有 {helpful_count} 次明确有效，值得继续在真实场景里放大成果。"
    return None


def _build_stage_reason(state: TrainingSkillState) -> str:
    stage_label = STAGE_LABELS.get(state.current_stage, state.current_stage)
    difficulty_label = DIFFICULTY_LABELS.get(state.current_difficulty, state.current_difficulty)
    scene = state.recommended_scene or "真实日常场景"
    if state.current_stage == "stabilize":
        return f"当前处于{stage_label}，建议先用{difficulty_label}在{scene}里把成功率做出来，再逐步加量。"
    if state.current_stage == "generalize":
        return f"当前已经进入{stage_label}，适合继续在{scene}这样的真实场景里扩展使用。"
    if state.current_stage == "maintain":
        return f"当前处于{stage_label}，继续把这项能力放回{scene}这样的日常场景，更容易守住已有进展。"
    return f"当前处于{stage_label}，在{scene}里按{difficulty_label}持续练，更容易把能力练稳。"


def _build_reason_for_priority(
    family: Family,
    area_key: str,
    state: TrainingSkillState,
    detail: dict[str, object],
    feedbacks: list[TrainingTaskFeedback],
) -> list[str]:
    raw_values = detail.get("reason_for_priority", [])
    raw_list = raw_values if isinstance(raw_values, list) else [raw_values]
    reasons = _clean_text_list(raw_list, limit=4)

    candidates = [
        state.reason_summary,
        _build_profile_reason(family=family, area_key=area_key, state=state),
        _build_feedback_reason(feedbacks),
        _build_stage_reason(state),
        state.risk_summary,
        get_domain(area_key).importance,
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        reasons = _clean_text_list([*reasons, candidate], limit=4)
        if len(reasons) >= 2:
            break

    return reasons


def _streak_days(items: list[TrainingTaskFeedback]) -> int:
    grouped = {item.date: any(feedback.completion_status in {"done", "partial"} for feedback in items if feedback.date == item.date) for item in items}
    streak = 0
    cursor = date_type.today()
    while grouped.get(cursor):
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _recent_trend(tasks: list[DailyTrainingTask], feedbacks: list[TrainingTaskFeedback]) -> list[TrainingTrendPoint]:
    feedback_by_date: dict[date_type, list[TrainingTaskFeedback]] = defaultdict(list)
    task_by_date: Counter[date_type] = Counter()
    for item in feedbacks:
        if item.date >= date_type.today() - timedelta(days=6):
            feedback_by_date[item.date].append(item)
    for item in tasks:
        if item.task_date >= date_type.today() - timedelta(days=6):
            task_by_date[item.task_date] += 1

    points: list[TrainingTrendPoint] = []
    for offset in range(6, -1, -1):
        day = date_type.today() - timedelta(days=offset)
        daily_feedbacks = feedback_by_date.get(day, [])
        completed_count = sum(item.completion_status in {"done", "partial"} for item in daily_feedbacks)
        total = max(task_by_date.get(day, 0), len(daily_feedbacks))
        rate = round((completed_count / total) * 100) if total else 0
        points.append(
            TrainingTrendPoint(
                label=f"{day.month}/{day.day}",
                completed_count=completed_count,
                task_count=total,
                completion_rate=rate,
            )
        )
    return points


def _method_insights(tasks: list[DailyTrainingTask], feedbacks: list[TrainingTaskFeedback]) -> list[TrainingMethodInsight]:
    task_map = {item.id: item for item in tasks}
    stats: dict[str, dict[str, int | str]] = {}
    for item in feedbacks:
        task = task_map.get(item.task_instance_id or -1)
        if task is None:
            key = item.task_title
            summary = "基于历史训练标题汇总出来的有效做法。"
        else:
            payload = task.task_json
            key = str(payload.get("title") or task.title)
            summary = f"更适合放在 {payload.get('training_scene', '日常场景')} 执行。"
        current = stats.setdefault(key, {"title": key, "summary": summary, "count": 0, "score": 0})
        current["count"] = int(current["count"]) + 1
        current["score"] = int(current["score"]) + (2 if item.helpfulness == "helpful" else 1 if item.completion_status == "done" else 0)

    ranked = sorted(stats.values(), key=lambda item: (int(item["score"]), int(item["count"])), reverse=True)[:3]
    return [
        TrainingMethodInsight(
            title=str(item["title"]),
            summary=str(item["summary"]),
            evidence_count=int(item["count"]),
            effectiveness_score=min(100, int(item["score"]) * 20),
        )
        for item in ranked
    ]


def _task_read(item: DailyTrainingTask) -> DailyTrainingTaskRead:
    payload = item.task_json
    reminder_status = item.reminder_status
    highlight = False
    if item.reminder_at and item.reminder_at <= datetime.utcnow() and item.status in {"pending", "scheduled"}:
        reminder_status = "due"
        highlight = True

    return DailyTrainingTaskRead(
        task_instance_id=item.id,
        area_key=item.area_key,
        area_title=get_domain(item.area_key).title,
        title=str(payload.get("title") or item.title),
        today_goal=str(payload.get("today_goal") or ""),
        training_scene=str(payload.get("training_scene") or ""),
        schedule_hint=str(payload.get("schedule_hint") or ""),
        steps=[str(step) for step in payload.get("steps", []) if isinstance(step, str)][:5],
        parent_script=str(payload.get("parent_script") or ""),
        duration_minutes=int(payload.get("duration_minutes") or 5),
        difficulty=str(payload.get("difficulty") or "starter"),
        materials=[str(material) for material in payload.get("materials", []) if isinstance(material, str)][:5],
        fallback_plan=str(payload.get("fallback_plan") or ""),
        coaching_tip=str(payload.get("coaching_tip") or ""),
        status=item.status,
        reminder_status=reminder_status,
        reminder_at=item.reminder_at,
        feedback_ready=True,
        highlight=highlight,
    )


def build_training_dashboard(
    db: Session,
    family: Family,
    cycle: TrainingPlanCycle,
) -> TrainingDashboardResponse:
    today = date_type.today()
    states = db.scalars(
        select(TrainingSkillState)
        .where(TrainingSkillState.family_id == family.family_id)
        .order_by(TrainingSkillState.priority_rank.asc(), TrainingSkillState.priority_score.desc())
    ).all()
    tasks = db.scalars(
        select(DailyTrainingTask)
        .where(DailyTrainingTask.family_id == family.family_id, DailyTrainingTask.task_date >= today - timedelta(days=6))
        .order_by(DailyTrainingTask.task_date.asc(), DailyTrainingTask.order_idx.asc())
    ).all()
    today_tasks = [item for item in tasks if item.task_date == today][:3]
    feedbacks = db.scalars(
        select(TrainingTaskFeedback)
        .where(TrainingTaskFeedback.family_id == family.family_id)
        .order_by(desc(TrainingTaskFeedback.date), desc(TrainingTaskFeedback.id))
    ).all()
    recent_adjustments = db.scalars(
        select(TrainingAdjustmentLog)
        .where(TrainingAdjustmentLog.family_id == family.family_id)
        .order_by(desc(TrainingAdjustmentLog.created_at))
        .limit(5)
    ).all()

    week_feedbacks = [item for item in feedbacks if item.date >= today - timedelta(days=6)]
    week_completed_count = sum(item.completion_status in {"done", "partial"} for item in week_feedbacks)
    progress_overview = TrainingProgressOverview(
        streak_days=_streak_days(week_feedbacks),
        weekly_completion_count=week_completed_count,
        seven_day_completion_rate=_completion_rate(week_feedbacks),
        recent_trend=_recent_trend(tasks, week_feedbacks),
        best_method_summary=_method_insights(tasks, week_feedbacks)[0].summary
        if _method_insights(tasks, week_feedbacks)
        else "先完成今天的一项任务，系统会开始识别更有效的方法。",
    )

    priority_domains = []
    today_area_keys = {item.area_key for item in today_tasks}
    for state in states[:3]:
        priority_domains.append(
            TrainingPriorityDomainCard(
                area_key=state.area_key,
                title=get_domain(state.area_key).title,
                priority_label="high" if state.priority_rank <= 2 else "medium",
                priority_score=state.priority_score,
                recommended_reason=state.reason_summary or get_domain(state.area_key).summary,
                current_stage=state.current_stage,
                current_difficulty=state.current_difficulty,
                weekly_sessions_count=state.weekly_sessions_count,
                has_today_task=state.area_key in today_area_keys,
                current_status=state.risk_summary or get_domain(state.area_key).importance,
                improvement_value=get_domain(state.area_key).importance,
            )
        )

    method_insights = _method_insights(tasks, week_feedbacks)
    safety_alert = next(
        (
            "最近训练反馈出现高风险/明显过载信号，建议先暂停普通训练并转入高摩擦或安全支持。"
            for item in week_feedbacks
            if item.safety_pause
        ),
        None,
    )

    return TrainingDashboardResponse(
        family_id=family.family_id,
        summary=TrainingDashboardSummary(
            week_completed_count=week_completed_count,
            priority_domain_count=len(priority_domains),
            streak_days=progress_overview.streak_days,
            current_load_level=cycle.load_level,
            summary_text=cycle.weekly_summary or "系统会根据孩子情况持续给出个性化训练建议。",
        ),
        priority_domains=priority_domains,
        today_tasks=[_task_read(item) for item in today_tasks],
        progress_overview=progress_overview,
        method_insights=method_insights,
        recent_adjustments=[_serialize_adjustment(item) for item in recent_adjustments],
        safety_alert=safety_alert,
    )


def build_training_domain_detail(
    db: Session,
    family: Family,
    area_key: str,
) -> TrainingDomainDetailResponse:
    state = db.scalar(
        select(TrainingSkillState).where(
            TrainingSkillState.family_id == family.family_id,
            TrainingSkillState.area_key == area_key,
        )
    )
    if state is None:
        raise ValueError("Training domain not found")

    detail = state.meta_json or {}
    feedbacks = db.scalars(
        select(TrainingTaskFeedback)
        .where(
            TrainingTaskFeedback.family_id == family.family_id,
            TrainingTaskFeedback.area_key == area_key,
        )
        .order_by(desc(TrainingTaskFeedback.date), desc(TrainingTaskFeedback.id))
        .limit(6)
    ).all()
    adjustments = db.scalars(
        select(TrainingAdjustmentLog)
        .where(
            TrainingAdjustmentLog.family_id == family.family_id,
            TrainingAdjustmentLog.area_key == area_key,
        )
        .order_by(desc(TrainingAdjustmentLog.created_at))
        .limit(6)
    ).all()
    reason_for_priority = _build_reason_for_priority(
        family=family,
        area_key=area_key,
        state=state,
        detail=detail,
        feedbacks=feedbacks,
    )

    return TrainingDomainDetailResponse(
        family_id=family.family_id,
        area_key=area_key,
        title=get_domain(area_key).title,
        current_stage=state.current_stage,
        current_difficulty=state.current_difficulty,
        importance_summary=str(detail.get("importance_summary") or get_domain(area_key).summary),
        related_daily_challenges=[str(item) for item in detail.get("related_daily_challenges", get_domain(area_key).related_challenges)][:4],
        reason_for_priority=reason_for_priority,
        current_risks=[str(item) for item in detail.get("current_risks", [state.risk_summary]) if str(item)][:3],
        short_term_goal=detail.get("short_term_goal"),
        medium_term_goal=detail.get("medium_term_goal"),
        training_principles=[str(item) for item in detail.get("training_principles", get_domain(area_key).principles)][:5],
        suggested_scenarios=[str(item) for item in detail.get("suggested_scenarios", get_domain(area_key).suggested_scenarios)][:4],
        parent_steps=[str(item) for item in detail.get("parent_steps", [])][:5],
        script_examples=[str(item) for item in detail.get("script_examples", [])][:3],
        fallback_options=[str(item) for item in detail.get("fallback_options", get_domain(area_key).fallback_options)][:3],
        cautions=[str(item) for item in detail.get("cautions", get_domain(area_key).cautions)][:4],
        progress=TrainingDomainProgress(
            current_stage=state.current_stage,
            current_difficulty=state.current_difficulty,
            weekly_sessions_count=state.weekly_sessions_count,
            total_completed_count=state.success_count,
            recent_completion_rate=_completion_rate(feedbacks),
            recent_effective_rate=_effective_rate(feedbacks),
        ),
        recent_feedbacks=[_serialize_feedback(item) for item in feedbacks],
        adjustment_logs=[_serialize_adjustment(item) for item in adjustments],
    )
