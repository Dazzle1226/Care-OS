from __future__ import annotations

import json

from app.models import ChildProfile, Family
from app.schemas.domain import OnboardingSupportCard, OnboardingSupportCardSection
from app.services.llm_client import LLMClient, LLMUnavailableError
from app.services.profile_builder import normalize_list

COMMUNICATION_LABELS = {
    "none": "无语言/图片辅助",
    "single_word": "单词/短语为主",
    "short_sentence": "短句为主",
    "fluent": "句子沟通",
}
SCENARIO_LABELS = {
    "transition": "过渡期",
    "bedtime": "睡前流程",
    "homework": "学习任务",
    "outing": "外出与社交",
}


def _ctx_list(context: dict[str, object], key: str, fallback: str) -> list[str]:
    values = normalize_list(context.get(key) or [], limit=8)
    return values or [fallback]


def _primary_focus(profile: ChildProfile) -> tuple[str, str]:
    scenario_key = profile.high_friction_scenarios[0] if profile.high_friction_scenarios else "transition"
    trigger = profile.triggers[0] if profile.triggers else "过渡"
    return scenario_key, trigger


def _communication_items(profile: ChildProfile, learning_needs: list[str]) -> list[str]:
    level = COMMUNICATION_LABELS.get(profile.language_level, profile.language_level)
    items = [f"常用沟通：{level}"]
    if profile.language_level in {"none", "single_word", "short_sentence"}:
        items.append("长句/多步骤：容易卡住")
    else:
        items.append("长句/多步骤：紧张时仍可能吃力")
    items.append(
        f"更适合：{' / '.join(normalize_list(['短句', '二选一', '视觉提示', *learning_needs[:2]], limit=3))}"
    )
    return items


def _early_signals(context: dict[str, object]) -> list[str]:
    behavior_patterns = normalize_list(context.get("behavior_patterns") or [], limit=3)
    emotion_patterns = normalize_list(context.get("emotion_patterns") or [], limit=2)
    return normalize_list(
        [*behavior_patterns, *emotion_patterns, "捂耳朵", "走来走去", "不回应", "重复提问"],
        limit=3,
    )


def _support_methods(profile: ChildProfile) -> list[str]:
    return normalize_list(
        [*profile.soothing_methods, "给选择", "去安静处", "减少说话", "使用计时器", "用喜欢的物品过渡"],
        limit=3,
    )


def _donts(profile: ChildProfile) -> list[str]:
    return normalize_list(
        [*profile.donts, "不要强拉", "不要提高音量", "不要多人同时说", "不要追问为什么"],
        limit=3,
    )


def _escalation_contact(context: dict[str, object]) -> str:
    emergency_contacts = normalize_list(context.get("emergency_contacts") or [], limit=2)
    supporters = normalize_list(context.get("available_supporters") or [], limit=2)
    if emergency_contacts:
        return emergency_contacts[0]
    if supporters:
        return supporters[0]
    return "家长/主要照护者"


def _safety_items(profile: ChildProfile, context: dict[str, object], scenario_key: str) -> list[str]:
    behavior_risks = normalize_list(context.get("behavior_risks") or [], limit=3)
    allergies = normalize_list(context.get("allergies") or [], limit=2)
    medications = normalize_list(context.get("medications") or [], limit=2)

    risk_item = f"风险重点：{'、'.join(behavior_risks)}" if behavior_risks else "风险重点：未记录明显走失/攻击风险"
    if any("逃跑" in item or "走失" in item for item in behavior_risks):
        solo_limit = "不要离开视线，也不要单独经过门口或马路边"
    elif any("攻击" in item or "打人" in item for item in behavior_risks):
        solo_limit = "不要带去拥挤、排队或多人靠近的场景"
    elif scenario_key in {"transition", "outing"} or any("等待" in item for item in profile.triggers):
        solo_limit = "不要临时加新流程，也不要带去人多久等的场景"
    else:
        solo_limit = "不要单独安排高要求任务"

    medical_item = "药物/过敏：无当场特殊信息"
    if allergies or medications:
        medical_item = f"药物/过敏：{'、'.join([*allergies, *medications][:3])}"

    return [risk_item, solo_limit, medical_item]


class SupportCardAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _profile_payload(self, family: Family, profile: ChildProfile) -> dict[str, object]:
        context = profile.school_context or {}
        scenario_key, trigger = _primary_focus(profile)
        return {
            "family_name": family.name,
            "child_name": str(context.get("child_name") or "孩子"),
            "age_band": profile.age_band,
            "language_level": profile.language_level,
            "scenario_focus": SCENARIO_LABELS.get(scenario_key, scenario_key),
            "trigger_focus": trigger,
            "triggers": profile.triggers,
            "sensory_flags": profile.sensory_flags,
            "soothing_methods": profile.soothing_methods,
            "donts": profile.donts,
            "high_friction_scenarios": profile.high_friction_scenarios,
            "school_context": {
                "learning_needs": normalize_list(context.get("learning_needs") or [], limit=4),
                "behavior_patterns": normalize_list(context.get("behavior_patterns") or [], limit=4),
                "emotion_patterns": normalize_list(context.get("emotion_patterns") or [], limit=4),
                "behavior_risks": normalize_list(context.get("behavior_risks") or [], limit=4),
                "available_supporters": normalize_list(context.get("available_supporters") or [], limit=4),
                "supporter_availability": normalize_list(context.get("supporter_availability") or [], limit=4),
                "allergies": normalize_list(context.get("allergies") or [], limit=3),
                "medications": normalize_list(context.get("medications") or [], limit=3),
                "emergency_contacts": normalize_list(context.get("emergency_contacts") or [], limit=3),
            },
        }

    def _attempt_llm_cards(self, family: Family, profile: ChildProfile) -> list[OnboardingSupportCard]:
        system_prompt = (
            "你是 ASD 家庭档案支持卡助手。"
            "只输出 JSON，不要解释。"
            "所有字段必须短句，不能写长段落。"
            "只能基于提供的家庭档案，不要编造未提供的信息。"
            "如果没有当天状态，必须明确写“未提供当日信息”或同义短句。"
        )
        user_prompt = json.dumps(
            {
                "task": "基于家庭档案生成支持卡和交接卡",
                "profile": self._profile_payload(family, profile),
                "output": {
                    "support_cards": [
                        {
                            "card_id": "固定为 ONB-SUPPORT 或 ONB-HANDOFF",
                            "icon": "support 或 handoff",
                            "title": "支持卡 或 交接卡",
                            "summary": "用途说明，1 句",
                            "one_liner": "一句话理解，1 句",
                            "quick_actions": ["先看这3条，2到3条短句"],
                            "sections": [
                                {
                                    "key": "固定短 key",
                                    "title": "小标题",
                                    "items": ["1到3条短句，不要段落"],
                                }
                            ],
                        }
                    ]
                },
                "constraints": {
                    "cards_exact": 2,
                    "support_card": {
                        "title": "支持卡",
                        "icon": "support",
                        "sections_exact": [
                            "沟通",
                            "触发器",
                            "早期信号",
                            "有效支持",
                            "不要做",
                            "升级处理",
                        ],
                    },
                    "handoff_card": {
                        "title": "交接卡",
                        "icon": "handoff",
                        "sections_exact": [
                            "当前状态",
                            "现在要做",
                            "安抚方式",
                            "禁忌",
                            "升级步骤",
                            "安全信息",
                            "联系方式",
                        ],
                    },
                    "section_items_max": 3,
                    "quick_actions_min": 2,
                    "quick_actions_max": 3,
                    "avoid_jargon": True,
                    "keep_scannable": True,
                },
            },
            ensure_ascii=False,
        )
        raw = self.llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        cards_raw = raw.get("support_cards")
        if not isinstance(cards_raw, list) or len(cards_raw) != 2:
            raise ValueError("Invalid support cards payload")
        return [OnboardingSupportCard.model_validate(item) for item in cards_raw]

    def _fallback_cards(self, family: Family, profile: ChildProfile) -> list[OnboardingSupportCard]:
        context = profile.school_context or {}
        child_name = str(context.get("child_name") or "孩子")
        learning_needs = normalize_list(context.get("learning_needs") or [], limit=4)
        scenario_key, trigger = _primary_focus(profile)
        focus_label = SCENARIO_LABELS.get(scenario_key, "当前高摩擦场景")
        communication_items = _communication_items(profile, learning_needs)
        early_signals = _early_signals(context)
        support_methods = _support_methods(profile)
        donts = _donts(profile)
        escalation_contact = _escalation_contact(context)
        supporter_availability = normalize_list(context.get("supporter_availability") or [], limit=2)
        availability_text = f"常见可联系时间：{'、'.join(supporter_availability)}" if supporter_availability else "有需要就先联系家长/主要照护者"

        support_sections = [
            OnboardingSupportCardSection(key="communication", title="沟通", items=communication_items),
            OnboardingSupportCardSection(
                key="triggers",
                title="触发器",
                items=normalize_list(profile.triggers[:4] or ["过渡", "等待", "噪音"], limit=3),
            ),
            OnboardingSupportCardSection(key="signals", title="早期信号", items=early_signals),
            OnboardingSupportCardSection(key="support", title="有效支持", items=support_methods),
            OnboardingSupportCardSection(key="donts", title="不要做", items=donts),
            OnboardingSupportCardSection(
                key="escalation",
                title="升级处理",
                items=[
                    "先停要求，先降刺激",
                    "带去安静处，只说下一步",
                    f"持续升级就联系 {escalation_contact}",
                ],
            ),
        ]

        handoff_sections = [
            OnboardingSupportCardSection(
                key="status",
                title="当前状态",
                items=[
                    "未提供当日信息，先按易受刺激接手",
                    f"最容易卡在：{trigger}",
                    f"先以平稳过完 {focus_label} 为主",
                ],
            ),
            OnboardingSupportCardSection(
                key="now",
                title="现在要做",
                items=[
                    "当前任务只留一件事",
                    "接下来 1-2 小时不临时加要求",
                    f"先保住 {focus_label} 的顺利切换",
                ],
            ),
            OnboardingSupportCardSection(key="soothe", title="安抚方式", items=support_methods),
            OnboardingSupportCardSection(key="taboo", title="禁忌", items=donts),
            OnboardingSupportCardSection(
                key="steps",
                title="升级步骤",
                items=[
                    "1. 停止催促，降低刺激",
                    "2. 带离现场，只给一个选择",
                    f"3. 仍升高就联系 {escalation_contact}",
                ],
            ),
            OnboardingSupportCardSection(
                key="safety",
                title="安全信息",
                items=_safety_items(profile, context, scenario_key),
            ),
            OnboardingSupportCardSection(
                key="contact",
                title="联系方式",
                items=[
                    f"先联系：{escalation_contact}",
                    availability_text,
                    "出现攻击、自伤、逃跑风险时必须联系家长",
                ],
            ),
        ]

        return [
            OnboardingSupportCard(
                card_id="ONB-SUPPORT",
                icon="support",
                title="支持卡",
                summary="给老师、家人、长期协作者，先知道怎么支持，不要现场猜。",
                one_liner=f"日常支持 {child_name} 时，先降刺激，再给清楚的下一步。",
                quick_actions=[
                    "先用短句",
                    support_methods[0],
                    "升级就先退到安静处",
                ],
                sections=support_sections,
            ),
            OnboardingSupportCard(
                card_id="ONB-HANDOFF",
                icon="handoff",
                title="交接卡",
                summary="给临时照护者，重点是现在就能接手，不靠临场猜。",
                one_liner=f"接手时先保平稳，再决定要不要继续 {focus_label} 相关任务。",
                quick_actions=[
                    "先保平稳",
                    support_methods[0],
                    f"升级就联系 {escalation_contact}",
                ],
                sections=handoff_sections,
            ),
        ]

    def generate_cards(self, family: Family, profile: ChildProfile) -> list[OnboardingSupportCard]:
        try:
            return self._attempt_llm_cards(family, profile)
        except (LLMUnavailableError, ValueError, TypeError, json.JSONDecodeError):
            return self._fallback_cards(family, profile)
