from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.base import SessionLocal
from app.models import ChunkEmbedding, EvidenceUnit, KnowledgeChunk, KnowledgeDocument, MultimodalIngestion, Review, StrategyCard
from app.schemas.domain import KnowledgeIngestionRequest, KnowledgeIngestionResponse, KnowledgeReindexJobRead, KnowledgeReindexResponse
from app.services.rag_providers import EmbeddingProviderRouter


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ContextFrame:
    summary_text: str
    signal_keys: list[str]
    signal_labels: list[str]
    ingestion_ids: list[int]


@dataclass(slots=True)
class ReindexJobState:
    job_id: str
    job_status: str
    corpus_version: str
    processed_chunks: int = 0
    embedding_provider: str = ""
    embedding_model: str = ""
    message: str = ""


class KnowledgeCorpusService:
    _reindex_jobs: dict[str, ReindexJobState] = {}

    def __init__(self) -> None:
        self.embedding_router = EmbeddingProviderRouter()

    def sync_strategy_cards(self, db: Session) -> int:
        bind = db.get_bind()
        if bind is None:
            return 0
        table_names = set(inspect(bind).get_table_names())
        if not {"knowledge_documents", "knowledge_chunks", "chunk_embeddings"}.issubset(table_names):
            return 0
        cards = db.scalars(select(StrategyCard)).all()
        units = db.scalars(select(EvidenceUnit)).all()
        units_by_card: dict[str, list[EvidenceUnit]] = {}
        for unit in units:
            units_by_card.setdefault(unit.card_id, []).append(unit)

        processed = 0
        for card in cards:
            document = db.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.source_type == "strategy_card",
                    KnowledgeDocument.scope == "global",
                    KnowledgeDocument.scope_key == card.card_id,
                )
            )
            body = "\n".join(
                [
                    card.title,
                    " ".join(card.steps_json),
                    " ".join(card.donts_json),
                    " ".join(card.escalate_json),
                    " ".join(str(value) for value in card.scripts_json.values()),
                ]
            ).strip()
            if document is None:
                document = KnowledgeDocument(
                    source_type="strategy_card",
                    title=card.title,
                    body=body,
                    scope="global",
                    scope_key=card.card_id,
                    version=settings.corpus_version,
                    metadata_json={"scenario_tags": card.scenario_tags, "evidence_tag": card.evidence_tag},
                )
                db.add(document)
                db.flush()
            else:
                document.title = card.title
                document.body = body
                document.version = settings.corpus_version
                document.status = "active"
                document.metadata_json = {"scenario_tags": card.scenario_tags, "evidence_tag": card.evidence_tag}

            chunk_specs: list[tuple[str, str, str, dict[str, Any], list[str], str | None]] = [
                (
                    "card_summary",
                    "strategy_card",
                    body,
                    {"title": card.title, "scenario_tags": card.scenario_tags},
                    [*card.scenario_tags, "card"],
                    None,
                )
            ]
            for unit in units_by_card.get(card.card_id, []):
                chunk_specs.append(
                    (
                        unit.unit_kind,
                        "evidence_unit",
                        unit.text,
                        {"dimensions": unit.dimensions_json, **(unit.metadata_json or {})},
                        list(unit.dimensions_json or []),
                        unit.id,
                    )
                )

            existing = {
                (chunk.chunk_type, chunk.evidence_unit_id or ""): chunk
                for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)).all()
            }
            seen_keys: set[tuple[str, str]] = set()
            for chunk_type, source_type, content, metadata, tags, evidence_unit_id in chunk_specs:
                key = (chunk_type, evidence_unit_id or "")
                seen_keys.add(key)
                chunk = existing.get(key)
                if chunk is None:
                    chunk = KnowledgeChunk(
                        document_id=document.id,
                        family_id=None,
                        card_id=card.card_id,
                        evidence_unit_id=evidence_unit_id,
                        chunk_type=chunk_type,
                        source_type=source_type,
                        content=content,
                        metadata_json=metadata,
                        tags_json=tags,
                        family_scope="shared",
                        segment_scope="",
                        knowledge_version=settings.corpus_version,
                        source_confidence=1.0,
                        is_active=True,
                    )
                    db.add(chunk)
                    db.flush()
                chunk.family_id = None
                chunk.chunk_type = chunk_type
                chunk.source_type = source_type
                chunk.content = content
                chunk.metadata_json = metadata
                chunk.tags_json = tags
                chunk.is_active = True
                chunk.source_confidence = 1.0
                self._upsert_embedding(db, chunk)
                processed += 1
            for key, chunk in existing.items():
                if key in seen_keys:
                    continue
                chunk.is_active = False
                for embedding in chunk.embeddings:
                    embedding.active = False
        return processed

    def ingest_manual_knowledge(self, db: Session, payload: KnowledgeIngestionRequest) -> KnowledgeIngestionResponse:
        document = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.family_id == payload.family_id,
                KnowledgeDocument.source_type == payload.source_type,
                KnowledgeDocument.scope == payload.scope,
                KnowledgeDocument.scope_key == payload.scope_key.strip(),
            )
        )
        if document is None:
            document = KnowledgeDocument(
                family_id=payload.family_id,
                source_type=payload.source_type,
                title=payload.title.strip(),
                body=payload.body.strip(),
                scope=payload.scope,
                scope_key=payload.scope_key.strip(),
                version=settings.corpus_version,
                status="active",
                metadata_json=payload.metadata,
            )
            db.add(document)
            db.flush()
        else:
            document.title = payload.title.strip()
            document.body = payload.body.strip()
            document.version = settings.corpus_version
            document.status = "active"
            document.metadata_json = payload.metadata
            for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)).all():
                chunk.is_active = False
                for embedding in chunk.embeddings:
                    embedding.active = False

        chunks: list[KnowledgeChunk] = []
        for index, text in enumerate([line.strip() for line in payload.body.splitlines() if line.strip()] or [payload.body.strip()]):
            chunk = KnowledgeChunk(
                document_id=document.id,
                family_id=payload.family_id,
                chunk_type="manual_note" if index else "document_summary",
                source_type=payload.source_type,
                content=text,
                metadata_json=payload.metadata,
                tags_json=[payload.scope, payload.source_type],
                family_scope="family_only" if payload.scope == "family" else "shared",
                segment_scope=payload.scope_key.strip(),
                knowledge_version=settings.corpus_version,
                source_confidence=0.92,
            )
            db.add(chunk)
            db.flush()
            self._upsert_embedding(db, chunk)
            chunks.append(chunk)
        return KnowledgeIngestionResponse(
            document_id=document.id,
            chunk_ids=[chunk.id for chunk in chunks],
            source_type=document.source_type,
            scope=document.scope,
            version=document.version,
        )

    def reindex(self, db: Session) -> KnowledgeReindexResponse:
        bind = db.get_bind()
        if bind is None:
            return KnowledgeReindexResponse(
                corpus_version=settings.corpus_version,
                processed_chunks=0,
                embedding_provider="hash",
                embedding_model="hash-embedding",
                job_status="completed",
                message="No database bind available for reindex.",
            )
        rows = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.is_active.is_(True))).all()
        provider_name = "hash"
        model_name = "hash-embedding"
        processed = 0
        try:
            db.query(ChunkEmbedding).filter(ChunkEmbedding.active.is_(True)).update({"active": False}, synchronize_session=False)
        except SQLAlchemyError:
            return KnowledgeReindexResponse(
                corpus_version=settings.corpus_version,
                processed_chunks=0,
                embedding_provider=provider_name,
                embedding_model=model_name,
                job_status="failed",
                message="Failed to deactivate previous active embeddings.",
            )
        for row in rows:
            row.knowledge_version = settings.corpus_version
            if row.document is not None:
                row.document.version = settings.corpus_version
                row.document.status = "active"
            response = self._upsert_embedding(db, row, force_new=True)
            provider_name = response.provider
            model_name = response.model
            processed += 1
        return KnowledgeReindexResponse(
            corpus_version=settings.corpus_version,
            processed_chunks=processed,
            embedding_provider=provider_name,
            embedding_model=model_name,
            job_status="completed",
            message="Reindex completed synchronously.",
        )

    def start_reindex_job(self) -> KnowledgeReindexResponse:
        job_id = uuid.uuid4().hex[:12]
        state = ReindexJobState(
            job_id=job_id,
            job_status="accepted",
            corpus_version=settings.corpus_version,
            message="Reindex job accepted.",
        )
        self._reindex_jobs[job_id] = state
        return KnowledgeReindexResponse(
            corpus_version=state.corpus_version,
            processed_chunks=0,
            embedding_provider="",
            embedding_model="",
            job_id=job_id,
            job_status="accepted",
            message=state.message,
        )

    def run_reindex_job(self, job_id: str) -> None:
        state = self._reindex_jobs.get(job_id)
        if state is None:
            return
        state.job_status = "running"
        state.message = "Reindex job is running."
        db = SessionLocal()
        try:
            result = self.reindex(db)
            db.commit()
            state.job_status = result.job_status
            state.processed_chunks = result.processed_chunks
            state.embedding_provider = result.embedding_provider
            state.embedding_model = result.embedding_model
            state.message = result.message
        except Exception as exc:
            db.rollback()
            state.job_status = "failed"
            state.message = str(exc)
        finally:
            db.close()

    def get_reindex_job(self, job_id: str) -> KnowledgeReindexJobRead | None:
        state = self._reindex_jobs.get(job_id)
        if state is None:
            return None
        return KnowledgeReindexJobRead(
            job_id=state.job_id,
            job_status=state.job_status,  # type: ignore[arg-type]
            corpus_version=state.corpus_version,
            processed_chunks=state.processed_chunks,
            embedding_provider=state.embedding_provider,
            embedding_model=state.embedding_model,
            message=state.message,
        )

    def build_context_frame(self, db: Session, ingestion_ids: list[int]) -> ContextFrame:
        if not ingestion_ids:
            return ContextFrame(summary_text="", signal_keys=[], signal_labels=[], ingestion_ids=[])
        rows = [db.get(MultimodalIngestion, ingestion_id) for ingestion_id in ingestion_ids]
        valid_rows = [row for row in rows if row is not None]
        signal_keys: list[str] = []
        signal_labels: list[str] = []
        summaries: list[str] = []
        for row in valid_rows:
            summaries.append(row.normalized_summary)
            for signal in list(row.meta_json.get("signals", []))[:6]:
                key = str(signal.get("signal_key", "")).strip()
                label = str(signal.get("signal_label", "")).strip()
                if key:
                    signal_keys.append(key)
                if label:
                    signal_labels.append(label)
        return ContextFrame(
            summary_text=" ".join(item for item in summaries if item.strip()).strip(),
            signal_keys=signal_keys[:10],
            signal_labels=signal_labels[:10],
            ingestion_ids=[row.id for row in valid_rows],
        )

    def sync_family_memory(self, db: Session, family_id: int) -> int:
        processed = 0
        reviews = db.scalars(select(Review).where(Review.family_id == family_id)).all()
        for review in reviews:
            title = f"复盘 {review.id}"
            body = " ".join(part for part in [review.response_action, review.followup_action, review.notes] if part).strip()
            if not body:
                continue
            payload = KnowledgeIngestionRequest(
                family_id=family_id,
                source_type="review_summary",
                title=title,
                body=body,
                scope="family",
                scope_key=str(review.id),
                metadata={"recommendation": review.recommendation, "outcome_score": review.outcome_score},
            )
            self.ingest_manual_knowledge(db, payload)
            processed += 1
        return processed

    def _upsert_embedding(self, db: Session, chunk: KnowledgeChunk, *, force_new: bool = False):
        response = self.embedding_router.embed(chunk.content)
        if force_new:
            db.query(ChunkEmbedding).filter(
                ChunkEmbedding.chunk_id == chunk.id,
                ChunkEmbedding.provider == response.provider,
                ChunkEmbedding.active.is_(True),
            ).update({"active": False}, synchronize_session=False)
        existing = db.scalar(
            select(ChunkEmbedding).where(
                ChunkEmbedding.chunk_id == chunk.id,
                ChunkEmbedding.provider == response.provider,
                ChunkEmbedding.active.is_(True),
            )
        )
        content_hash = _hash_text(chunk.content)
        if existing is None or force_new:
            existing = ChunkEmbedding(chunk_id=chunk.id, provider=response.provider, model=response.model)
            db.add(existing)
        existing.model = response.model
        existing.dim = len(response.vector)
        existing.vector_json = response.vector
        existing.content_hash = content_hash
        existing.rebuild_version = settings.corpus_version
        existing.active = True
        chunk.knowledge_version = settings.corpus_version
        return response
