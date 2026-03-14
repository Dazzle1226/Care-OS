from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChildProfile, DailyCheckin, IncidentLog, ReportFeedback, Review, StrategyCard, WeeklyReport
from app.schemas.domain import (
    ActionSuggestion,
    MonthlyHistoryPoint,
    MonthlyReportResponse,
    MonthlyTrendItem,
    ReportFeedbackCreate,
    ReportFeedbackResponse,
    ReportFeedbackState,
    ReportFeedbackSummary,
    ReportMetricPoint,
    ReplayResponse,
    StrategyInsight,
    TaskEffectItem,
    TrendDeltaItem,
    WeeklyReportResponse,
)
from app.services.policy_learning import PolicyLearningService
from app.services.review_learning import (
    build_replay_response,
    is_learnable_card_id,
    recommendation_label,
)

SCENARIO_LABELS = {
    "transition": "过渡",
    "bedtime": "睡前",
    "homework": "作业",
    "outing": "外出",
}
DEFAULT_TRIGGERS = ["过渡", "等待", "噪音"]
DEFAULT_METHODS = [
    ("method:提前5分钟提醒", "提前5分钟提醒", "在高摩擦场景前先给孩子一个可预期的缓冲。"),
    ("method:给选择不下命令", "给选择不下命令", "把对抗感降下来，更容易换来合作。"),
    ("method:先降刺激再提要求", "先降刺激再提要求", "先处理环境负荷，再处理任务本身。"),
]


def normalize_week_start(target: date) -> date:
    return target - timedelta(days=target.isoweekday() - 1)


def normalize_month_start(target: date) -> date:
    return date(target.year, target.month, 1)


def next_month_start(target: date) -> date:
    if target.month == 12:
        return date(target.year + 1, 1, 1)
    return date(target.year, target.month + 1, 1)


def _start_of_day(target: date) -> datetime:
    return datetime.combine(target, time.min)


def _average(values: list[float]) -> float:
    return round(float(fmean(values)), 1) if values else 0.0


def _percentage(hits: int, total: int) -> int:
    return round((hits / total) * 100) if total else 0


def _scenario_label(value: str | None) -> str:
    if not value:
        return "本周任务"
    return SCENARIO_LABELS.get(value, value)


def _strategy_ranking_summary() -> str:
    return "排序先看平均效果，再看有效率、适配率、证据数和家庭级策略权重；只有低风险且样本少的策略，才会被保留在前排继续验证。"


def _applicability_label(fit_rate: int) -> str:
    if fit_rate >= 75:
        return "high"
    if fit_rate >= 45:
        return "medium"
    return "low"


def _load_profile(db: Session, family_id: int) -> ChildProfile | None:
    return db.scalar(select(ChildProfile).where(ChildProfile.family_id == family_id))


def _load_card_titles(db: Session, card_ids: set[str]) -> dict[str, str]:
    if not card_ids:
        return {}
    cards = db.scalars(select(StrategyCard).where(StrategyCard.card_id.in_(sorted(card_ids)))).all()
    return {card.card_id: card.title for card in cards}


def _load_feedback_rows(db: Session, family_id: int, period_type: str, period_start: date) -> list[ReportFeedback]:
    return db.scalars(
        select(ReportFeedback)
        .where(
            ReportFeedback.family_id == family_id,
            ReportFeedback.period_type == period_type,
            ReportFeedback.period_start == period_start,
        )
        .order_by(ReportFeedback.updated_at.desc(), ReportFeedback.created_at.desc())
    ).all()


def _build_feedback_summary(rows: list[ReportFeedback]) -> ReportFeedbackSummary:
    counter = Counter(row.feedback_value for row in rows)
    return ReportFeedbackSummary(
        effective_count=counter["effective"],
        not_effective_count=counter["not_effective"],
        continue_count=counter["continue"],
        adjust_count=counter["adjust"],
    )


def _build_feedback_states(rows: list[ReportFeedback]) -> list[ReportFeedbackState]:
    return [
        ReportFeedbackState(
            target_kind=row.target_kind,
            target_key=row.target_key,
            target_label=row.target_label,
            feedback=row.feedback_value,
        )
        for row in rows
    ]


def _trend_points(
    checkins: list[DailyCheckin],
    start_date: date,
    days: int,
    value_getter,
) -> list[ReportMetricPoint]:
    by_day = {checkin.date: checkin for checkin in checkins}
    points: list[ReportMetricPoint] = []
    for offset in range(days):
        target = start_date + timedelta(days=offset)
        checkin = by_day.get(target)
        value = float(value_getter(checkin)) if checkin else 0.0
        points.append(ReportMetricPoint(label=target.strftime("%m-%d"), value=round(value, 1)))
    return points


