from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_type, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ChildProfile, DailyCheckin, Family, IncidentLog, Review, TrainingTaskFeedback
from app.services.training_registry import SCENARIO_LABELS, all_domains, get_domain


@dataclass(slots=True)
class DomainAssessment:
    area_key: str
    priority_score: int
    reasons: list[str]
    related_challenges: list[str]
    current_status: str
    improvement_value: str
    stage: str
    difficulty: str
    recommended_time: str
    recommended_scene: str
    best_method: str
    weekly_sessions_count: int
    success_count: int
    effectiveness_score: int
    meta: dict[str, object]


@dataclass(slots=True)
class AssessmentResult:
    child_summary: str
    summary_text: str
    load_level: str
    top_area_keys: list[str]
    assessments: dict[str, DomainAssessment]
    source_summary: str


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _safe_int(value: float) -> int:
    return max(0, min(100, round(value)))


def _first(values: list[str], fallback: str) -> str:
    for value in values:
        if value:
            return value
    return fallback


def _contains_any(items: list[str], keywords: list[str]) -> bool:
    joined = " ".join(items)
    return any(keyword in joined for keyword in keywords)


def _scenario_text(key: str | None) -> str:
    return SCENARIO_LABELS.get(key or "", "日常关键场景")


def load_assessment_inputs(
    db: Session,
    family_id: int,
) -> tuple[list[DailyCheckin], list[IncidentLog], list[Review], list[TrainingTaskFeedback]]:
    today = date_type.today()
    checkins = db.scalars(
        select(DailyCheckin)
        .where(DailyCheckin.family_id == family_id, DailyCheckin.date >= today - timedelta(days=13))
        .order_by(desc(DailyCheckin.date))
    ).all()
    incidents = db.scalars(
        select(IncidentLog)
        .where(IncidentLog.family_id == family_id, IncidentLog.ts >= today - timedelta(days=30))
        .order_by(desc(IncidentLog.ts))
    ).all()
    reviews = db.scalars(
        select(Review)
        .where(Review.family_id == family_id, Review.created_at >= today - timedelta(days=30))
        .order_by(desc(Review.created_at))
    ).all()
    feedbacks = db.scalars(
        select(TrainingTaskFeedback)
        .where(TrainingTaskFeedback.family_id == family_id, TrainingTaskFeedback.date >= today - timedelta(days=13))
        .order_by(desc(TrainingTaskFeedback.date), desc(TrainingTaskFeedback.id))
    ).all()
    return checkins, incidents, reviews, feedbacks


