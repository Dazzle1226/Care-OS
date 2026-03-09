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


class SafetyAgent:
    conflict_pairs = [
        ("触", ["抱", "拉", "按住", "触摸"]),
        ("大声", ["大声", "吼", "提高音量"]),
        ("追问", ["为什么", "你怎么", "继续问"]),
    ]

    def _has_high_risk_keywords(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in settings.high_risk_keywords)

    def should_block_high_risk(self, explicit_flag: bool, texts: list[str]) -> SafetyDecision:
        merged = "\n".join(texts)
        if explicit_flag or self._has_high_risk_keywords(merged):
            return SafetyDecision(blocked=True, block=build_safety_block("检测到高风险信号，已进入安全阻断模式"))
        return SafetyDecision(blocked=False)

    def _check_dont_conflicts(self, profile_donts: list[str], candidate_texts: list[str]) -> list[str]:
        conflicts: list[str] = []
        merged = "\n".join(candidate_texts)

        for dont in profile_donts:
            for marker, risky_tokens in self.conflict_pairs:
                if marker not in dont:
                    continue
                for tok in risky_tokens:
                    if tok not in merged:
                        continue

                    conflict_hit = False
                    for hit in re.finditer(re.escape(tok), merged):
                        prefix = merged[max(0, hit.start() - 4) : hit.start()]
                        if any(neg in prefix for neg in ["不要", "不可", "别"]):
                            continue
                        conflict_hit = True
                        break
                    if not conflict_hit:
                        continue
                    conflicts.append(f"禁忌“{dont}”与建议动作冲突")
                    break
                if conflicts:
                    break
        return conflicts

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

        conflicts = self._check_dont_conflicts(profile_donts, text_bank)
        if conflicts:
            return SafetyDecision(blocked=True, block=build_safety_block(conflicts[0]))

        return SafetyDecision(blocked=False)

    def validate_script(self, script: ScriptResponse, profile_donts: list[str], explicit_high_risk: bool, free_text: str) -> SafetyDecision:
        if not script.citations:
            return SafetyDecision(blocked=True, block=build_safety_block("脚本缺少策略卡引用，已阻断"))

        text_bank = [*script.steps, script.script_line, *script.donts, *script.exit_plan, free_text]
        # 高风险阻断应基于用户输入信号，而不是系统生成文本本身。
        high_risk = self.should_block_high_risk(explicit_high_risk, [free_text])
        if high_risk.blocked:
            return high_risk

        conflicts = self._check_dont_conflicts(profile_donts, text_bank)
        if conflicts:
            return SafetyDecision(blocked=True, block=build_safety_block(conflicts[0]))

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

        conflicts = self._check_dont_conflicts(profile_donts, text_bank)
        if conflicts:
            return SafetyDecision(blocked=True, block=build_safety_block(conflicts[0]))

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
            support.headline,
            support.situation_summary,
            support.school_message,
            support.respite_suggestion.title,
            support.respite_suggestion.summary,
            support.respite_suggestion.support_plan,
            *support.child_signals,
            *support.caregiver_signals,
            *support.voice_guidance,
            *support.exit_plan,
            *support.personalized_strategies,
            free_text,
        ]
        for step in support.action_plan:
            text_bank.extend([step.title, step.action, step.parent_script, step.why_it_fits])

        conflicts = self._check_dont_conflicts(profile_donts, text_bank)
        if conflicts:
            return SafetyDecision(blocked=True, block=build_safety_block(conflicts[0]))

        return SafetyDecision(blocked=False)
