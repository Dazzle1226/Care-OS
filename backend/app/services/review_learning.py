from __future__ import annotations

from collections.abc import Iterable

from app.models import IncidentLog, Review
from app.schemas.domain import ReplayResponse, ReplayStep

MANUAL_CARD_PREFIX = "manual:"

SCENARIO_LABELS = {
    "transition": "过渡",
    "bedtime": "睡前",
    "homework": "作业",
    "outing": "外出",
    "respite": "微喘息",
}


def normalize_review_card_ids(card_ids: Iterable[str], scenario: str | None) -> list[str]:
    cleaned: list[str] = []
    for raw in card_ids:
        item = raw.strip()
        if item and item not in cleaned:
            cleaned.append(item)
    if cleaned:
        return cleaned

    scenario_key = (scenario or "general").strip() or "general"
    return [f"{MANUAL_CARD_PREFIX}{scenario_key}"]


def is_learnable_card_id(card_id: str) -> bool:
    return not card_id.startswith(MANUAL_CARD_PREFIX)


def child_state_label(value: str) -> str:
    return {
        "settled": "更稳了",
        "partly_settled": "部分缓下来了",
        "still_escalating": "还在升级",
    }.get(value, "状态未知")


def caregiver_state_label(value: str) -> str:
    return {
        "calmer": "负荷下降",
        "same": "负荷差不多",
        "more_overloaded": "更累了",
    }.get(value, "负荷未知")


def recommendation_label(value: str) -> str:
    return {
        "continue": "继续",
        "pause": "暂停",
        "replace": "替换",
    }.get(value, "继续")


def outcome_score_label(score: int) -> str:
    if score >= 2:
        return "明显有效"
    if score >= 1:
        return "有帮助"
    if score == 0:
        return "部分有效"
    if score == -1:
        return "效果一般"
    return "更难执行"


def build_followup_action(
    recommendation: str,
    child_state_after: str,
    caregiver_state_after: str,
    followup_action: str = "",
) -> str:
    if followup_action.strip():
        return followup_action.strip()

    if recommendation == "continue":
        if child_state_after == "settled":
            return "保留这套做法，下次继续用同样开场和同样顺序。"
        return "保留核心步骤，下次把提示语再缩短一点。"

    if recommendation == "pause":
        if caregiver_state_after == "more_overloaded":
            return "先暂停这套做法，等家长和孩子状态更稳再试。"
        return "先暂停本策略，回到更低刺激、更少要求的版本。"

    return "下次换成更小一步或更低刺激的策略，不再硬推当前做法。"


def review_result_summary(review: Review) -> str:
    return (
        f"{outcome_score_label(review.outcome_score)}；孩子{child_state_label(review.child_state_after)}；"
        f"家长{caregiver_state_label(review.caregiver_state_after)}。"
    )


def replay_strategy_titles(review: Review, card_titles: dict[str, str]) -> list[str]:
    titles: list[str] = []
    response_action = review.response_action.strip()
    if response_action:
        titles.append(response_action)
    for card_id in review.card_ids:
        if is_learnable_card_id(card_id):
            title = card_titles.get(card_id, card_id)
        else:
            title = "手动记录（未绑定策略卡）"
        if title not in titles:
            titles.append(title)
    return titles or ["未绑定策略卡"]


def build_replay_response(
    review: Review,
    incident: IncidentLog,
    card_titles: dict[str, str],
) -> ReplayResponse:
    strategy_titles = replay_strategy_titles(review, card_titles)
    trigger_text = "、".join(incident.triggers) if incident.triggers else "未记录明确触发器"
    strategy_text = review.response_action.strip() or "、".join(strategy_titles[:2])
    next_improvement = build_followup_action(
        recommendation=review.recommendation,
        child_state_after=review.child_state_after,
        caregiver_state_after=review.caregiver_state_after,
        followup_action=review.followup_action,
    )

    return ReplayResponse(
        incident_id=incident.id,
        scenario=SCENARIO_LABELS.get(incident.scenario, incident.scenario),
        happened_at=review.created_at,
        recommendation=review.recommendation,
        strategy_titles=strategy_titles,
        timeline=[
            ReplayStep(label="触发器", value=trigger_text),
            ReplayStep(label="策略", value=strategy_text),
            ReplayStep(label="结果", value=review_result_summary(review)),
            ReplayStep(label="下次改进", value=next_improvement),
        ],
        next_improvement=next_improvement,
    )
