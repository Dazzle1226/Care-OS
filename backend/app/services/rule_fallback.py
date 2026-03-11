from __future__ import annotations

from collections.abc import Iterable

from app.models import StrategyCard
from app.schemas.domain import (
    Plan48hResponse,
    PlanActionItem,
    PlanMessage,
    RespiteSlot,
    SafetyBlockResponse,
    ScriptResponse,
    TodayFocusResponse,
    TodayReminderItem,
)


def _fallback_action_from_card(card: StrategyCard, idx: int) -> PlanActionItem:
    step = card.steps_json[min(idx, len(card.steps_json) - 1)] if card.steps_json else "先降刺激，再给简单选择。"
    script = card.scripts_json.get("parent", "我们先做一个小步骤，我会陪你。")
    donts = card.donts_json if len(card.donts_json) >= 2 else ["不要催促", "不要提高音量"]
    escalate = card.escalate_json if card.escalate_json else ["出现持续失控超过10分钟", "有伤害风险"]
    return PlanActionItem(card_id=card.card_id, step=step, script=script, donts=donts[:3], escalate_when=escalate[:3])


def build_fallback_plan(risk_level: str, scenarios: list[str], cards: Iterable[StrategyCard], support_hint: str) -> Plan48hResponse:
    chosen_cards = list(cards)[:3]
    if not chosen_cards:
        raise ValueError("No strategy cards available for fallback plan")

    action_steps = [_fallback_action_from_card(card, idx) for idx, card in enumerate(chosen_cards)]

    respite_duration = 15 if support_hint == "none" else 30
    respite_resource = "自己独处" if support_hint == "none" else "家庭成员接手"

    return Plan48hResponse(
        today_cut_list=["取消一项非必要外出", "今晚不做高难度任务", "把目标降到只完成第一步"][:3],
        priority_scenarios=(scenarios or ["transition"])[:2],
        respite_slots=[
            RespiteSlot(
                duration_minutes=respite_duration,
                resource=respite_resource,
                handoff_card={
                    "triggers_top3": ["过渡", "等待", "噪音"],
                    "soothing_top3": ["提前预告", "安静角落", "低语速"],
                    "donts_top3": ["不要强拉", "不要追问", "不要大声"],
                },
            )
        ],
        messages=[
            PlanMessage(target="teacher", text="今天孩子负荷较高，请减少临时变更并使用两步指令。"),
            PlanMessage(target="family", text="今晚优先执行低刺激流程，冲突升级时按退场卡处理。"),
        ],
        exit_card_3steps=[
            "降刺激：降低光线与噪音，停止语言输入 30 秒。",
            "给选择：只给两个可行选项，不追问原因。",
            "安全退场：若升级，转移到安静区并联系支持者。",
        ],
        tomorrow_plan=[
            "明早复用同样的低刺激起床流程。",
            "预留一次 15-30 分钟微喘息。",
            "仅追踪一个关键触发器。",
        ],
        action_steps=action_steps,
        citations=[card.card_id for card in chosen_cards],
        safety_flags=["risk:" + risk_level],
    )


def build_fallback_script(cards: Iterable[StrategyCard], scenario: str, intensity: str) -> ScriptResponse:
    chosen_cards = list(cards)[:2]
    if not chosen_cards:
        raise ValueError("No strategy cards available for fallback script")

    step_candidates: list[str] = []
    donts: list[str] = []
    exit_plan: list[str] = []

    for card in chosen_cards:
        step_candidates.extend(card.steps_json)
        donts.extend(card.donts_json)
        exit_plan.extend(card.escalate_json)

    while len(step_candidates) < 3:
        step_candidates.append("保持低语速并等待 5 秒再给下一步提示。")

    if len(donts) < 2:
        donts.extend(["不要强拉身体", "不要连续追问"])

    if not exit_plan:
        exit_plan.append("若升级到重度，立即执行安全退场并联系支持者。")

    script_line = chosen_cards[0].scripts_json.get("parent", "我看到你很难受，我们先做第一步。")

    return ScriptResponse(
        steps=step_candidates[:3],
        script_line=f"[{scenario}/{intensity}] {script_line}",
        donts=list(dict.fromkeys(donts))[:3],
        exit_plan=list(dict.fromkeys(exit_plan))[:3],
        citations=[card.card_id for card in chosen_cards],
    )


