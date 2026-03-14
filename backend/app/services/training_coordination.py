from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.emotion import EmotionAgent
from app.agents.signal import SignalAgent
from app.models import DailyCheckin, Family
from app.schemas.domain import CoordinationDecision, EmotionAssessment, FrictionSupportGenerateRequest, SignalOutput
from app.services.policy_learning import PolicyLearningService


@dataclass(slots=True)
class TrainingCoordinationResult:
    signal: SignalOutput
    emotion: EmotionAssessment
    readiness_status: str
    readiness_reason: str
    recommended_action: str
    effective_load_level: str
    task_limit: int
    coordination_hint: str
    used_memory_signals: list[str]


class TrainingCoordinationService:
    def __init__(self) -> None:
        self.signal_agent = SignalAgent()
        self.emotion_agent = EmotionAgent()
        self.policy_learning = PolicyLearningService()

    def assess(
        self,
        db: Session,
        family: Family,
        *,
        extra_context: str = "",
        proposed_load_level: str,
        prefer_lighter: bool = False,
    ) -> TrainingCoordinationResult:
        latest_checkin = db.scalar(
            select(DailyCheckin).where(DailyCheckin.family_id == family.family_id).order_by(desc(DailyCheckin.date)).limit(1)
        )
        payload = self._payload_from_checkin(family=family, latest_checkin=latest_checkin, extra_context=extra_context)
        signal = self.signal_agent.evaluate(db=db, family_id=family.family_id)
        memory_diff = self.policy_learning.build_diff(db, family.family_id)
        used_memory_signals = [
            item.target_key
            for item in memory_diff.strongest_positive[:3]
            if item.target_kind in {"timing", "method", "emotion_pattern", "successful_adjustment"}
        ]
        emotion = self.emotion_agent.assess(payload=payload, fused_text=extra_context, historical_patterns=used_memory_signals)

        readiness_status = "ready"
        readiness_reason = "当前状态允许按计划推进今天训练。"
        recommended_action = "按今天任务顺序练，先完成第一项。"
        effective_load_level = proposed_load_level
        task_limit = {"light": 1, "standard": 2, "adaptive": 3}[proposed_load_level]

        if signal.risk_level == "red" or (
            emotion.child_overload_level == "high" and emotion.caregiver_overload_level in {"medium", "high"}
        ):
            readiness_status = "pause"
            readiness_reason = "今天更适合先稳住情绪和负荷，普通训练先暂停。"
            recommended_action = "先转入低负荷陪伴、降刺激或高摩擦支持，不安排正式训练。"
            effective_load_level = "light"
            task_limit = 0
        elif prefer_lighter or (
            signal.risk_level == "yellow"
            or emotion.caregiver_overload_level == "high"
            or emotion.confidence_drift in {"dropping", "critical"}
            or emotion.child_overload_level == "high"
        ):
            readiness_status = "lighter"
            readiness_reason = "今天可以练，但要压缩成低负担版本，先保成功率。"
            recommended_action = "只保留最重要的一项训练，缩短时长并优先在更熟悉的场景开始。"
            effective_load_level = "light"
            task_limit = 1

        coordination_hint = used_memory_signals[0] if used_memory_signals else recommended_action
        return TrainingCoordinationResult(
            signal=signal,
            emotion=emotion,
            readiness_status=readiness_status,
            readiness_reason=readiness_reason,
            recommended_action=recommended_action,
            effective_load_level=effective_load_level,
            task_limit=task_limit,
            coordination_hint=coordination_hint,
            used_memory_signals=used_memory_signals[:3],
        )

    def to_decision(
        self,
        *,
        result: TrainingCoordinationResult,
        now_step: str,
        now_script: str,
        next_if_not_working: str,
    ) -> CoordinationDecision:
        return CoordinationDecision(
            selected_proposal_id=f"training-{result.readiness_status}",
            alternative_proposal_ids=[],
            decision_reason=result.readiness_reason,
            weight_summary=[
                *result.signal.reasons[:2],
                *result.emotion.reasoning[:2],
                *[f"家庭记忆：{item}" for item in result.used_memory_signals[:1]],
            ][:5],
            replan_triggers=[
                "状态没改善",
                "家长更累了",
                "孩子更抗拒了",
                "用户要求更轻",
            ],
            active_mode="blocked" if result.readiness_status == "pause" else "lighter" if result.readiness_status == "lighter" else "continue",
            now_step=now_step,
            now_script=now_script,
            next_if_not_working=next_if_not_working,
            summary=result.recommended_action,
        )

    def _payload_from_checkin(
        self,
        *,
        family: Family,
        latest_checkin: DailyCheckin | None,
        extra_context: str,
    ) -> FrictionSupportGenerateRequest:
        profile = family.child_profile
        if latest_checkin is None:
            return FrictionSupportGenerateRequest(
                family_id=family.family_id,
                scenario=(profile.high_friction_scenarios[0] if profile and profile.high_friction_scenarios else "transition"),
                child_state="emotional_wave",
                sensory_overload_level="light",
                transition_difficulty=5,
                meltdown_count=0,
                caregiver_stress=5,
                caregiver_fatigue=5,
                caregiver_sleep_quality=6,
                support_available="one",
                confidence_to_follow_plan=6,
                env_changes=[],
                free_text=extra_context[:500],
            )

        details = latest_checkin.details_json or {}
        mood = str(details.get("child_mood_state", "stable"))
        child_state = {
            "anxious": "emotional_wave",
            "sensitive": "sensory_overload",
            "irritable": "conflict",
            "low_energy": "transition_block",
            "stable": "transition_block",
        }.get(mood, "transition_block")
        fatigue = min(10.0, max(0.0, 10 - latest_checkin.caregiver_sleep_hours))
        confidence = max(1.0, 10 - latest_checkin.caregiver_stress)
        return FrictionSupportGenerateRequest(
            family_id=family.family_id,
            scenario=(profile.high_friction_scenarios[0] if profile and profile.high_friction_scenarios else "transition"),
            child_state=child_state,  # type: ignore[arg-type]
            sensory_overload_level=latest_checkin.sensory_overload_level,  # type: ignore[arg-type]
            transition_difficulty=latest_checkin.transition_difficulty,
            meltdown_count=latest_checkin.meltdown_count,
            caregiver_stress=latest_checkin.caregiver_stress,
            caregiver_fatigue=fatigue,
            caregiver_sleep_quality=latest_checkin.caregiver_sleep_hours,
            support_available=latest_checkin.support_available,  # type: ignore[arg-type]
            confidence_to_follow_plan=confidence,
            env_changes=latest_checkin.env_changes,
            free_text=extra_context[:500],
        )