def _top_triggers(
    incidents: list[IncidentLog],
    checkins: list[DailyCheckin],
    profile: ChildProfile | None,
) -> list[str]:
    counter = Counter()
    for incident in incidents:
        counter.update(trigger for trigger in incident.triggers if trigger)
    for checkin in checkins:
        counter.update(change for change in checkin.env_changes if change)

    ordered = [item for item, _ in counter.most_common()]
    if profile:
        for trigger in profile.triggers:
            if trigger and trigger not in ordered:
                ordered.append(trigger)
    for fallback in DEFAULT_TRIGGERS:
        if fallback not in ordered:
            ordered.append(fallback)
    return ordered[:3]


def _highest_risk_scenario(
    incidents: list[IncidentLog],
    reviews: list[Review],
    incident_map: dict[int, IncidentLog],
    profile: ChildProfile | None,
) -> str:
    counter = Counter()
    for incident in incidents:
        counter.update([incident.scenario])
    for review in reviews:
        linked = incident_map.get(review.incident_id)
        if linked:
            counter.update([linked.scenario])

    if counter:
        return _scenario_label(counter.most_common(1)[0][0])
    if profile and profile.high_friction_scenarios:
        return _scenario_label(profile.high_friction_scenarios[0])
    return "过渡"


def _build_trigger_summary(
    top_triggers: list[str],
    checkins: list[DailyCheckin],
    incidents: list[IncidentLog],
) -> str:
    if not checkins and not incidents:
        return "本周数据较少，先连续记录几天签到和一次复盘，系统会更快识别触发模式。"

    pieces = [f"本周最常见的触发因素是 {'、'.join(top_triggers)}。"]
    avg_transition = _average([checkin.transition_difficulty for checkin in checkins])
    medium_or_heavy_days = sum(
        1 for checkin in checkins if checkin.sensory_overload_level in {"medium", "heavy"}
    )
    if avg_transition >= 7:
        pieces.append("高波动大多出现在过渡难度升高的时候。")
    if medium_or_heavy_days >= 2:
        pieces.append("感官负荷偏高的日子里，情绪更容易升级。")
    return " ".join(pieces)


def _build_child_emotion_summary(checkins: list[DailyCheckin]) -> str:
    if not checkins:
        return "本周签到不足，先用每日签到建立孩子情绪和冲突的基线。"

    avg_meltdowns = _average([float(checkin.meltdown_count) for checkin in checkins])
    avg_transition = _average([checkin.transition_difficulty for checkin in checkins])
    heavy_days = sum(1 for checkin in checkins if checkin.sensory_overload_level == "heavy")
    if avg_meltdowns >= 2 or avg_transition >= 7.5 or heavy_days >= 2:
        return "孩子本周情绪波动较大，过渡和感官负荷叠加时最容易进入升级区。"
    if avg_meltdowns >= 1 or avg_transition >= 6:
        return "孩子本周存在中等波动，提前预告和减少同时要求仍然是关键。"
    return "孩子本周整体较平稳，维持固定节奏比继续加新要求更有效。"


def _task_status(outcome_score: int) -> str:
    if outcome_score >= 1:
        return "done"
    if outcome_score == 0:
        return "partial"
    return "retry"


def _task_summary_text(outcome_score: int) -> str:
    if outcome_score >= 1:
        return "已执行且效果较好，可以继续保持。"
    if outcome_score == 0:
        return "部分执行，说明方向可用，但还需要再微调。"
    return "执行阻力较大，建议缩小目标或换一个切入点。"


def _build_task_effects(
    reviews: list[Review],
    incident_map: dict[int, IncidentLog],
    card_titles: dict[str, str],
) -> tuple[list[TaskEffectItem], list[TaskEffectItem], list[TaskEffectItem], int, str]:
    completed: list[TaskEffectItem] = []
    partial: list[TaskEffectItem] = []
    retry: list[TaskEffectItem] = []

    for review in reviews:
        incident = incident_map.get(review.incident_id)
        scenario_label = _scenario_label(incident.scenario if incident else None)
        visible_card_ids = [card_id for card_id in review.card_ids if is_learnable_card_id(card_id)]
        card_label = " / ".join(card_titles.get(card_id, card_id) for card_id in visible_card_ids[:2]).strip()
        title = (review.followup_action or "").strip()
        if not title:
            title = f"{scenario_label} · {card_label}" if card_label else f"{scenario_label}复盘"

        item = TaskEffectItem(
            title=title[:72],
            summary=_task_summary_text(review.outcome_score),
            status=_task_status(review.outcome_score),
            outcome_score=review.outcome_score,
        )

        if item.status == "done":
            completed.append(item)
        elif item.status == "partial":
            partial.append(item)
        else:
            retry.append(item)

    total = len(reviews)
    if total == 0:
        return completed, partial, retry, 0, "本周还没有复盘记录，先补一条最卡场景的复盘，系统才能判断任务执行效果。"

    completion_score = round(((len(completed) + len(partial) * 0.5) / total) * 100)
    summary = (
        f"本周记录 {total} 次任务/策略复盘，完成度评分 {completion_score}/100；"
        f"{len(completed)} 项执行稳定，{len(partial)} 项部分完成，{len(retry)} 项需要重试。"
    )
    return completed[:3], partial[:3], retry[:3], completion_score, summary