def build_safety_block(
    reason: str,
    *,
    severity: str = "quality",
    safe_next_steps: list[str] | None = None,
    do_not_do: list[str] | None = None,
    say_this_now: str | None = None,
    exit_plan: list[str] | None = None,
    help_now: list[str] | None = None,
    low_stim_recommended: bool = True,
    conflict_explanation: str | None = None,
    alternatives: list[str] | None = None,
) -> SafetyBlockResponse:
    default_safe_next_steps = {
        "high_risk": [
            "先停止当前要求，只保留安全陪伴。",
            "移开危险物和围观者，只留一位沟通者。",
            "把孩子和自己带到更安静、更开阔的位置。",
        ],
        "conflict": [
            "立刻停用与禁忌冲突的动作或说法。",
            "改用低刺激短句，只给一个边界。",
            "若仍升级，直接执行退场方案，不再坚持原任务。",
        ],
        "quality": [
            "先把目标缩到只保留安全和降刺激。",
            "只执行一个动作，再等 5 秒观察。",
            "若 10 分钟仍无效，转入退场或求助。",
        ],
    }
    default_do_not_do = {
        "high_risk": ["不要围堵", "不要争辩", "不要突然触碰"],
        "conflict": ["不要继续原动作", "不要补长解释", "不要同时提多个要求"],
        "quality": ["不要一次做三件事", "不要连续追问", "不要提高音量"],
    }
    default_say_this = {
        "high_risk": "我现在先保证安全，不要求你立刻完成任何事。",
        "conflict": "我先停下这个做法，换一个你更能接受的方式。",
        "quality": "我们先只做一步，别的先暂停。",
    }
    default_exit_plan = {
        "high_risk": [
            "先停任务，移开危险物。",
            "转到安静区域，保持可见距离。",
            "持续升级或有人身风险时立即求助。",
        ],
        "conflict": [
            "停止冲突动作，退后半步。",
            "重复一句短句，带去安静处。",
            "若继续升级，联系支持者接手。",
        ],
        "quality": [
            "停止当前目标，先降刺激。",
            "只给两个可行选项，不追问。",
            "若仍卡住，直接退场并稍后再试。",
        ],
    }
    default_help_now = {
        "high_risk": [
            "若存在持续自伤/他伤风险，请立即联系当地急救或危机热线。",
            "同步通知学校/社区已知支持联系人立即介入。",
        ],
        "conflict": [
            "若 10 分钟内仍持续升级，请联系支持者到场或接手。",
        ],
        "quality": [
            "若连续两轮都无效，请联系支持者一起执行退场。",
        ],
    }

    return SafetyBlockResponse(
        severity=severity,  # type: ignore[arg-type]
        block_reason=reason,
        safe_next_steps=safe_next_steps or default_safe_next_steps.get(severity, default_safe_next_steps["quality"]),
        do_not_do=do_not_do or default_do_not_do.get(severity, default_do_not_do["quality"]),
        say_this_now=say_this_now or default_say_this.get(severity, default_say_this["quality"]),
        exit_plan=exit_plan or default_exit_plan.get(severity, default_exit_plan["quality"]),
        help_now=help_now or default_help_now.get(severity, default_help_now["quality"]),
        low_stim_recommended=low_stim_recommended,
        conflict_explanation=conflict_explanation,
        alternatives=alternatives or [],
        environment_checklist=safe_next_steps or default_safe_next_steps.get(severity, default_safe_next_steps["quality"]),
        emergency_guidance=help_now or default_help_now.get(severity, default_help_now["quality"]),
        emergency_contact_template="当前出现高风险失控信号，请立即协助到场/接手，地点：____，联系方式：____。",
    )


def build_fallback_coach_tip(risk_level: str) -> str:
    mapping = {
        "green": "今天只记录一次有效触发器与一个成功动作。",
        "yellow": "今天目标：提前预告一次过渡 + 安排 15 分钟微喘息。",
        "red": "今天先保安全与降刺激，其他目标全部降级。",
    }
    return mapping.get(risk_level, mapping["yellow"])


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _contains_any(values: list[str], candidates: set[str]) -> bool:
    return any(item in candidates for item in values)


