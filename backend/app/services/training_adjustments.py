from __future__ import annotations

from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models import DailyTrainingTask, Family, TrainingAdjustmentLog, TrainingSkillState, TrainingTaskFeedback

RISK_NOTE_KEYWORDS = ("崩溃", "打人", "自伤", "撞头", "咬人", "逃跑", "危险", "窒息", "伤人")
OVERLOAD_NOTE_KEYWORDS = ("太难", "太累", "烦躁", "很抗拒", "不愿意", "过载")

STAGE_ORDER = ["stabilize", "practice", "generalize", "maintain"]
DIFFICULTY_ORDER = ["starter", "build", "advance"]


def derive_feedback_metrics(
    completion_status: str,
    child_response: str,
    helpfulness: str,
    obstacle_tag: str,
    notes: str,
) -> tuple[str, float, float, bool]:
    if obstacle_tag == "too_hard":
        difficulty_rating = "too_hard"
    elif helpfulness == "helpful" and completion_status == "done":
        difficulty_rating = "just_right"
    else:
        difficulty_rating = "just_right"

    base_effect = {
        "helpful": 8.0,
        "neutral": 5.0,
        "not_helpful": 2.0,
    }[helpfulness]
    if completion_status == "partial":
        base_effect -= 1.5
    elif completion_status == "missed":
        base_effect -= 3.0
    if child_response == "overloaded":
        base_effect -= 2.0
    elif child_response == "resistant":
        base_effect -= 1.0

    confidence = {
        "done": 8.0,
        "partial": 5.5,
        "missed": 3.0,
    }[completion_status]
    if obstacle_tag in {"too_hard", "parent_overloaded", "wrong_timing", "sensory_overload"}:
        confidence -= 1.5
    confidence = max(0.0, min(10.0, confidence))
    effect_score = max(0.0, min(10.0, base_effect))

    note_text = notes.strip()
    safety_pause = obstacle_tag == "sensory_overload" or any(keyword in note_text for keyword in RISK_NOTE_KEYWORDS)
    return difficulty_rating, effect_score, confidence, safety_pause


def _move_stage(current: str, direction: int) -> str:
    try:
        index = STAGE_ORDER.index(current)
    except ValueError:
        index = 0
    return STAGE_ORDER[max(0, min(len(STAGE_ORDER) - 1, index + direction))]


def _move_difficulty(current: str, direction: int) -> str:
    try:
        index = DIFFICULTY_ORDER.index(current)
    except ValueError:
        index = 0
    return DIFFICULTY_ORDER[max(0, min(len(DIFFICULTY_ORDER) - 1, index + direction))]


