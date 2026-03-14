from __future__ import annotations

import json
from datetime import date as date_type, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models import ChildProfile, DailyTrainingTask, Family, TrainingPlanCycle, TrainingSkillState
from app.services.training_coordination import TrainingCoordinationResult
from app.services.llm_client import LLMClient, LLMUnavailableError
from app.services.training_assessment import AssessmentResult, DomainAssessment
from app.services.training_registry import get_domain


def _first(values: list[str], fallback: str) -> str:
    for value in values:
        if value:
            return value
    return fallback


def _task_count(load_level: str) -> int:
    return {"light": 1, "standard": 2, "adaptive": 3}[load_level]


def _build_goals(area_key: str, area: DomainAssessment) -> tuple[dict[str, str], dict[str, str]]:
    domain = get_domain(area_key)
    short_goal = {
        "title": f"本周先稳住 {domain.title}",
        "target": f"这一周先把 {domain.title} 放回可开始、可结束、可复用的状态。",
        "success_marker": "本周至少出现 3 次完成或部分完成，并留下 1 条有效做法。",
    }
    medium_goal = {
        "title": f"本月让 {domain.title} 能迁移到真实场景",
        "target": f"让 {domain.title} 从练习卡片，逐步迁移到家庭里最常见的真实困难场景。",
        "success_marker": "在 2 个以上真实场景里出现更快进入或更少升级。",
    }
    if area.stage == "generalize":
        medium_goal["success_marker"] = "能在不同照护者或不同情境下继续保持稳定。"
    return short_goal, medium_goal


def _build_domain_plan(
    area_key: str,
    area: DomainAssessment,
    profile: ChildProfile,
    context: dict[str, Any],
) -> dict[str, Any]:
    domain = get_domain(area_key)
    child_name = str(context.get("child_name") or "").strip() or "孩子"
    preferred_item = _first(
        [str(item) for item in context.get("interests", []) if isinstance(item, str)]
        + [str(item) for item in context.get("likes", []) if isinstance(item, str)],
        "喜欢的东西",
    )
    supporter = _first([str(item) for item in context.get("available_supporters", []) if isinstance(item, str)], "家长")
    short_goal, medium_goal = _build_goals(area_key, area)

    parent_steps_map = {
        "emotion_regulation": [
            "先帮孩子命名当前状态，不追问原因。",
            "给两个固定降温动作，只让孩子选一个。",
            "结束后只记录哪一步最有帮助。",
        ],
        "transition_flexibility": [
            "切换前先做一次清晰预告。",
            "用先后卡或倒计时，让孩子能看到接下来会发生什么。",
            "切换一完成就给简短确认，不再追加要求。",
        ],
        "communication": [
            "制造一个自然请求机会。",
            "只给一个到两个表达入口，不开放追问。",
            "孩子一有主动表达就立刻回应并示范更完整版本。",
        ],
        "waiting_tolerance": [
            "等待从极短时长开始。",
            "等待时给手上可做的小动作。",
            "一旦做到就马上确认‘你做到了等待’。",
        ],
        "task_initiation": [
            "把任务压缩成第一步。",
            "先陪孩子开始，不追求一次完成全部。",
            "做完第一步就停，保留成功感。",
        ],
        "bedtime_routine": [
            "睡前流程保持同样顺序。",
            "每晚只练一个卡点，不同时优化多个环节。",
            "状态差时优先缩流程，而不是硬撑完整流程。",
        ],
        "daily_living": [
            "把自理任务拆成看得懂的小步骤。",
            "先练一个环节，别一次练完整流程。",
            "同一句提示词连续用几天，减少变化。",
        ],
        "social_interaction": [
            "只做短回合互动。",
            "先共同注意，再加轮流。",
            "结束时一起回看刚才做到的那一步。",
        ],
        "sensory_regulation": [
            "先找过载前兆。",
            "一出现信号就做固定降载动作。",
            "把环境调整视为训练的一部分。",
        ],
        "simple_compliance": [
            "一次只说一个动作。",
            "必要时用动作示范配合语言。",
            "孩子一做出动作就立刻确认，不继续连发指令。",
        ],
    }
    script_map = {
        "emotion_regulation": [
            f"{child_name}，我看到你有点不舒服，我们先选一个让身体慢下来的办法。",
            "我们先让身体安全下来，等会儿再说后面的事。",
        ],
        "transition_flexibility": [
            "还有一点时间就要切换了，我会先告诉你，再陪你做最后一步。",
            "先做这个，再做下一个，做完我们就停。",
        ],
        "communication": [
            "你可以指给我看，或者告诉我‘要这个/不要这个’，我会马上帮你。",
            "先用你现在最容易的方式告诉我，我会听。",
        ],
        "waiting_tolerance": [
            "现在先等一下，我们一起看着倒计时，到了就轮到你。",
            "你已经在等了，我们只等很短一下。",
        ],
        "task_initiation": [
            "今天我们只先做第一小步，做完就算开始成功。",
            "你不用一次做完，我们只先开始。",
        ],
        "bedtime_routine": [
            "我们照着这张睡前卡，一步一步来，今晚只先把这一环做好。",
            "先做这一件，做完就往下走，不赶。",
        ],
        "daily_living": [
            "今天先练这一小步，做到就很好。",
            "我先示范一次，然后你试一下。",
        ],
        "social_interaction": [
            "现在轮到你一下，我做完就再轮到你，我们只玩三个回合。",
            "我们先一起看同一个东西，再轮流一次。",
        ],
        "sensory_regulation": [
            "一觉得太吵或太累，我们先做固定的安静动作。",
            "身体在提醒我们了，先降一点刺激。",
        ],
        "simple_compliance": [
            "现在只做这一件：先把这个放进去。",
            "你先跟我做同一个动作，做完就停。",
        ],
    }

    return {
        "importance_summary": domain.summary,
        "reason_for_priority": area.reasons[:3],
        "related_daily_challenges": list(domain.related_challenges),
        "current_risks": [area.current_status, f"当前建议场景：{area.recommended_scene}"],
        "short_term_goal": short_goal,
        "medium_term_goal": medium_goal,
        "training_principles": list(domain.principles),
        "suggested_scenarios": list(domain.suggested_scenarios),
        "parent_steps": parent_steps_map[area_key],
        "script_examples": script_map[area_key],
        "fallback_options": list(domain.fallback_options),
        "cautions": list(domain.cautions),
        "method_examples": list(domain.method_examples),
        "importance": domain.importance,
        "best_method": area.best_method or domain.method_examples[0],
        "current_status": area.current_status,
        "improvement_value": area.improvement_value,
        "preferred_item": preferred_item,
        "supporter": supporter,
        "language_level": profile.language_level,
    }