def build_fallback_today_focus(context: dict[str, object]) -> TodayFocusResponse:
    transition_difficulty = _as_float(context.get("transition_difficulty"))
    meltdown_count = int(context.get("meltdown_count", 0)) if isinstance(context.get("meltdown_count"), (int, float)) else 0
    child_sleep_hours = _as_float(context.get("child_sleep_hours")) or 0.0
    caregiver_sleep_quality = _as_float(context.get("caregiver_sleep_quality")) or 0.0
    caregiver_stress = _as_float(context.get("caregiver_stress")) or 0.0
    sensory_overload_level = str(context.get("sensory_overload_level") or "light")
    support_available = str(context.get("support_available") or "one")
    today_activities = _as_string_list(context.get("today_activities"))
    today_learning_tasks = _as_string_list(context.get("today_learning_tasks"))
    negative_emotions = _as_string_list(context.get("negative_emotions"))

    has_transition_risk = (transition_difficulty is not None and transition_difficulty >= 7) or meltdown_count >= 2
    has_outing_pressure = _contains_any(today_activities, {"医生预约", "社交活动", "外出安排", "学校活动", "需要长途通勤"})
    has_anxious_signals = _contains_any(negative_emotions, {"焦虑", "恐惧", "社交回避"})
    has_learning_tasks = bool(today_learning_tasks)
    has_low_capacity = child_sleep_hours <= 5 or caregiver_sleep_quality <= 4 or caregiver_stress >= 8

    if has_transition_risk:
        return TodayFocusResponse(
            today_one_thing="今天只保一个关键过渡",
            headline="先把最难的那个过渡单独做完",
            reminders=[
                TodayReminderItem(
                    eyebrow="这次最容易做偏",
                    title="不要连续催促或临时加码",
                    body="一次只给一步，没完成前不要追加第二个要求。"
                ),
                TodayReminderItem(
                    eyebrow="现场开始卡住",
                    title="先停输入，再给二选一",
                    body="先安静 10 秒，再只给两个可接受出口。"
                ),
            ],
        )

    if has_outing_pressure or has_anxious_signals or sensory_overload_level in {"medium", "heavy"}:
        return TodayFocusResponse(
            today_one_thing="今天先把外出预告讲清楚",
            headline="先做一次低刺激预告，再出门",
            reminders=[
                TodayReminderItem(
                    eyebrow="这次最容易做偏",
                    title="不要临时改流程或加快节奏",
                    body="提前说顺序，只保留最必要安排，不临场加项目。"
                ),
                TodayReminderItem(
                    eyebrow="现场开始卡住",
                    title="一紧张就先减输入",
                    body="压低声音，少解释，只重复眼前这一步。"
                ),
            ],
        )

    if has_learning_tasks:
        return TodayFocusResponse(
            today_one_thing="今天先把任务第一步做出来",
            headline="先完成第一步，不追整段",
            reminders=[
                TodayReminderItem(
                    eyebrow="这次最容易做偏",
                    title="不要一开始就追完整",
                    body="把任务切到最小动作，做完第一步再决定要不要继续。"
                ),
                TodayReminderItem(
                    eyebrow="现场开始卡住",
                    title="一抗拒就改成陪做 30 秒",
                    body="先一起开始，再慢慢退出辅助，不要当场拉长战线。"
                ),
            ],
        )

    if has_low_capacity or support_available == "none":
        support_body = "支持不足时先停一项任务，换成安静短流程。" if support_available == "none" else "一旦卡住就先减负，只留最低目标。"
        return TodayFocusResponse(
            today_one_thing="今天先减负，只保最低目标",
            headline="先砍掉非必要任务，保住配合",
            reminders=[
                TodayReminderItem(
                    eyebrow="这次最容易做偏",
                    title="不要把低能量日当训练日",
                    body="能延期的先延期，只留今天非做不可的一步。"
                ),
                TodayReminderItem(
                    eyebrow="现场开始卡住",
                    title="先留退路，不要硬顶",
                    body=support_body
                ),
            ],
        )

    return TodayFocusResponse(
        today_one_thing="今天先把最关键的一步做稳",
        headline="先完成今天最值的一步",
        reminders=[
            TodayReminderItem(
                eyebrow="这次最容易做偏",
                title="不要同时推进两件事",
                body="只盯一个目标，其他事情先挂起。"
            ),
            TodayReminderItem(
                eyebrow="现场开始卡住",
                title="先缩小目标，再继续",
                body="把要求缩到第一步，做完再看要不要往下走。"
            ),
        ],
    )
