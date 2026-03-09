from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.signal import SignalAgent


def test_signal_should_trigger_48h(db_session: Session, seeded_family) -> None:
    signal = SignalAgent().evaluate(db=db_session, family_id=seeded_family.family_id)
    assert signal.trigger_48h is True
    assert signal.risk_level in {"yellow", "red"}