def _build_task_snapshot(
    area_key: str,
    area: DomainAssessment,
    detail: dict[str, Any],
) -> dict[str, Any]:
    preferred_item = str(detail["preferred_item"])
    supporter = str(detail["supporter"])
    duration_map = {"starter": 5, "build": 8, "advance": 10}
    duration = duration_map[area.difficulty]
    if area.stage == "stabilize":
        duration = min(duration, 5)
    scene = area.recommended_scene
    title_map = {
        "emotion_regulation": f"{preferred_item}情绪温度计",
        "transition_flexibility": "视觉倒计时过渡练习",
        "communication": "需求表达二选一",
        "waiting_tolerance": "短等待成功练习",
        "task_initiation": "第一步就算开始",
        "bedtime_routine": "睡前一环节配合练习",
        "daily_living": "自理小步骤打卡",
        "social_interaction": f"{supporter}轮流互动 3 回合",
        "sensory_regulation": "感官前兆识别 + 降载",
        "simple_compliance": "一句一事指令练习",
    }
    goal_map = {
        "emotion_regulation": "今天先让孩子能指出状态，并接受一个降温动作。",
        "transition_flexibility": "今天先把一次切换做成看得见、做得到的三步。",
        "communication": "今天把需求表达从哭闹/僵住，转成一个明确表达入口。",
        "waiting_tolerance": "今天先练很短等待，重点是能等一下而不是等很久。",
        "task_initiation": "今天先练更容易开始，而不是做完整任务。",
        "bedtime_routine": "今天只练睡前一个最容易卡住的环节。",
        "daily_living": "今天只练一个自理步骤，先把成功感做出来。",
        "social_interaction": "今天只做短回合轮流和回应，不追求复杂互动。",
        "sensory_regulation": "今天先练发现前兆并用固定动作降刺激。",
        "simple_compliance": "今天先练一句一事，更容易听懂并开始做。",
    }
    materials_map = {
        "emotion_regulation": [preferred_item, "情绪卡", "安静角落提示"],
        "transition_flexibility": ["先后卡", "倒计时", preferred_item],
        "communication": [preferred_item, "二选一卡", "图片/手势提示"],
        "waiting_tolerance": ["倒计时", preferred_item, "等待提示卡"],
        "task_initiation": ["第一步卡", "计时器", preferred_item],
        "bedtime_routine": ["睡前流程卡", "视觉提示", "固定收尾物件"],
        "daily_living": ["步骤卡", "小贴纸", preferred_item],
        "social_interaction": [preferred_item, supporter, "轮流提示卡"],
        "sensory_regulation": ["耳罩/安静角落", "身体部位图", "固定降载物"],
        "simple_compliance": ["动作卡", preferred_item, "视觉提示"],
    }

    return {
        "task_key": f"{area_key}_{area.stage}",
        "title": title_map[area_key],
        "today_goal": goal_map[area_key],
        "training_scene": scene,
        "schedule_hint": area.recommended_time,
        "steps": detail["parent_steps"][:3],
        "parent_script": detail["script_examples"][0],
        "duration_minutes": duration,
        "difficulty": area.difficulty,
        "materials": materials_map[area_key],
        "fallback_plan": detail["fallback_options"][0],
        "coaching_tip": detail["training_principles"][0],
    }


