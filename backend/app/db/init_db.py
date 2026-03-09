from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.db.base import Base, engine
from app.models import StrategyCard
from app.services.retrieval import RetrievalService


def _ensure_schema_updates() -> None:
    inspector = inspect(engine)

    if "daily_checkins" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("daily_checkins")}
        if "details_json" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE daily_checkins ADD COLUMN details_json JSON NOT NULL DEFAULT '{}'"))


def init_db(seed_strategy_cards: bool = True, seed_path: str | None = None) -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_schema_updates()

    if not seed_strategy_cards:
        return

    default_seed = Path(__file__).resolve().parents[2] / "seed" / "strategy_cards.json"
    target_seed = Path(seed_path) if seed_path else default_seed
    if not target_seed.exists():
        return

    with Session(engine) as db:
        existing = db.scalar(select(StrategyCard).limit(1))
        if existing:
            return
        retrieval = RetrievalService(db)
        retrieval.ingest_strategy_cards(target_seed)
        db.commit()