def _fallback_strategies(profile: ChildProfile | None) -> list[StrategyInsight]:
    if profile and profile.soothing_methods:
        return [
            StrategyInsight(
                target_key=f"method:{method}",
                title=method,
                summary="当前缺少足够复盘数据，先沿用家长已知有效的方法继续建立证据。",
                evidence_count=0,
                avg_outcome=1.0,
                success_rate=0,
                fit_rate=0,
                applicability="medium",
                recommendation="continue",
                why_ranked=["当前缺少复盘证据。", "先沿用家庭已知较稳的方法建立基线。"],
            )
            for method in profile.soothing_methods[:3]
        ]

    return [
        StrategyInsight(
            target_key=target_key,
            title=title,
            summary=summary,
            evidence_count=0,
            avg_outcome=1.0,
            success_rate=0,
            fit_rate=0,
            applicability="medium",
            recommendation="continue",
            why_ranked=["当前缺少复盘证据。", "先从低风险、低成本的方法开始积累家庭数据。"],
        )
        for target_key, title, summary in DEFAULT_METHODS
    ]


def _build_strategy_insights(
    db: Session,
    family_id: int,
    reviews: list[Review],
    incident_map: dict[int, IncidentLog],
    card_titles: dict[str, str],
    profile: ChildProfile | None,
) -> list[StrategyInsight]:
    policy_weights = PolicyLearningService().get_effective_weight_map(
        db=db,
        family_id=family_id,
        target_kind="card",
        profile=profile,
    )
    bucket: dict[str, list[Review]] = defaultdict(list)
    for review in reviews:
        for card_id in review.card_ids:
            if not is_learnable_card_id(card_id):
                continue
            bucket[card_id].append(review)

    if not bucket:
        return _fallback_strategies(profile)

    ranked_rows: list[tuple[float, StrategyInsight]] = []
    for card_id, rows in bucket.items():
        ordered_rows = sorted(rows, key=lambda item: item.created_at, reverse=True)
        scores = [review.outcome_score for review in ordered_rows]
        avg_outcome = _average([float(score) for score in scores])
        total = len(ordered_rows)
        positive_hits = sum(review.outcome_score >= 1 for review in ordered_rows)
        fit_hits = sum(
            review.child_state_after != "still_escalating" and review.caregiver_state_after != "more_overloaded"
            for review in ordered_rows
        )
        continue_hits = sum(review.recommendation == "continue" for review in ordered_rows)
        success_rate = _percentage(positive_hits, total)
        fit_rate = _percentage(fit_hits, total)
        continue_rate = _percentage(continue_hits, total)
        recent_negative_hits = sum(review.outcome_score <= 0 for review in ordered_rows[:2])

        low_risk_probe = False
        if total == 1 and ordered_rows[0].outcome_score >= 1:
            incident = incident_map.get(ordered_rows[0].incident_id)
            low_risk_probe = incident is None or (incident.intensity != "heavy" and not incident.high_risk_flag)

        recommendation = "continue"
        if total >= 2 and (avg_outcome <= -0.3 or success_rate < 34 or fit_rate < 40):
            recommendation = "replace"
        elif total >= 2 and (continue_rate < 50 or recent_negative_hits >= 1):
            recommendation = "pause"

        if recommendation == "continue":
            summary = f"本周期平均效果 {avg_outcome:.1f}/2，有效率 {success_rate}% ，适合继续放在前排。"
        elif recommendation == "pause":
            summary = "这条策略方向可能还对，但近期稳定性不足，建议先暂停加码。"
        else:
            summary = "这条策略已有多次不稳证据，建议换成更低刺激或更容易起步的做法。"

        why_ranked = [
            f"有效率 {success_rate}%（{positive_hits}/{total}）",
            f"适配率 {fit_rate}%（孩子未继续升级且家长负荷未上升）",
        ]
        if low_risk_probe:
            why_ranked.append("当前样本少，仅在低风险场景保留前排验证。")
        else:
            why_ranked.append(f"已累计 {total} 次家庭内证据，建议{recommendation_label(recommendation)}。")
        policy_weight = policy_weights.get(card_id, 0.0)
        if policy_weight > 0.15:
            why_ranked.append("家庭级持续学习对这类策略给出了正向加权。")
        elif policy_weight < -0.15:
            why_ranked.append("家庭级持续学习对这类策略给出了负向惩罚。")

        insight = StrategyInsight(
            target_key=f"card:{card_id}",
            title=card_titles.get(card_id, card_id),
            summary=summary,
            evidence_count=total,
            avg_outcome=avg_outcome,
            success_rate=success_rate,
            fit_rate=fit_rate,
            applicability=_applicability_label(fit_rate),
            recommendation=recommendation,
            why_ranked=why_ranked[:3],
        )
        ranking_score = (
            avg_outcome * 30
            + success_rate * 0.35
            + fit_rate * 0.2
            + continue_rate * 0.12
            + min(total, 4) * 3
            + policy_weight * 12
            - recent_negative_hits * 5
        )
        ranked_rows.append((ranking_score, insight))

    ranked_rows.sort(key=lambda item: (item[0], item[1].evidence_count, item[1].avg_outcome), reverse=True)
    return [item[1] for item in ranked_rows[:3]] or _fallback_strategies(profile)