def apply_feedback_adjustment(
    db: Session,
    family: Family,
    task: DailyTrainingTask,
    feedback: TrainingTaskFeedback,
) -> tuple[str, str | None]:
    state = db.scalar(
        select(TrainingSkillState).where(
            TrainingSkillState.family_id == family.family_id,
            TrainingSkillState.area_key == task.area_key,
        )
    )
    if state is None:
        return "继续保持当前安排，先观察接下来 1-2 次训练反馈。", None

    before = {
        "stage": state.current_stage,
        "difficulty": state.current_difficulty,
        "recommended_time": state.recommended_time,
        "recommended_scene": state.recommended_scene,
    }

    recent_same_area = db.scalars(
        select(TrainingTaskFeedback)
        .where(
            TrainingTaskFeedback.family_id == family.family_id,
            TrainingTaskFeedback.area_key == task.area_key,
            TrainingTaskFeedback.id != feedback.id,
            TrainingTaskFeedback.date >= feedback.date - timedelta(days=7),
        )
        .order_by(desc(TrainingTaskFeedback.date), desc(TrainingTaskFeedback.id))
        .limit(4)
    ).all()

    note_text = feedback.notes.strip()
    adjustment_title = "保持当前节奏"
    adjustment_summary = "当前反馈还不足以触发调整，先继续观察同一能力在同一场景下的表现。"
    safety_alert: str | None = None

    if feedback.safety_pause:
        state.current_stage = "stabilize"
        state.current_difficulty = "starter"
        adjustment_title = "暂停普通升级"
        adjustment_summary = "检测到高风险或明显过载信号，普通训练先暂停，建议先转入高摩擦/安全支持流程。"
        safety_alert = adjustment_summary
    elif (
        feedback.helpfulness == "helpful"
        and feedback.completion_status == "done"
        and feedback.child_response in {"engaged", "accepted"}
        and any(
            item.helpfulness == "helpful"
            and item.completion_status == "done"
            and item.child_response in {"engaged", "accepted"}
            for item in recent_same_area[:2]
        )
    ):
        if state.current_difficulty != "advance":
            state.current_difficulty = _move_difficulty(state.current_difficulty, 1)
            adjustment_title = "逐步升级难度"
            adjustment_summary = "因为连续两次完成顺利且反馈有帮助，系统把难度上调了一个档位。"
        else:
            state.current_stage = _move_stage(state.current_stage, 1)
            adjustment_title = "进入下一阶段"
            adjustment_summary = "因为连续两次完成稳定，系统把训练阶段推进到更接近泛化的一层。"
    elif (
        feedback.completion_status in {"partial", "missed"}
        or feedback.child_response in {"resistant", "overloaded"}
        or feedback.helpfulness == "not_helpful"
        or feedback.obstacle_tag in {"too_hard", "parent_overloaded", "wrong_timing", "sensory_overload"}
    ):
        if feedback.obstacle_tag == "wrong_timing":
            state.recommended_time = "改到更稳定、要求更少的时段"
            adjustment_title = "调整训练时段"
            adjustment_summary = "因为当前时段不合适，系统把推荐训练时段改成更容易开始的时段。"
        elif feedback.obstacle_tag == "parent_overloaded":
            state.current_stage = "stabilize"
            state.current_difficulty = "starter"
            adjustment_title = "减轻家长负担"
            adjustment_summary = "因为家长连续感到吃力，系统先把训练退回低负担版本。"
        else:
            state.current_difficulty = _move_difficulty(state.current_difficulty, -1)
            state.current_stage = "stabilize"
            adjustment_title = "先降级再稳定"
            adjustment_summary = "因为近期训练偏难或孩子抗拒较高，系统先做降级处理，缩短任务并退回更低负担、更容易开始的版本。"
    elif any(keyword in note_text for keyword in OVERLOAD_NOTE_KEYWORDS):
        state.current_difficulty = "starter"
        adjustment_title = "按备注降负荷"
        adjustment_summary = "备注里出现了明显吃力/烦躁信号，系统先按低负担模式重新安排。"

    two_recent_missed = [feedback] + recent_same_area[:2]
    if sum(item.completion_status == "missed" for item in two_recent_missed) >= 2:
        state.current_difficulty = "starter"
        state.current_stage = "stabilize"
        state.recommended_time = "改到更容易开始的固定时段"
        adjustment_title = "连续未完成后减量"
        adjustment_summary = "因为连续两天未完成，系统已经减少负担并建议重新固定训练时段。"

    state.last_adjusted_at = utc_now()

    after = {
        "stage": state.current_stage,
        "difficulty": state.current_difficulty,
        "recommended_time": state.recommended_time,
        "recommended_scene": state.recommended_scene,
    }

    if before != after or adjustment_title != "保持当前节奏":
        db.add(
            TrainingAdjustmentLog(
                family_id=family.family_id,
                area_key=task.area_key,
                task_instance_id=task.id,
                feedback_id=feedback.id,
                title=adjustment_title,
                summary=adjustment_summary,
                trigger=feedback.obstacle_tag if feedback.obstacle_tag != "none" else feedback.helpfulness,
                before_json=before,
                after_json=after,
            )
        )

    task.status = feedback.completion_status
    task.feedback_submitted = True
    task.reminder_status = "none"
    task.reminder_at = None
    return adjustment_summary, safety_alert
