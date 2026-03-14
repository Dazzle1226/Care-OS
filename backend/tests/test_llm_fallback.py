from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.plan import PlanAgent
from app.services.retrieval import RetrievalService


def test_plan_agent_fallback_without_llm(db_session: Session, seeded_family) -> None:
    agent = PlanAgent()
    script, fallback_reason = agent.generate_script_with_meta(
        db=db_session,
        family=seeded_family,
        scenario="transition",
        intensity="medium",
        free_text="",
    )

    assert len(script.steps) == 3
    assert len(script.citations) >= 1
    assert fallback_reason is not None
    assert "rule_fallback" in fallback_reason or "openai_compatible" in fallback_reason


def test_plan_agent_accepts_modelscope_script_shape(db_session: Session, seeded_family) -> None:
    agent = PlanAgent()
    agent.llm = type(
        "StubLLM",
        (),
        {
            "generate_json": staticmethod(
                lambda **_: {
                    "scenario": "transition",
                    "intensity": "medium",
                    "steps": ["先提前预告", "再给两个选择", "完成后马上强化"],
                    "scripts": {"parent": "我看到你现在有点难，我们先做第一步。"},
                    "donts": ["不要强拉身体", "不要连续追问"],
                    "escalate_when": ["持续升级超过10分钟", "出现明显自伤/他伤风险"],
                    "citations": ["CARD-0012", "CARD-0006"],
                }
            )
        },
    )()

    cards = RetrievalService(db_session).compose_plan_cards(
        family_id=seeded_family.family_id,
        scenario="transition",
        intensity="medium",
        profile=seeded_family.child_profile,
        extra_context="过渡 等待",
        max_cards=2,
    )
    script, fallback_reason = agent.generate_script_with_meta(
        db=db_session,
        family=seeded_family,
        scenario="transition",
        intensity="medium",
        free_text="今天校车改点，需要非常短句。",
        cards=cards,
    )

    assert fallback_reason is None
    assert script.script_line.startswith("[transition/medium]")
    assert script.exit_plan == ["持续升级超过10分钟", "出现明显自伤/他伤风险"]
