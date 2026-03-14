from __future__ import annotations

from app.agents.emotion import EmotionAgent
from app.schemas.domain import V3FrictionSessionStartRequest


def test_emotion_agent_detects_high_overload_and_confidence_drift() -> None:
    payload = V3FrictionSessionStartRequest(
        family_id=1,
        scenario="transition",
        child_state="meltdown",
        sensory_overload_level="heavy",
        transition_difficulty=9,
        meltdown_count=3,
        caregiver_stress=9,
        caregiver_fatigue=8,
        caregiver_sleep_quality=3,
        support_available="one",
        confidence_to_follow_plan=2,
        free_text="现场太吵，我真的撑不住了，他一直尖叫不要走。",
    )

    assessment = EmotionAgent().assess(
        payload=payload,
        fused_text="学校临时调整，刚回家就开始哭闹。",
        historical_patterns=["handoff_pattern:先由配偶接手"],
    )

    assert assessment.child_emotion == "meltdown_risk"
    assert assessment.caregiver_emotion == "overloaded"
    assert assessment.child_overload_level == "high"
    assert assessment.caregiver_overload_level == "high"
    assert assessment.confidence_drift == "critical"
    assert "压缩成一步" in " ".join(assessment.recommended_adjustments)
