from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.base import Base, engine
from app.db.vector import pgvector_available
from app.models import ChunkEmbedding, EvidenceUnit, KnowledgeChunk, KnowledgeDocument, RetrievalCandidate, RetrievalRun, StrategyCard
from app.services.evidence_units import sync_evidence_units
from app.services.knowledge_corpus import KnowledgeCorpusService
from app.services.rag_providers import EmbeddingProviderRouter


REQUIRED_RAG_TABLES = [
    StrategyCard.__table__,
    KnowledgeDocument.__table__,
    KnowledgeChunk.__table__,
    ChunkEmbedding.__table__,
    EvidenceUnit.__table__,
    RetrievalRun.__table__,
    RetrievalCandidate.__table__,
]


def _ensure_postgres_extensions() -> None:
    if engine.dialect.name != "postgresql" or not pgvector_available():
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _ensure_pgvector_indexes() -> None:
    if engine.dialect.name != "postgresql" or not pgvector_available():
        return
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_strategy_cards_embedding_ivfflat ON strategy_cards USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)",
        "CREATE INDEX IF NOT EXISTS ix_evidence_units_embedding_ivfflat ON evidence_units USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)",
        "CREATE INDEX IF NOT EXISTS ix_chunk_embeddings_vector_ivfflat ON chunk_embeddings USING ivfflat (vector_json vector_cosine_ops) WITH (lists = 100)",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_family_active ON knowledge_chunks (family_id, is_active, source_type)",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


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

    if "decision_traces" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("decision_traces")}
        with engine.begin() as conn:
            if "graph_version" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN graph_version VARCHAR(16) NOT NULL DEFAULT 'v1'"))
            if "stage_order_json" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN stage_order_json JSON NOT NULL DEFAULT '[]'"))
            if "stage_runs_json" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN stage_runs_json JSON NOT NULL DEFAULT '[]'"))
            if "entry_signal_ids_json" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN entry_signal_ids_json JSON NOT NULL DEFAULT '[]'"))
            if "final_reason" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN final_reason TEXT"))
            if "provider_name" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN provider_name VARCHAR(64)"))
            if "embedding_model" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN embedding_model VARCHAR(128)"))
            if "reranker_model" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN reranker_model VARCHAR(128)"))
            if "corpus_version" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN corpus_version VARCHAR(64)"))
            if "retrieval_stage_timings_json" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN retrieval_stage_timings_json JSON NOT NULL DEFAULT '{}'"))
            if "plan_tree_json" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN plan_tree_json JSON NOT NULL DEFAULT '[]'"))
            if "execution_state_json" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN execution_state_json JSON NOT NULL DEFAULT '{}'"))
            if "revision_no" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN revision_no INTEGER"))
            if "parent_trace_id" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN parent_trace_id INTEGER"))
            if "replan_reason" not in existing_columns:
                conn.execute(text("ALTER TABLE decision_traces ADD COLUMN replan_reason TEXT"))


def _ensure_required_tables() -> set[str]:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    missing_tables = [table for table in REQUIRED_RAG_TABLES if table.name not in table_names]
    if missing_tables:
        Base.metadata.create_all(bind=engine, tables=missing_tables)
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
    return table_names


def _table_is_queryable(table_name: str) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text(f'SELECT 1 FROM "{table_name}" LIMIT 1'))
        return True
    except SQLAlchemyError:
        return False


def init_db(seed_strategy_cards: bool = True, seed_path: str | None = None) -> None:
    _ensure_postgres_extensions()
    Base.metadata.create_all(bind=engine)
    Base.metadata.create_all(bind=engine, tables=REQUIRED_RAG_TABLES)
    _ensure_schema_updates()
    _ensure_pgvector_indexes()
    table_names = _ensure_required_tables()

    if not seed_strategy_cards:
        return

    default_seed = Path(__file__).resolve().parents[2] / "seed" / "strategy_cards.json"
    target_seed = Path(seed_path) if seed_path else default_seed
    if not target_seed.exists():
        return

    with Session(engine) as db:
        existing_cards = {
            row.card_id: row
            for row in db.scalars(select(StrategyCard)).all()
        }
        if seed_strategy_cards:
            embedding_router = EmbeddingProviderRouter()
            cards = json.loads(target_seed.read_text(encoding="utf-8"))
            seen_card_ids: set[str] = set()
            for item in cards:
                card_id = str(item.get("id") or "").strip()
                if not card_id or card_id in seen_card_ids:
                    continue
                seen_card_ids.add(card_id)
                title = str(item.get("title") or "").strip()
                steps = [str(step) for step in item.get("steps", []) if str(step).strip()]
                scripts = item.get("scripts", {})
                embedding_source = "\n".join([title, *steps, " ".join(str(value) for value in scripts.values())]).strip()
                model = existing_cards.get(card_id)
                if model is None:
                    model = StrategyCard(card_id=card_id)
                    db.add(model)
                    existing_cards[card_id] = model
                model.title = title
                model.scenario_tags = [str(tag) for tag in item.get("scenario_tags", []) if str(tag).strip()]
                model.conditions_json = item.get("applicable_conditions", {}) or {}
                model.steps_json = steps
                model.scripts_json = scripts if isinstance(scripts, dict) else {}
                model.donts_json = [str(text) for text in item.get("donts", []) if str(text).strip()]
                model.escalate_json = [str(text) for text in item.get("escalate_when", []) if str(text).strip()]
                model.cost_level = str(item.get("cost_level") or "medium")
                model.risk_level = str(item.get("risk_level") or "medium")
                model.evidence_tag = str(item.get("evidence_tag") or "expert")
                model.embedding = embedding_router.embed(embedding_source).vector
            db.flush()

        if "evidence_units" in table_names:
            if not _table_is_queryable("evidence_units"):
                Base.metadata.create_all(bind=engine, tables=[EvidenceUnit.__table__])
            try:
                sync_evidence_units(db)
            except SQLAlchemyError:
                db.rollback()
                Base.metadata.create_all(bind=engine, tables=[EvidenceUnit.__table__])
                sync_evidence_units(db)
        if {"knowledge_documents", "knowledge_chunks", "chunk_embeddings"}.issubset(table_names):
            try:
                KnowledgeCorpusService().sync_strategy_cards(db)
            except SQLAlchemyError:
                db.rollback()
                if seed_strategy_cards:
                    for model in existing_cards.values():
                        db.merge(model)
        db.commit()
