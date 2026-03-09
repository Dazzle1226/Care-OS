from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.plan import PlanAgent


def test_plan_agent_fallback_without_llm(db_session: Session, seeded_family) -> None:
    script = PlanAgent().generate_script(
        db=db_session,
        family=seeded_family,
        scenario="transition",
        intensity="medium",
        free_text="",
    )

    assert len(script.steps) == 3
    assert len(script.citations) >= 1