def _build_weekly_actions(
    top_triggers: list[str],
    checkins: list[DailyCheckin],
    highest_risk_scenario: str,
    task_completion_score: int,
    retry_tasks: list[TaskEffectItem],
) -> list[ActionSuggestion]:
    avg_transition = _average([checkin.transition_difficulty for checkin in checkins])
    avg_stress = _average([checkin.caregiver_stress for checkin in checkins])
    avg_sleep = _average([checkin.caregiver_sleep_hours for checkin in checkins])
    sensory_heavy_days = sum(1 for checkin in checkins if checkin.sensory_overload_level in {"medium", "heavy"})

    actions: list[ActionSuggestion] = []
    if "过渡" in top_triggers or highest_risk_scenario == "过渡" or avg_transition >= 7:
        actions.append(
            ActionSuggestion(
                target_key="action:transition_buffer",
                title="把过渡提醒固定到提前 5 分钟",
                summary="下周只练一个高频过渡场景，例如出门前或睡前，保持同一句提醒和同一个顺序。",
                rationale="本周过渡仍是最高频摩擦点，先降低不确定性最划算。",
                recommendation="continue",
            )
        )
    if avg_stress >= 7 or avg_sleep <= 5:
        actions.append(
            ActionSuggestion(
                target_key="action:caregiver_reset",
                title="先为家长留出固定的 15 分钟喘息窗口",
                summary="下周至少安排 1 次可交接或免任务时间，不把所有恢复都压到晚上。",
                rationale="家长压力和恢复度都偏高，先保护照护者稳定度，后续执行才会更稳。",
                recommendation="continue",
            )
        )
    if sensory_heavy_days >= 2 or "噪音" in top_triggers:
        actions.append(
            ActionSuggestion(
                target_key="action:sensory_buffer",
                title="先降刺激，再提要求",
                summary="饭点、回家后和作业前先处理噪音、灯光和同时指令，再进入任务。",
                rationale="感官负荷升高时更容易出现情绪升级，环境干预比口头要求更有效。",
                recommendation="continue",
            )
        )
    if task_completion_score < 60 or retry_tasks:
        actions.append(
            ActionSuggestion(
                target_key="action:task_slice",
                title="把高摩擦任务拆成一个最小完成标准",
                summary="只保留一个本周必须完成的最小动作，例如先坐下 3 分钟或先完成 1 题。",
                rationale="本周任务执行稳定度还不够，目标过大时更容易反复失败。",
                recommendation="replace",
            )
        )

    if not actions:
        actions.append(
            ActionSuggestion(
                target_key="action:keep_baseline",
                title="延续本周最稳定的一条节奏",
                summary="不要同时新增多个要求，先把本周最顺的一条流程继续保持 7 天。",
                rationale="当前整体状态相对平稳，保持比继续加码更容易积累正反馈。",
                recommendation="continue",
            )
        )

    return actions[:3]


def _build_caregiver_summary(checkins: list[DailyCheckin]) -> tuple[str, float, float, float]:
    if not checkins:
        return "本周还缺少足够签到数据，先连续签到几天建立家长压力与疲劳基线。", 0.0, 0.0, 0.0

    stress_values = [checkin.caregiver_stress for checkin in checkins]
    sleep_values = [checkin.caregiver_sleep_hours for checkin in checkins]
    avg_stress = _average(stress_values)
    peak_stress = round(max(stress_values), 1)
    avg_sleep = _average(sleep_values)

    if avg_sleep <= 4:
        fatigue = "高疲劳"
    elif avg_sleep <= 6:
        fatigue = "中等疲劳"
    else:
        fatigue = "恢复尚可"

    if peak_stress - min(stress_values) >= 3:
        emotion_state = "情绪波动较大"
    elif avg_stress >= 7:
        emotion_state = "持续紧绷"
    elif avg_stress >= 5:
        emotion_state = "有负荷但仍可承受"
    else:
        emotion_state = "相对稳定"

    summary = (
        f"家长本周平均压力 {avg_stress:.1f}/10，峰值 {peak_stress:.1f}/10，"
        f"睡眠恢复 {avg_sleep:.1f}/10，整体处于{fatigue}、{emotion_state}状态。"
    )
    return summary, avg_stress, peak_stress, avg_sleep


