from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.config import settings
from app.schemas.domain import (
    FrictionSupportPlan,
    MicroRespitePlan,
    Plan48hResponse,
    SafetyBlockResponse,
    ScriptResponse,
)
from app.services.rule_fallback import build_safety_block


@dataclass(slots=True)
class SafetyDecision:
    blocked: bool
    block: SafetyBlockResponse | None = None


@dataclass(slots=True)
class ConflictMatch:
    dont: str
    conflict_text: str
    explanation: str
    alternatives: list[str]
    do_not_do: list[str]


class SafetyAgent:
    conflict_rules = [
        {
            "markers": ["触", "碰"],
            "risky_tokens": ["抱", "拉", "按住", "触摸", "强拉", "拖走", "拽"],
            "explanation": "孩子档案里标记了不可触碰，身体介入会明显增加反抗或升级风险。",
            "alternatives": [
                "退后半步，只保留一位沟通者。",
                "改用手指物品或两个选项，不碰身体。",
                "必要时直接转去安静处旁站陪伴。",
            ],
            "do_not_do": ["不要抱住", "不要强拉", "不要突然触碰"],
        },
        {
            "markers": ["大声", "吼"],
            "risky_tokens": ["大声", "吼", "提高音量", "喊"],
            "explanation": "档案里标记了不可大声，音量升级会让孩子更难回到可执行状态。",
            "alternatives": [
                "先停 5 秒，把音量降到短句低声。",
                "移开围观者，只重复同一句边界。",
                "先关掉额外声音，再给一个选择。",
            ],
            "do_not_do": ["不要提高音量", "不要重复喊", "不要围观施压"],
        },
        {
            "markers": ["追问", "为什么"],
            "risky_tokens": ["为什么", "你怎么", "继续问", "解释一下"],
            "explanation": "档案里标记了不要追问，连续追问会把孩子重新推回对抗。",
            "alternatives": [
                "只说现在要做的一步，不问原因。",
                "说完后等 5 秒，不追加第二段解释。",
                "若仍卡住，直接切到退场或低刺激恢复。",
            ],
            "do_not_do": ["不要追问原因", "不要连问几句", "不要边问边催"],
        },
    ]

    def _has_high_risk_keywords(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in settings.high_risk_keywords)

    def should_block_high_risk(self, explicit_flag: bool, texts: list[str]) -> SafetyDecision:
        merged = "\n".join(texts)
        if explicit_flag or self._has_high_risk_keywords(merged):
            return SafetyDecision(
                blocked=True,
                block=build_safety_block(
                    "检测到高风险信号，已进入安全阻断模式",
                    severity="high_risk",
                ),
            )
        return SafetyDecision(blocked=False)

    def _check_dont_conflicts(self, profile_donts: list[str], candidate_texts: list[str]) -> ConflictMatch | None:
        merged = "\n".join(candidate_texts)

        for dont in profile_donts:
            for rule in self.conflict_rules:
                if not any(marker in dont for marker in rule["markers"]):
                    continue
                for tok in rule["risky_tokens"]:
                    if tok not in merged:
                        continue

                    conflict_hit = False
                    for hit in re.finditer(re.escape(tok), merged):
                        clause_start = max(merged.rfind("。", 0, hit.start()), merged.rfind("\n", 0, hit.start())) + 1
                        prefix = merged[clause_start : hit.start()]
                        if any(neg in prefix for neg in ["不要", "不可", "别"]):
                            continue
                        conflict_hit = True
                        break
                    if not conflict_hit:
                        continue
                    return ConflictMatch(
                        dont=dont,
                        conflict_text=f"禁忌“{dont}”与建议动作冲突",
                        explanation=rule["explanation"],
                        alternatives=list(rule["alternatives"]),
                        do_not_do=list(rule["do_not_do"]),
                    )
        return None

    def _build_conflict_block(self, match: ConflictMatch) -> SafetyBlockResponse:
        return build_safety_block(
            match.conflict_text,
            severity="conflict",
            do_not_do=match.do_not_do,
            conflict_explanation=match.explanation,
            alternatives=match.alternatives,
        )

    def validate_plan(self, plan: Plan48hResponse, profile_donts: list[str], explicit_high_risk: bool, free_text: str) -> SafetyDecision:
        if not plan.citations:
            return SafetyDecision(blocked=True, block=build_safety_block("计划缺少策略卡引用，已阻断"))

        text_bank = [
            *plan.today_cut_list,
            *plan.priority_scenarios,
            *plan.exit_card_3steps,
            *plan.tomorrow_plan,
            *[msg.text for msg in plan.messages],
            *[item.step for item in plan.action_steps],
            *[item.script for item in plan.action_steps],
            free_text,
        ]

        # 高风险阻断应基于用户输入信号，而不是系统生成文本本身。
        high_risk = self.should_block_high_risk(explicit_high_risk, [free_text])
        if high_risk.blocked:
            return high_risk

        conflict = self._check_dont_conflicts(profile_donts, text_bank)
        if conflict is not None:
            return SafetyDecision(blocked=True, block=self._build_conflict_block(conflict))

        return SafetyDecision(blocked=False)

    def validate_script(self, script: ScriptResponse, profile_donts: list[str], explicit_high_risk: bool, free_text: str) -> SafetyDecision:
        if not script.citations:
            return SafetyDecision(blocked=True, block=build_safety_block("脚本缺少策略卡引用，已阻断"))

        text_bank = [*script.steps, script.script_line, *script.donts, *script.exit_plan, free_text]
        # 高风险阻断应基于用户输入信号，而不是系统生成文本本身。
        high_risk = self.should_block_high_risk(explicit_high_risk, [free_text])
        if high_risk.blocked:
            return high_risk

        conflict = self._check_dont_conflicts(profile_donts, text_bank)
        if conflict is not None:
            return SafetyDecision(blocked=True, block=self._build_conflict_block(conflict))

        return SafetyDecision(blocked=False)

    def validate_respite_plan(
        self,
        plan: MicroRespitePlan,
        profile_donts: list[str],
        explicit_high_risk: bool,
        free_text: str,
        support_available: str,
    ) -> SafetyDecision:
        if len(plan.options) < 3:
            return SafetyDecision(blocked=True, block=build_safety_block("微喘息建议不足 3 条，已阻断"))

        if any(not option.source_card_ids for option in plan.options):
            return SafetyDecision(blocked=True, block=build_safety_block("微喘息建议缺少策略卡引用，已阻断"))

        high_risk = self.should_block_high_risk(explicit_high_risk, [free_text])
        if high_risk.blocked:
            return high_risk

        text_bank = [plan.headline, plan.context_summary, *plan.safety_notes]
        for option in plan.options:
            text_bank.extend(
                [
                    option.title,
                    option.summary,
                    option.fit_reason,
                    option.child_focus,
                    option.parent_focus,
                    option.support_plan,
                    *option.setup_steps,
                    *option.instructions,
                    *option.safety_notes,
                ]
            )

        conflict = self._check_dont_conflicts(profile_donts, text_bank)
        if conflict is not None:
            return SafetyDecision(blocked=True, block=self._build_conflict_block(conflict))

        if plan.low_stimulation_only and any(not option.low_stimulation_only for option in plan.options):
            return SafetyDecision(blocked=True, block=build_safety_block("当前仅允许低刺激微喘息方案，已阻断不匹配建议"))

        if support_available == "none" and any(option.duration_minutes > 15 for option in plan.options):
            return SafetyDecision(blocked=True, block=build_safety_block("无人接手时，微喘息时长不能超过 15 分钟"))

        if all(option.requires_manual_review for option in plan.options):
            return SafetyDecision(blocked=True, block=build_safety_block("当前建议均需人工复核，暂不直接推荐"))

        return SafetyDecision(blocked=False)

    def validate_friction_support(
        self,
        support: FrictionSupportPlan,
        profile_donts: list[str],
        explicit_high_risk: bool,
        free_text: str,
    ) -> SafetyDecision:
        if not support.citations:
            return SafetyDecision(blocked=True, block=build_safety_block("高摩擦支持缺少策略卡引用，已阻断"))

        high_risk = self.should_block_high_risk(explicit_high_risk, [free_text])
        if high_risk.blocked:
            return high_risk

        text_bank = [
            support.preset_label,
            support.headline,
            support.situation_summary,
            support.school_message,
            support.respite_suggestion.title,
            support.respite_suggestion.summary,
            support.respite_suggestion.support_plan,
            support.low_stim_mode.headline,
            *support.child_signals,
            *support.caregiver_signals,
            *support.donts,
            *support.say_this,
            *support.voice_guidance,
            *support.exit_plan,
            *support.low_stim_mode.actions,
            support.crisis_card.title,
            *support.crisis_card.badges,
            *support.crisis_card.first_do,
            *support.crisis_card.donts,
            *support.crisis_card.say_this,
            *support.crisis_card.exit_plan,
            *support.crisis_card.help_now,
            *support.personalized_strategies,
            free_text,
        ]
        for step in support.action_plan:
            text_bank.extend([step.title, step.action, step.parent_script, step.why_it_fits])

        conflict = self._check_dont_conflicts(profile_donts, text_bank)
        if conflict is not None:
            return SafetyDecision(blocked=True, block=self._build_conflict_block(conflict))

        return SafetyDecision(blocked=False)
