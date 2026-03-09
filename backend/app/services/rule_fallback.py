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


def build_safety_block(reason: str) -> SafetyBlockResponse:
    return SafetyBlockResponse(
        block_reason=reason,
        environment_checklist=[
            "先确保周围无尖锐/可投掷物，保持安全距离。",
            "减少声音与灯光刺激，移除围观者。",
            "只保留一位主要沟通者，使用短句。",
        ],
        emergency_guidance=[
            "若存在持续自伤/他伤风险，请立即联系当地急救或危机热线。",
            "通知学校/社区已知支持联系人同步介入。",
        ],
        emergency_contact_template="当前出现高风险失控信号，请立即协助到场/接手，地点：____，联系方式：____。",
    )


def build_fallback_coach_tip(risk_level: str) -> str:
    mapping = {
        "green": "今天只记录一次有效触发器与一个成功动作。",
        "yellow": "今天目标：提前预告一次过渡 + 安排 15 分钟微喘息。",
        "red": "今天先保安全与降刺激，其他目标全部降级。",
    }
    return mapping.get(risk_level, mapping["yellow"])