def _build_weekly_wow_items(
    current_checkins: list[DailyCheckin],
    previous_checkins: list[DailyCheckin],
    current_reviews: list[Review],
    previous_reviews: list[Review],
) -> list[TrendDeltaItem]:
    current_stress = _average([checkin.caregiver_stress for checkin in current_checkins])
    previous_stress = _average([checkin.caregiver_stress for checkin in previous_checkins])
    current_meltdowns = round(sum(checkin.meltdown_count for checkin in current_checkins) / max(len(current_checkins), 1), 1)
    previous_meltdowns = round(
        sum(checkin.meltdown_count for checkin in previous_checkins) / max(len(previous_checkins), 1), 1
    )
    current_completion = _completion_rate(current_reviews)
    previous_completion = _completion_rate(previous_reviews)

    return [
        TrendDeltaItem(
            title="家长压力",
            summary=_stress_summary(current_stress, previous_stress),
            current_value=current_stress,
            previous_value=previous_stress,
            direction=_direction(current_stress, previous_stress, lower_is_better=True),
            unit="/10",
        ),
        TrendDeltaItem(
            title="情绪升级均值",
            summary=(
                "还没有连续两周数据，先保持签到。"
                if not previous_checkins
                else f"日均升级次数从 {previous_meltdowns:.1f} 变为 {current_meltdowns:.1f}。"
            ),
            current_value=current_meltdowns,
            previous_value=previous_meltdowns,
            direction=_direction(current_meltdowns, previous_meltdowns, lower_is_better=True),
            unit="次/天",
        ),
        TrendDeltaItem(
            title="策略落地度",
            summary=_task_completion_summary(current_completion, previous_completion, len(current_reviews)),
            current_value=float(current_completion),
            previous_value=float(previous_completion),
            direction=_direction(float(current_completion), float(previous_completion), lower_is_better=False),
            unit="/100",
        ),
    ]


def _build_replay_items(
    reviews: list[Review],
    incident_map: dict[int, IncidentLog],
    card_titles: dict[str, str],
) -> list[ReplayResponse]:
    replay_items: list[ReplayResponse] = []
    for review in sorted(reviews, key=lambda item: item.created_at, reverse=True):
        incident = incident_map.get(review.incident_id)
        if incident is None:
            continue
        replay_items.append(build_replay_response(review=review, incident=incident, card_titles=card_titles))
        if len(replay_items) >= 3:
            break
    return replay_items


def _query_period_data(
    db: Session,
    family_id: int,
    start_date: date,
    end_date: date,
) -> tuple[list[DailyCheckin], list[IncidentLog], list[Review], dict[int, IncidentLog]]:
    start_ts = _start_of_day(start_date)
    end_ts = _start_of_day(end_date)

    checkins = db.scalars(
        select(DailyCheckin)
        .where(
            DailyCheckin.family_id == family_id,
            DailyCheckin.date >= start_date,
            DailyCheckin.date < end_date,
        )
        .order_by(DailyCheckin.date.asc())
    ).all()
    incidents = db.scalars(
        select(IncidentLog)
        .where(
            IncidentLog.family_id == family_id,
            IncidentLog.ts >= start_ts,
            IncidentLog.ts < end_ts,
        )
        .order_by(IncidentLog.ts.desc())
    ).all()
    reviews = db.scalars(
        select(Review)
        .where(
            Review.family_id == family_id,
            Review.created_at >= start_ts,
            Review.created_at < end_ts,
        )
        .order_by(Review.created_at.desc())
    ).all()

    incident_map = {incident.id: incident for incident in incidents}
    missing_ids = sorted({review.incident_id for review in reviews if review.incident_id not in incident_map})
    if missing_ids:
        linked_incidents = db.scalars(select(IncidentLog).where(IncidentLog.id.in_(missing_ids))).all()
        incident_map.update({incident.id: incident for incident in linked_incidents})

    return checkins, incidents, reviews, incident_map


