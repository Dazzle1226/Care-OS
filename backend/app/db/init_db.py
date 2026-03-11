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

    if "reviews" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("reviews")}
        with engine.begin() as conn:
            if "child_state_after" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE reviews ADD COLUMN child_state_after "
                        "VARCHAR(32) NOT NULL DEFAULT 'partly_settled'"
                    )
                )
            if "caregiver_state_after" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE reviews ADD COLUMN caregiver_state_after "
                        "VARCHAR(32) NOT NULL DEFAULT 'same'"
                    )
                )
            if "recommendation" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE reviews ADD COLUMN recommendation "
                        "VARCHAR(16) NOT NULL DEFAULT 'continue'"
                    )
                )
            if "response_action" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE reviews ADD COLUMN response_action "
                        "TEXT NOT NULL DEFAULT ''"
                    )
                )

    if "training_task_feedbacks" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("training_task_feedbacks")}
        with engine.begin() as conn:
            if "task_instance_id" not in existing_columns:
                conn.execute(text("ALTER TABLE training_task_feedbacks ADD COLUMN task_instance_id INTEGER"))
            if "helpfulness" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE training_task_feedbacks ADD COLUMN helpfulness "
                        "VARCHAR(16) NOT NULL DEFAULT 'neutral'"
                    )
                )
            if "obstacle_tag" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE training_task_feedbacks ADD COLUMN obstacle_tag "
                        "VARCHAR(32) NOT NULL DEFAULT 'none'"
                    )
                )
            if "safety_pause" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE training_task_feedbacks ADD COLUMN safety_pause "
                        "BOOLEAN NOT NULL DEFAULT 0"
                    )
                )


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
