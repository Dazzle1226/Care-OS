from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, select, text

from app.db.base import SessionLocal, engine
from app.db.init_db import init_db
from app.models import EvidenceUnit


def test_init_db_recovers_missing_evidence_units_table() -> None:
    seed_path = Path(__file__).resolve().parents[1] / "seed" / "strategy_cards.json"

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS chunk_embeddings"))
        conn.execute(text("DROP TABLE IF EXISTS knowledge_chunks"))
        conn.execute(text("DROP TABLE IF EXISTS evidence_selection_logs"))
        conn.execute(text("DROP TABLE IF EXISTS evidence_units"))

    init_db(seed_strategy_cards=True, seed_path=str(seed_path))

    inspector = inspect(engine)
    assert "evidence_units" in inspector.get_table_names()

    with SessionLocal() as db:
        evidence_units = db.scalars(select(EvidenceUnit)).all()

    assert evidence_units