def compute_weekly_report(db: Session, family_id: int, week_start: date) -> WeeklyReportResponse:
    normalized_start = normalize_week_start(week_start)
    week_end = normalized_start + timedelta(days=7)
    previous_start = normalized_start - timedelta(days=7)

    profile = _load_profile(db, family_id)
    checkins, incidents, reviews, incident_map = _query_period_data(db, family_id, normalized_start, week_end)
    previous_checkins, _, previous_reviews, _ = _query_period_data(db, family_id, previous_start, normalized_start)
    feedback_rows = _load_feedback_rows(db, family_id, "weekly", normalized_start)

    card_ids = {
        card_id
        for review in reviews
        for card_id in review.card_ids
        if is_learnable_card_id(card_id)
    }
    card_titles = _load_card_titles(db, card_ids)

    top_triggers = _top_triggers(incidents, checkins, profile)
    trigger_summary = _build_trigger_summary(top_triggers, checkins, incidents)
    child_emotion_summary = _build_child_emotion_summary(checkins)
    highest_risk_scenario = _highest_risk_scenario(incidents, reviews, incident_map, profile)
    completed_tasks, partial_tasks, retry_tasks, task_completion_score, task_summary = _build_task_effects(
        reviews,
        incident_map,
        card_titles,
    )
    caregiver_summary, avg_stress, peak_stress, avg_sleep = _build_caregiver_summary(checkins)
    strategy_top3 = _build_strategy_insights(db, family_id, reviews, incident_map, card_titles, profile)
    replay_items = _build_replay_items(reviews, incident_map, card_titles)
    next_actions = _build_weekly_actions(
        top_triggers=top_triggers,
        checkins=checkins,
        highest_risk_scenario=highest_risk_scenario,
        task_completion_score=task_completion_score,
        retry_tasks=retry_tasks,
    )

    row = db.scalar(
        select(WeeklyReport).where(
            WeeklyReport.family_id == family_id,
            WeeklyReport.week_start == normalized_start,
        )
    )
    if row is None:
        row = WeeklyReport(family_id=family_id, week_start=normalized_start)
        db.add(row)
        db.flush()

    report = WeeklyReportResponse(
        family_id=family_id,
        week_start=normalized_start,
        week_end=week_end - timedelta(days=1),
        trigger_top3=top_triggers,
        trigger_summary=trigger_summary,
        child_emotion_summary=child_emotion_summary,
        highest_risk_scenario=highest_risk_scenario,
        stress_trend=_trend_points(checkins, normalized_start, 7, lambda item: item.caregiver_stress if item else 0),
        meltdown_trend=_trend_points(checkins, normalized_start, 7, lambda item: item.meltdown_count if item else 0),
        week_over_week=_build_weekly_wow_items(checkins, previous_checkins, reviews, previous_reviews),
        task_completion_score=task_completion_score,
        task_summary=task_summary,
        completed_tasks=completed_tasks,
        partial_tasks=partial_tasks,
        retry_tasks=retry_tasks,
        caregiver_summary=caregiver_summary,
        caregiver_stress_avg=avg_stress,
        caregiver_stress_peak=peak_stress,
        caregiver_sleep_avg=avg_sleep,
        strategy_ranking_summary=_strategy_ranking_summary(),
        strategy_top3=strategy_top3,
        replay_items=replay_items,
        next_actions=next_actions,
        one_thing_next_week=next_actions[0].title,
        feedback_summary=_build_feedback_summary(feedback_rows),
        feedback_states=_build_feedback_states(feedback_rows),
        export_count=row.export_count,
    )

    row.summary_json = report.model_dump(mode="json")
    return report


def _completion_rate(reviews: list[Review]) -> int:
    if not reviews:
        return 0
    done = sum(review.outcome_score >= 1 for review in reviews)
    partial = sum(review.outcome_score == 0 for review in reviews)
    return round(((done + partial * 0.5) / len(reviews)) * 100)


def _direction(current: float, previous: float, lower_is_better: bool) -> str:
    if abs(current - previous) < 0.1:
        return "flat"
    improved = current < previous if lower_is_better else current > previous
    return "down" if improved else "up"


def _stress_summary(current: float, previous: float) -> str:
    if previous == 0 and current == 0:
        return "过去两个月都还没有形成足够的压力数据。"
    if previous == 0:
        return f"本月家长平均压力为 {current:.1f}/10，已建立第一版长期基线。"
    if current < previous:
        return f"家长平均压力从 {previous:.1f} 降到 {current:.1f}，负荷在回落。"
    if current > previous:
        return f"家长平均压力从 {previous:.1f} 升到 {current:.1f}，需要先保护照护者恢复。"
    return f"家长平均压力维持在 {current:.1f}/10，整体变化不大。"


def _conflict_summary(current: int, previous: int) -> str:
    if previous == 0 and current == 0:
        return "两个月内都没有记录到明确冲突事件。"
    if previous == 0:
        return f"本月记录到 {current} 次冲突/高摩擦事件，后续可以拿来作为比较基线。"
    change_pct = round(((current - previous) / previous) * 100)
    if current < previous:
        return f"冲突频次从 {previous} 次降到 {current} 次，下降 {abs(change_pct)}%。"
    if current > previous:
        return f"冲突频次从 {previous} 次升到 {current} 次，增加 {change_pct}%。"
    return f"冲突频次维持在 {current} 次，暂时没有明显变化。"


