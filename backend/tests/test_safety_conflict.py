from __future__ import annotations

from app.agents.safety import SafetyAgent
from app.schemas.domain import ScriptResponse


def test_dont_conflict_should_block() -> None:
    script = ScriptResponse(
        steps=["先抱住孩子", "强行带离现场", "继续追问为什么"],
        script_line="我现在要抱住你，马上停下来。",
        donts=["不要强拉", "不要大声"],
        exit_plan=["升级则联系支持者"],
        citations=["CARD-0001"],
    )

    decision = SafetyAgent().validate_script(
        script=script,
        profile_donts=["不可触碰"],
        explicit_high_risk=False,
        free_text="",
    )

    assert decision.blocked is True
    assert decision.block is not None
    assert "冲突" in decision.block.block_reason
    assert decision.block.severity == "conflict"
    assert decision.block.conflict_explanation
    assert len(decision.block.alternatives) >= 1
