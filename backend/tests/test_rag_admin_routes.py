from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import ChunkEmbedding, KnowledgeChunk


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "rag-admin", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_knowledge_ingestion_and_retrieval_trace_routes(db_session: Session, seeded_family) -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)

        ingestion_response = client.post(
            "/api/v2/knowledge/ingestions",
            json={
                "family_id": seeded_family.family_id,
                "source_type": "review_summary",
                "title": "晚饭复盘",
                "body": "今天晚饭前等待时更容易升级，提前预告后明显更稳。",
                "scope": "family",
                "scope_key": "dinner-review",
                "metadata": {"tag": "meal"},
            },
            headers=headers,
        )
        assert ingestion_response.status_code == 200
        ingestion_body = ingestion_response.json()
        assert ingestion_body["document_id"] is not None
        assert ingestion_body["chunk_ids"]

        ingestion_update = client.post(
            "/api/v2/knowledge/ingestions",
            json={
                "family_id": seeded_family.family_id,
                "source_type": "review_summary",
                "title": "晚饭复盘（更新）",
                "body": "今天晚饭前等待时更容易升级，提前预告和倒计时后明显更稳。",
                "scope": "family",
                "scope_key": "dinner-review",
                "metadata": {"tag": "meal", "version": "updated"},
            },
            headers=headers,
        )
        assert ingestion_update.status_code == 200
        assert ingestion_update.json()["document_id"] == ingestion_body["document_id"]

        db_session.expire_all()
        active_chunks = db_session.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == ingestion_body["document_id"],
            KnowledgeChunk.is_active.is_(True),
        ).all()
        inactive_chunks = db_session.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == ingestion_body["document_id"],
            KnowledgeChunk.is_active.is_(False),
        ).all()
        assert active_chunks
        assert inactive_chunks

        reindex_response = client.post("/api/v2/knowledge/reindex?async_mode=false", headers=headers)
        assert reindex_response.status_code == 200
        reindex_body = reindex_response.json()
        assert reindex_body["processed_chunks"] >= len(active_chunks)
        assert reindex_body["job_status"] == "completed"

        async_reindex = client.post("/api/v2/knowledge/reindex", headers=headers)
        assert async_reindex.status_code == 200
        async_body = async_reindex.json()
        assert async_body["job_status"] == "accepted"
        assert async_body["job_id"]

        job_response = client.get(f"/api/v2/knowledge/reindex/{async_body['job_id']}", headers=headers)
        assert job_response.status_code == 200
        assert job_response.json()["job_status"] in {"running", "completed"}

        db_session.expire_all()
        active_chunk_ids = [chunk.id for chunk in active_chunks]
        active_embeddings = db_session.query(ChunkEmbedding).filter(
            ChunkEmbedding.chunk_id.in_(active_chunk_ids),
            ChunkEmbedding.active.is_(True),
        ).all()
        assert len(active_embeddings) == len(active_chunk_ids)

        generation_response = client.post(
            "/api/v2/scripts/generate",
            json={
                "family_id": seeded_family.family_id,
                "scenario": "transition",
                "intensity": "medium",
                "resources": {},
                "high_risk_selected": False,
                "free_text": "今天校车改点，孩子比较紧张。",
                "ingestion_ids": [],
            },
            headers=headers,
        )
        assert generation_response.status_code == 200
        body = generation_response.json()
        assert body["evidence_bundle"]["query_plan"]["intent"] == "script"

        trace_response = client.get(f"/api/v2/retrieval/traces/{body['trace_id']}", headers=headers)
        assert trace_response.status_code == 200
        trace_body = trace_response.json()
        assert trace_body["trace"]["retrieval_bundle"]["selected_sources"]
        assert "retrieval_latency_ms" in trace_body["trace"]["retrieval_stage_timings"]
        assert trace_body["candidates"]
        assert any(item["source_type"] != "strategy_card" for item in trace_body["candidates"])