def _task_completion_summary(current: int, previous: int, review_count: int) -> str:
    if review_count == 0:
        return "本月还缺少足够复盘记录，先保证每周至少补 1 次复盘，才能看到长期任务趋势。"
    if previous == 0:
        return f"本月任务执行稳定度为 {current}/100，已经有了长期追踪的起点。"
    if current > previous:
        return f"任务执行稳定度从 {previous}/100 提升到 {current}/100，说明策略更容易落地。"
    if current < previous:
        return f"任务执行稳定度从 {previous}/100 降到 {current}/100，建议先缩小目标再继续。"
    return f"任务执行稳定度维持在 {current}/100，说明当前策略大体稳定。"


def _build_trend_items(
    current_checkins: list[DailyCheckin],
    previous_checkins: list[DailyCheckin],
    current_incidents: list[IncidentLog],
    previous_incidents: list[IncidentLog],
    current_reviews: list[Review],
    previous_reviews: list[Review],
) -> list[MonthlyTrendItem]:
    current_stress = _average([checkin.caregiver_stress for checkin in current_checkins])
    previous_stress = _average([checkin.caregiver_stress for checkin in previous_checkins])
    current_sleep = _average([checkin.caregiver_sleep_hours for checkin in current_checkins])
    previous_sleep = _average([checkin.caregiver_sleep_hours for checkin in previous_checkins])
    current_completion = _completion_rate(current_reviews)
    previous_completion = _completion_rate(previous_reviews)

    return [
        MonthlyTrendItem(
            title="家长压力",
            summary=_stress_summary(current_stress, previous_stress),
            current_value=current_stress,
            previous_value=previous_stress,
            direction=_direction(current_stress, previous_stress, lower_is_better=True),
            unit="/10",
        ),
        MonthlyTrendItem(
            title="冲突频次",
            summary=_conflict_summary(len(current_incidents), len(previous_incidents)),
            current_value=float(len(current_incidents)),
            previous_value=float(len(previous_incidents)),
            direction=_direction(float(len(current_incidents)), float(len(previous_incidents)), lower_is_better=True),
            unit="次",
        ),
        MonthlyTrendItem(
            title="任务完成度",
            summary=_task_completion_summary(current_completion, previous_completion, len(current_reviews)),
            current_value=float(current_completion),
            previous_value=float(previous_completion),
            direction=_direction(float(current_completion), float(previous_completion), lower_is_better=False),
            unit="/100",
        ),
        MonthlyTrendItem(
            title="家长恢复度",
            summary=(
                f"睡眠恢复从 {previous_sleep:.1f} 提升到 {current_sleep:.1f}。"
                if current_sleep > previous_sleep
                else f"睡眠恢复从 {previous_sleep:.1f} 降到 {current_sleep:.1f}。"
                if current_sleep < previous_sleep
                else f"睡眠恢复维持在 {current_sleep:.1f}/10。"
            ),
            current_value=current_sleep,
            previous_value=previous_sleep,
            direction=_direction(current_sleep, previous_sleep, lower_is_better=False),
            unit="/10",
        ),
    ]


def _build_monthly_history(
    db: Session,
    family_id: int,
    month_start: date,
) -> list[MonthlyHistoryPoint]:
    history: list[MonthlyHistoryPoint] = []
    cursor = normalize_month_start(month_start)
    for _ in range(2):
        previous_month = cursor.month - 1
        previous_year = cursor.year
        if previous_month == 0:
            previous_month = 12
            previous_year -= 1
        cursor = date(previous_year, previous_month, 1)

    for _ in range(3):
        month_end = next_month_start(cursor)
        checkins, incidents, reviews, _ = _query_period_data(db, family_id, cursor, month_end)
        history.append(
            MonthlyHistoryPoint(
                label=f"{cursor.month}月",
                avg_stress=_average([checkin.caregiver_stress for checkin in checkins]),
                conflict_count=len(incidents),
                task_completion_rate=_completion_rate(reviews),
            )
        )
        cursor = month_end

    return history


def _build_monthly_actions(
    top_triggers: list[str],
    current_checkins: list[DailyCheckin],
    current_incidents: list[IncidentLog],
    current_reviews: list[Review],
) -> list[ActionSuggestion]:
    highest_scenario = _scenario_label(current_incidents[0].scenario) if current_incidents else "过渡"
    completion_rate = _completion_rate(current_reviews)
    retry_like = [review for review in current_reviews if review.outcome_score <= 0]
    return _build_weekly_actions(
        top_triggers=top_triggers,
        checkins=current_checkins,
        highest_risk_scenario=highest_scenario,
        task_completion_score=completion_rate,
        retry_tasks=[
            TaskEffectItem(
                title=str(index),
                summary="",
                status="retry",
                outcome_score=review.outcome_score,
            )
            for index, review in enumerate(retry_like, start=1)
        ],
    )