def assess_training_needs(
    family: Family,
    profile: ChildProfile,
    checkins: list[DailyCheckin],
    incidents: list[IncidentLog],
    reviews: list[Review],
    feedbacks: list[TrainingTaskFeedback],
    extra_context: str = "",
) -> AssessmentResult:
    context = profile.school_context or {}
    child_name = str(context.get("child_name") or "").strip() or "孩子"
    child_age = context.get("child_age")
    age_text = f"{child_age} 岁" if isinstance(child_age, int) else f"{profile.age_band} 岁段"
    learning_needs = [str(item) for item in context.get("learning_needs", []) if isinstance(item, str)]
    behavior_patterns = [str(item) for item in context.get("behavior_patterns", []) if isinstance(item, str)]
    emotion_patterns = [str(item) for item in context.get("emotion_patterns", []) if isinstance(item, str)]
    supporters = [str(item) for item in context.get("available_supporters", []) if isinstance(item, str)]
    parent_schedule = [str(item) for item in context.get("parent_schedule", []) if isinstance(item, str)]
    supporter_availability = str(context.get("supporter_availability") or "").strip()
    school_notes = str(context.get("school_notes") or "").strip()
    top_scenario = profile.high_friction_scenarios[0] if profile.high_friction_scenarios else "transition"
    scenario_text = _scenario_text(top_scenario)

    scores: dict[str, int] = {item.area_key: 0 for item in all_domains()}
    reasons: dict[str, list[str]] = defaultdict(list)

    def bump(area_key: str, value: int, reason: str) -> None:
        scores[area_key] = min(100, scores[area_key] + value)
        if reason not in reasons[area_key]:
            reasons[area_key].append(reason)

    language_level = profile.language_level
    if language_level in {"none", "single_word"}:
        bump("communication", 34, f"当前沟通水平为 {language_level}，需求表达仍需要清晰脚手架。")
    elif language_level == "short_sentence":
        bump("communication", 18, "虽然已有短句表达，但在高压场景里仍需要更稳定的功能性沟通。")

    if _contains_any(learning_needs + [school_notes], ["表达", "沟通", "理解", "请求", "语言"]):
        bump("communication", 18, "档案里已记录沟通/理解相关困难。")
    if _contains_any(profile.triggers, ["等待", "排队"]):
        bump("waiting_tolerance", 18, "高频触发器里出现等待/排队，说明延迟满足是当前难点。")
    if _contains_any(behavior_patterns + learning_needs + [school_notes], ["作业", "启动", "开始困难", "拖延", "坐下"]):
        bump("task_initiation", 22, "家长记录里已经出现任务启动困难。")
    if "bedtime" in profile.high_friction_scenarios or _contains_any(profile.triggers + behavior_patterns, ["睡前", "洗澡", "刷牙", "上床"]):
        bump("bedtime_routine", 22, "睡前流程已是高摩擦场景，需要单独拆步训练。")
    if _contains_any(behavior_patterns + learning_needs + [school_notes], ["刷牙", "穿衣", "洗澡", "自理", "收拾"]):
        bump("daily_living", 20, "自理/流程执行已影响日常节奏。")
    if _contains_any(learning_needs + [school_notes], ["社交", "同伴", "轮流", "回应", "共同注意"]):
        bump("social_interaction", 18, "社交回应和轮流已经进入当前训练关注点。")
    if profile.sensory_flags:
        bump("sensory_regulation", min(24, len(profile.sensory_flags) * 8), "已记录感官敏感，需要优先练降载。")
    if _contains_any(profile.triggers + behavior_patterns, ["过渡", "变动", "切换", "关屏", "出门"]):
        bump("transition_flexibility", 24, "过渡和变化已是当前的高频触发点。")
    if _contains_any(behavior_patterns + learning_needs + [school_notes], ["听指令", "遵从", "配合", "指令"]):
        bump("simple_compliance", 16, "简单指令进入速度偏慢，影响日常协作。")
    if emotion_patterns or _contains_any(profile.triggers, ["焦虑", "崩溃", "情绪"]):
        bump("emotion_regulation", 18, "档案中存在明显情绪波动或升级线索。")

    avg_meltdown = _average([float(item.meltdown_count) for item in checkins])
    avg_transition = _average([float(item.transition_difficulty) for item in checkins])
    avg_parent_stress = _average([float(item.caregiver_stress) for item in checkins])
    heavy_sensory_days = sum(1 for item in checkins if item.sensory_overload_level in {"medium", "heavy"})
    unsupported_days = sum(1 for item in checkins if item.support_available == "none")
    bedtime_mentions = 0
    task_start_mentions = 0
    waiting_mentions = 0
    compliance_mentions = 0

    for checkin in checkins:
        details = checkin.details_json or {}
        activities = [str(item) for item in details.get("today_activities", []) if isinstance(item, str)]
        tasks = [str(item) for item in details.get("today_learning_tasks", []) if isinstance(item, str)]
        negative = [str(item) for item in details.get("negative_emotions", []) if isinstance(item, str)]
        discomforts = [str(item) for item in details.get("physical_discomforts", []) if isinstance(item, str)]
        text_pool = activities + tasks + negative + discomforts + checkin.env_changes
        if _contains_any(text_pool, ["睡前", "洗澡", "刷牙", "熄灯"]):
            bedtime_mentions += 1
        if _contains_any(text_pool, ["作业", "开始", "任务", "坐下"]):
            task_start_mentions += 1
        if _contains_any(text_pool, ["等待", "排队", "轮流"]):
            waiting_mentions += 1
        if _contains_any(text_pool, ["不听", "指令", "收玩具", "坐好"]):
            compliance_mentions += 1

    if avg_meltdown >= 2:
        bump("emotion_regulation", 24, f"近 14 天平均升级 {avg_meltdown:g} 次，情绪调节应放在前面。")
    elif avg_meltdown >= 1:
        bump("emotion_regulation", 14, f"近 14 天仍有持续情绪升级，平均 {avg_meltdown:g} 次。")
    if avg_transition >= 7:
        bump("transition_flexibility", 20, f"近 14 天过渡难度均值 {avg_transition:g}/10。")
    if heavy_sensory_days >= 3:
        bump("sensory_regulation", 16, f"近 14 天有 {heavy_sensory_days} 天出现中高感官负荷。")
    if bedtime_mentions >= 2:
        bump("bedtime_routine", 10, "最近签到里反复出现睡前流程困难。")
    if task_start_mentions >= 2:
        bump("task_initiation", 12, "最近签到里反复出现任务开始困难。")
    if waiting_mentions >= 2:
        bump("waiting_tolerance", 10, "最近签到里等待场景反复触发冲突。")
    if compliance_mentions >= 2:
        bump("simple_compliance", 10, "最近日常记录里多次出现简单指令难进入。")
    if unsupported_days >= 2:
        bump("daily_living", 8, "支持条件不足时，更需要能在家里稳定复用的小步骤。")

    if incidents:
        top_scenarios = [item.scenario for item in incidents[:8]]
        if top_scenarios.count("transition") >= 2:
            bump("transition_flexibility", 12, "近 30 天高摩擦事件多集中在过渡场景。")
        if top_scenarios.count("bedtime") >= 2:
            bump("bedtime_routine", 10, "近 30 天睡前相关事件频率较高。")
        if top_scenarios.count("homework") >= 2:
            bump("task_initiation", 10, "近 30 天学习/任务场景反复卡住。")
        if top_scenarios.count("outing") >= 2:
            bump("waiting_tolerance", 8, "外出/社交事件增加时，等待与规则切换更容易出问题。")

    if reviews:
        negative_reviews = sum(1 for item in reviews[:10] if item.outcome_score <= 0)
        if negative_reviews >= 3:
            bump("emotion_regulation", 8, "近期复盘里有多次‘未稳住’结果，普通训练要更保守。")

    feedback_by_area: dict[str, list[TrainingTaskFeedback]] = defaultdict(list)
    for item in feedbacks:
        feedback_by_area[item.area_key].append(item)

    for area_key, items in feedback_by_area.items():
        done_count = sum(1 for item in items if item.completion_status == "done")
        missed_count = sum(1 for item in items if item.completion_status == "missed")
        resistant_count = sum(1 for item in items if item.child_response in {"resistant", "overloaded"})
        helpful_count = sum(1 for item in items if item.helpfulness == "helpful")
        avg_effect = _average([float(item.effect_score) for item in items[:5]])
        if missed_count >= max(2, done_count + 1):
            bump(area_key, 10, "最近这块任务连续不容易完成，需要继续前置。")
        if resistant_count >= 2:
            bump(area_key, 8, "近期反馈显示孩子在这一能力训练上抗拒较高。")
        if helpful_count >= 2 and avg_effect >= 7:
            scores[area_key] = max(0, scores[area_key] - 4)
            reasons[area_key].append("最近这一块已有正向反馈，可以开始更稳地泛化。")

    time_capacity_low = _contains_any(parent_schedule, ["忙", "加班", "轮班", "接送紧张"]) and not supporters
    load_level = "standard"
    if avg_parent_stress >= 7 or heavy_sensory_days >= 4 or time_capacity_low:
        load_level = "light"
    elif feedbacks:
        load_level = "adaptive"

    ranked = sorted(scores, key=lambda key: (scores[key], key), reverse=True)
    top_area_keys = ranked[:3]

    preferred_scene = {
        "emotion_regulation": "情绪起波动前",
        "transition_flexibility": scenario_text,
        "communication": "孩子需要帮助时",
        "waiting_tolerance": "等待喜欢的东西前",
        "task_initiation": "坐下任务前",
        "bedtime_routine": "睡前固定流程",
        "daily_living": "洗澡/刷牙/穿衣等流程前",
        "social_interaction": "和熟悉照护者互动时",
        "sensory_regulation": "放学后或外出前",
        "simple_compliance": "收玩具或出门前",
    }
    recommended_time = {
        "emotion_regulation": "情绪刚升温时",
        "transition_flexibility": "切换前 5 分钟",
        "communication": "自然想要东西时",
        "waiting_tolerance": "等待前 1 分钟",
        "task_initiation": "任务开始前",
        "bedtime_routine": "晚饭后到熄灯前",
        "daily_living": "晨起或晚间固定时段",
        "social_interaction": "状态稳定的短时段",
        "sensory_regulation": "高刺激前或恢复期",
        "simple_compliance": "家长能靠近示范时",
    }

    assessments: dict[str, DomainAssessment] = {}
    for area_key in scores:
        items = feedback_by_area.get(area_key, [])
        weekly_sessions_count = sum(1 for item in items if item.date >= date_type.today() - timedelta(days=6))
        success_count = sum(1 for item in items if item.completion_status == "done")
        helpful_count = sum(1 for item in items if item.helpfulness == "helpful")
        effective_rate = _safe_int((helpful_count / max(len(items), 1)) * 100) if items else 0
        resistant_count = sum(1 for item in items if item.child_response in {"resistant", "overloaded"})
        if resistant_count >= 2 or scores[area_key] >= 72:
            stage = "stabilize"
        elif success_count >= 5 and effective_rate >= 80:
            stage = "maintain"
        elif success_count >= 3 and effective_rate >= 75:
            stage = "generalize"
        else:
            stage = "practice"

        if stage == "stabilize":
            difficulty = "starter"
        elif stage == "generalize":
            difficulty = "advance"
        elif stage == "maintain":
            difficulty = "advance"
        else:
            difficulty = "build"

        domain = get_domain(area_key)
        reason_list = reasons[area_key][:3] if reasons[area_key] else [f"当前先补 {domain.title}，更容易带动其它训练。"]
        current_status = reason_list[0]
        improvement_value = domain.importance
        best_method = domain.method_examples[0]
        if items:
            strongest = max(items[:5], key=lambda item: (item.effect_score, item.helpfulness == "helpful"))
            if strongest.task_title:
                best_method = strongest.task_title

        assessments[area_key] = DomainAssessment(
            area_key=area_key,
            priority_score=scores[area_key],
            reasons=reason_list,
            related_challenges=list(domain.related_challenges),
            current_status=current_status,
            improvement_value=improvement_value,
            stage=stage,
            difficulty=difficulty,
            recommended_time=recommended_time[area_key],
            recommended_scene=preferred_scene[area_key],
            best_method=best_method,
            weekly_sessions_count=weekly_sessions_count,
            success_count=success_count,
            effectiveness_score=effective_rate,
            meta={
                "principles": list(domain.principles),
                "suggested_scenarios": list(domain.suggested_scenarios),
                "cautions": list(domain.cautions),
                "method_examples": list(domain.method_examples),
                "fallback_options": list(domain.fallback_options),
                "importance": domain.importance,
                "summary": domain.summary,
            },
        )

    priority_text = "、".join(get_domain(key).title for key in top_area_keys)
    supporter_text = _first(supporters, "家长")
    source_bits = [
        f"最近 14 天签到 {len(checkins)} 次",
        f"高摩擦事件 {len(incidents)} 次",
        f"训练反馈 {len(feedbacks)} 次",
        f"当前支持者以 {supporter_text} 为主",
    ]
    if supporter_availability:
        source_bits.append(f"支持可用性：{supporter_availability}")
    if extra_context.strip():
        source_bits.append(f"家长补充：{extra_context.strip()}")

    child_summary = (
        f"{child_name}，{age_text}，当前以 {profile.language_level} 沟通为主；"
        f"高频触发器包括 {'、'.join(profile.triggers[:2]) if profile.triggers else '过渡和环境变化'}，"
        f"近两周平均崩溃 {avg_meltdown:g} 次、过渡难度 {avg_transition:g}/10。"
    )
    summary_text = (
        f"当前重点训练 {priority_text}。本轮采用{'低负荷' if load_level == 'light' else '动态' if load_level == 'adaptive' else '标准'}节奏，"
        f"优先把训练嵌进 {scenario_text} 这样的真实场景。"
    )

    return AssessmentResult(
        child_summary=child_summary,
        summary_text=summary_text,
        load_level=load_level,
        top_area_keys=top_area_keys,
        assessments=assessments,
        source_summary="；".join(source_bits),
    )
