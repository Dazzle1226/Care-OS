from __future__ import annotations

from app.agents.safety import SafetyAgent


def test_high_risk_keyword_should_block() -> None:
    decision = SafetyAgent().should_block_high_risk(
        explicit_flag=False,
        texts=["孩子出现自伤倾向，需要立即处理"],
    )

    assert decision.blocked is True
    assert decision.block is not None
    assert "高风险" in decision.block.block_reason