def _attempt_llm_refine(candidate: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "task": "基于给定候选训练方案，输出更个体化但仍然低负担、可执行的 ASD 家庭训练 JSON。",
        "candidate": candidate,
        "constraints": {
            "top_domains": 3,
            "tasks_max": 3,
            "steps_max": 5,
            "scripts_max": 3,
            "fallbacks_max": 3,
        },
    }
    raw = LLMClient().generate_json(
        system_prompt="你是 ASD 家庭训练系统的结构化计划生成器。只输出合法 JSON，不要解释。",
        user_prompt=json.dumps(payload, ensure_ascii=False),
    )
    if isinstance(raw, dict):
        return raw
    raise LLMUnavailableError("Invalid LLM planner output")


def persist_training_cycle(
    db: Session,
    family: Family,
    assessment: AssessmentResult,
    coordination: TrainingCoordinationResult,
    extra_context: str = "",
    force_new: bool = False,
) -> TrainingPlanCycle:
    profile = family.child_profile
    if profile is None:
        raise ValueError("Family profile not found")

    context = profile.school_context or {}
    existing_states = {
        item.area_key: item
        for item in db.scalars(select(TrainingSkillState).where(TrainingSkillState.family_id == family.family_id)).all()
    }

    detail_by_area: dict[str, dict[str, Any]] = {}
    for index, area_key in enumerate(sorted(assessment.assessments, key=lambda key: assessment.assessments[key].priority_score, reverse=True), start=1):
        area = assessment.assessments[area_key]
        detail = _build_domain_plan(area_key=area_key, area=area, profile=profile, context=context)
        detail_by_area[area_key] = detail
        state = existing_states.get(area_key)
        if state is None:
            state = TrainingSkillState(family_id=family.family_id, area_key=area_key)
            db.add(state)
            existing_states[area_key] = state

        state.priority_score = area.priority_score
        state.priority_rank = index
        state.current_stage = area.stage
        state.current_difficulty = area.difficulty
        state.recommended_time = area.recommended_time
        state.recommended_scene = area.recommended_scene
        state.best_method = area.best_method
        state.reason_summary = area.reasons[0]
        state.risk_summary = area.current_status
        state.weekly_sessions_count = area.weekly_sessions_count
        state.success_count = area.success_count
        state.effectiveness_score = area.effectiveness_score
        state.last_assessed_at = utc_now()
        state.meta_json = detail

    today = date_type.today()
    cycle = db.scalar(
        select(TrainingPlanCycle)
        .where(
            TrainingPlanCycle.family_id == family.family_id,
            TrainingPlanCycle.cycle_date == today,
            TrainingPlanCycle.active.is_(True),
        )
        .order_by(desc(TrainingPlanCycle.created_at))
        .limit(1)
    )

    if cycle is None or force_new:
        active_cycles = db.scalars(
            select(TrainingPlanCycle).where(
                TrainingPlanCycle.family_id == family.family_id,
                TrainingPlanCycle.active.is_(True),
            )
        ).all()
        for item in active_cycles:
            item.active = False

        cycle = TrainingPlanCycle(
            family_id=family.family_id,
            cycle_date=today,
            active=True,
            load_level=coordination.effective_load_level,
            weekly_summary=assessment.summary_text,
            source_summary=assessment.source_summary,
            top_area_keys=assessment.top_area_keys,
            snapshot_json={},
        )
        db.add(cycle)
        db.flush()

    cycle.load_level = coordination.effective_load_level
    cycle.weekly_summary = assessment.summary_text
    cycle.source_summary = f"{assessment.source_summary}；{extra_context.strip()}" if extra_context.strip() else assessment.source_summary
    cycle.top_area_keys = assessment.top_area_keys

    existing_tasks = db.scalars(
        select(DailyTrainingTask)
        .where(DailyTrainingTask.cycle_id == cycle.id, DailyTrainingTask.task_date == today)
        .order_by(DailyTrainingTask.order_idx)
    ).all()
    if not existing_tasks or force_new:
        for task in existing_tasks:
            db.delete(task)
        db.flush()

        task_candidates = []
        for area_key in assessment.top_area_keys[: coordination.task_limit]:
            area = assessment.assessments[area_key]
            detail = detail_by_area[area_key]
            task_snapshot = _build_task_snapshot(area_key=area_key, area=area, detail=detail)
            if coordination.readiness_status == "lighter":
                task_snapshot.update(
                    {
                        "title": f"{task_snapshot['title']} · 低负担版",
                        "duration_minutes": min(int(task_snapshot["duration_minutes"]), 5),
                        "coaching_tip": f"今天先压低负担：{coordination.recommended_action}",
                        "why_today": coordination.readiness_reason,
                        "coordination_mode": "lighter",
                    }
                )
            else:
                task_snapshot.update(
                    {
                        "why_today": coordination.readiness_reason,
                        "coordination_mode": coordination.readiness_status,
                    }
                )
            task_candidates.append(
                {
                    "area_key": area_key,
                    "detail": detail,
                    "task": task_snapshot,
                }
            )

        llm_candidate = {
            "summary_text": assessment.summary_text,
            "top_area_keys": assessment.top_area_keys,
            "tasks": [item["task"] for item in task_candidates],
            "domain_plans": {item["area_key"]: item["detail"] for item in task_candidates},
        }
        try:
            refined = _attempt_llm_refine(llm_candidate)
            refined_tasks = refined.get("tasks")
            if isinstance(refined_tasks, list) and len(refined_tasks) == len(task_candidates):
                for index, payload in enumerate(refined_tasks):
                    if isinstance(payload, dict):
                        task_candidates[index]["task"].update(payload)
        except (LLMUnavailableError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

        for order_idx, item in enumerate(task_candidates, start=1):
            task_payload = item["task"]
            db.add(
                DailyTrainingTask(
                    family_id=family.family_id,
                    cycle_id=cycle.id,
                    task_date=today,
                    order_idx=order_idx,
                    area_key=item["area_key"],
                    title=str(task_payload["title"]),
                    status="pending",
                    reminder_status="none",
                    feedback_submitted=False,
                    task_json=task_payload,
                )
            )

    cycle.snapshot_json = {
        "child_summary": assessment.child_summary,
        "summary_text": assessment.summary_text,
        "load_level": coordination.effective_load_level,
        "top_area_keys": assessment.top_area_keys,
        "domain_plans": detail_by_area,
        "coordination": {
            "readiness_status": coordination.readiness_status,
            "readiness_reason": coordination.readiness_reason,
            "recommended_action": coordination.recommended_action,
            "signal": coordination.signal.model_dump(),
            "emotion": coordination.emotion.model_dump(),
            "used_memory_signals": coordination.used_memory_signals,
            "coordination_hint": coordination.coordination_hint,
        },
    }
    db.flush()
    return cycle
