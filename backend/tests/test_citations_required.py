from __future__ import annotations

from app.agents.safety import SafetyAgent
from app.schemas.domain import Plan48hResponse, PlanActionItem, PlanMessage, RespiteSlot


def test_missing_citations_should_block() -> None:
    plan = Plan48hResponse(
        today_cut_list=["不做高难度任务"],
        priority_scenarios=["transition"],
        respite_slots=[RespiteSlot(duration_minutes=15, resource="自己独处", handoff_card={"a": "b"})],
        messages=[PlanMessage(target="family", text="请帮我接手15分钟")],
        exit_card_3steps=["降刺激", "给选择", "退场"],
        tomorrow_plan=["重复低刺激流程"],
        action_steps=[
            PlanActionItem(
                card_id="CARD-0001",
                step="先预告",
                script="我们先做第一步",
                donts=["不要强拉", "不要追问"],
                escalate_when=["出现伤害风险"],
            )
        ],
        citations=["CARD-0001"],
        safety_flags=[],
    )
    plan = plan.model_copy(update={"citations": []})

    decision = SafetyAgent().validate_plan(
        plan=plan,
        profile_donts=[],
        explicit_high_risk=False,
        free_text="",
    )

    assert decision.blocked is True
    assert decision.block is not None
    assert "引用" in decision.block.block_reason