def compute_monthly_report(db: Session, family_id: int, month_start: date) -> MonthlyReportResponse:
    normalized_start = normalize_month_start(month_start)
    month_end = next_month_start(normalized_start)
    previous_start = normalize_month_start(normalized_start - timedelta(days=1))

    profile = _load_profile(db, family_id)
    current_checkins, current_incidents, current_reviews, current_incident_map = _query_period_data(
        db, family_id, normalized_start, month_end
    )
    previous_checkins, previous_incidents, previous_reviews, _ = _query_period_data(db, family_id, previous_start, normalized_start)
    feedback_rows = _load_feedback_rows(db, family_id, "monthly", normalized_start)

    card_ids = {
        card_id
        for review in current_reviews
        for card_id in review.card_ids
        if is_learnable_card_id(card_id)
    }
    card_titles = _load_card_titles(db, card_ids)
    top_triggers = _top_triggers(current_incidents, current_checkins, profile)

    current_stress = _average([checkin.caregiver_stress for checkin in current_checkins])
    previous_stress = _average([checkin.caregiver_stress for checkin in previous_checkins])
    overview_summary = (
        f"过去一个月，家长平均压力从 {previous_stress:.1f} 调整到 {current_stress:.1f}，"
        f"冲突记录 {len(previous_incidents)} 次 -> {len(current_incidents)} 次。"
        if previous_checkins or previous_incidents or previous_reviews
        else f"本月已累计 {len(current_checkins)} 次签到、{len(current_reviews)} 次复盘，正在建立第一版长期跟踪基线。"
    )

    completion_current = _completion_rate(current_reviews)
    completion_previous = _completion_rate(previous_reviews)

    return MonthlyReportResponse(
        family_id=family_id,
        month_start=normalized_start,
        month_end=month_end - timedelta(days=1),
        overview_summary=overview_summary,
        stress_change_summary=_stress_summary(current_stress, previous_stress),
        conflict_change_summary=_conflict_summary(len(current_incidents), len(previous_incidents)),
        task_completion_summary=_task_completion_summary(completion_current, completion_previous, len(current_reviews)),
        long_term_trends=_build_trend_items(
            current_checkins,
            previous_checkins,
            current_incidents,
            previous_incidents,
            current_reviews,
            previous_reviews,
        ),
        strategy_ranking_summary=_strategy_ranking_summary(),
        successful_methods=_build_strategy_insights(db, family_id, current_reviews, current_incident_map, card_titles, profile),
        next_month_plan=_build_monthly_actions(top_triggers, current_checkins, current_incidents, current_reviews),
        history=_build_monthly_history(db, family_id, normalized_start),
        feedback_summary=_build_feedback_summary(feedback_rows),
        feedback_states=_build_feedback_states(feedback_rows),
    )


def save_report_feedback(db: Session, payload: ReportFeedbackCreate) -> ReportFeedbackResponse:
    period_start = normalize_week_start(payload.period_start) if payload.period_type == "weekly" else normalize_month_start(payload.period_start)
    row = db.scalar(
        select(ReportFeedback).where(
            ReportFeedback.family_id == payload.family_id,
            ReportFeedback.period_type == payload.period_type,
            ReportFeedback.period_start == period_start,
            ReportFeedback.target_kind == payload.target_kind,
            ReportFeedback.target_key == payload.target_key,
        )
    )

    if row is None:
        row = ReportFeedback(
            family_id=payload.family_id,
            period_type=payload.period_type,
            period_start=period_start,
            target_kind=payload.target_kind,
            target_key=payload.target_key,
            target_label=payload.target_label,
            feedback_value=payload.feedback,
            note=payload.note,
        )
        db.add(row)
        db.flush()
    else:
        row.target_label = payload.target_label
        row.feedback_value = payload.feedback
        row.note = payload.note
        db.flush()

    PolicyLearningService().record_report_feedback(
        db=db,
        family_id=payload.family_id,
        target_kind=payload.target_kind,
        target_key=payload.target_key,
        feedback=payload.feedback,
    )
    rows = _load_feedback_rows(db, payload.family_id, payload.period_type, period_start)
    return ReportFeedbackResponse(
        feedback_id=row.id,
        family_id=payload.family_id,
        period_type=payload.period_type,
        period_start=period_start,
        target_kind=payload.target_kind,
        target_key=payload.target_key,
        feedback=payload.feedback,
        summary=_build_feedback_summary(rows),
    )
