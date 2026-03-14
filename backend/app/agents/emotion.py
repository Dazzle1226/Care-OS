from __future__ import annotations

from collections.abc import Iterable

from app.schemas.domain import EmotionAssessment, FrictionSupportGenerateRequest


class EmotionAgent:
    child_escalation_markers = ("哭", "尖叫", "崩溃", "失控", "不要", "躺地", "打人", "逃跑")
    caregiver_strain_markers = ("我很累", "撑不住", "不知道怎么办", "不想再说", "太难了", "快点")

    def assess(
        self,
        payload: FrictionSupportGenerateRequest,
        fused_text: str,
        historical_patterns: Iterable[str] | None = None,
    ) -> EmotionAssessment:
        text_bank = " ".join(part for part in [payload.free_text, fused_text, " ".join(historical_patterns or [])] if part).lower()

        child_emotion = self._child_emotion(payload, text_bank)
        caregiver_emotion = self._caregiver_emotion(payload, text_bank)
        child_overload = self._child_overload(payload, text_bank)
        caregiver_overload = self._caregiver_overload(payload, text_bank)
        confidence_drift = self._confidence_drift(payload, text_bank)

        reasoning: list[str] = []
        if child_overload == "high":
            reasoning.append("孩子当前更接近过载或升级，优先降刺激。")
        elif child_overload == "medium":
            reasoning.append("孩子状态脆弱，先避免继续加码。")
        if caregiver_overload == "high":
            reasoning.append("照护者负荷明显偏高，建议压缩动作和语言。")
        elif caregiver_overload == "medium":
            reasoning.append("照护者已接近吃力阈值，建议提前准备交接。")
        if confidence_drift != "stable":
            reasoning.append("执行信心在下降，应该减少步骤并更快得到反馈。")

        adjustments: list[str] = []
        if child_overload == "high":
            adjustments.extend(["切到低刺激模式", "保留一个最小动作", "准备快速退场"])
        elif child_overload == "medium":
            adjustments.extend(["减少语言密度", "先做一步", "避免追加要求"])

        if caregiver_overload == "high":
            adjustments.extend(["压缩成一步", "优先安排交接", "避免继续解释"])
        elif caregiver_overload == "medium":
            adjustments.extend(["提前准备交接口径", "保留短句提示"])

        if confidence_drift == "critical":
            adjustments.append("系统应主动给更轻方案")
        elif confidence_drift == "dropping":
            adjustments.append("优先展示当前第一步，不展开全部方案")

        confidence = 0.5
        if child_overload == "high" or caregiver_overload == "high":
            confidence += 0.2
        if payload.free_text.strip():
            confidence += 0.1
        if fused_text.strip():
            confidence += 0.1

        return EmotionAssessment(
            child_emotion=child_emotion,
            caregiver_emotion=caregiver_emotion,
            child_overload_level=child_overload,
            caregiver_overload_level=caregiver_overload,
            confidence_drift=confidence_drift,
            recommended_adjustments=list(dict.fromkeys(adjustments))[:4],
            confidence=min(round(confidence, 2), 0.95),
            reasoning=reasoning[:4] or ["先按当前最小动作推进，继续观察是否稳定。"],
        )

    def _child_emotion(self, payload: FrictionSupportGenerateRequest, text_bank: str) -> str:
        if payload.child_state == "meltdown" or payload.sensory_overload_level == "heavy" or any(
            marker in text_bank for marker in self.child_escalation_markers
        ):
            return "meltdown_risk"
        if payload.child_state in {"sensory_overload", "conflict"} or payload.meltdown_count >= 2:
            return "escalating"
        if payload.child_state == "emotional_wave" or payload.transition_difficulty >= 6:
            return "fragile"
        return "calm"

    def _caregiver_emotion(self, payload: FrictionSupportGenerateRequest, text_bank: str) -> str:
        if payload.caregiver_stress >= 8 or payload.caregiver_fatigue >= 8 or any(
            marker in text_bank for marker in self.caregiver_strain_markers
        ):
            return "overloaded"
        if payload.caregiver_stress >= 7 or payload.caregiver_fatigue >= 7:
            return "anxious"
        if payload.caregiver_stress >= 5:
            return "strained"
        return "calm"

    def _child_overload(self, payload: FrictionSupportGenerateRequest, text_bank: str) -> str:
        if payload.child_state == "meltdown" or payload.sensory_overload_level == "heavy" or "太吵" in text_bank:
            return "high"
        if payload.child_state in {"sensory_overload", "conflict"} or payload.sensory_overload_level == "medium":
            return "medium"
        return "low"

    def _caregiver_overload(self, payload: FrictionSupportGenerateRequest, text_bank: str) -> str:
        if (
            payload.caregiver_stress >= 8
            or payload.caregiver_fatigue >= 8
            or payload.caregiver_sleep_quality <= 3
            or "撑不住" in text_bank
        ):
            return "high"
        if payload.caregiver_stress >= 6 or payload.caregiver_fatigue >= 6 or payload.caregiver_sleep_quality <= 5:
            return "medium"
        return "low"

    def _confidence_drift(self, payload: FrictionSupportGenerateRequest, text_bank: str) -> str:
        if payload.confidence_to_follow_plan <= 3 or any(token in text_bank for token in ("不知道怎么办", "跟不上", "不想再说")):
            return "critical"
        if payload.confidence_to_follow_plan <= 5 or any(token in text_bank for token in ("有点难", "不知道", "没用")):
            return "dropping"
        return "stable"
