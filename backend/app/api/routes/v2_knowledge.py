from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.domain import KnowledgeIngestionRequest, KnowledgeIngestionResponse, KnowledgeReindexJobRead, KnowledgeReindexResponse
from app.services.knowledge_corpus import KnowledgeCorpusService

router = APIRouter(prefix="/v2/knowledge", tags=["v2-knowledge"])


@router.post("/ingestions", response_model=KnowledgeIngestionResponse)
def ingest_knowledge(
    payload: KnowledgeIngestionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> KnowledgeIngestionResponse:
    response = KnowledgeCorpusService().ingest_manual_knowledge(db=db, payload=payload)
    db.commit()
    return response


@router.post("/reindex", response_model=KnowledgeReindexResponse)
def reindex_knowledge(
    background_tasks: BackgroundTasks,
    async_mode: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> KnowledgeReindexResponse:
    service = KnowledgeCorpusService()
    if async_mode:
        response = service.start_reindex_job()
        if response.job_id is not None:
            background_tasks.add_task(service.run_reindex_job, response.job_id)
        return response
    response = service.reindex(db=db)
    db.commit()
    return response


@router.get("/reindex/{job_id}", response_model=KnowledgeReindexJobRead)
def get_reindex_job(
    job_id: str,
    _: User = Depends(get_current_user),
) -> KnowledgeReindexJobRead:
    response = KnowledgeCorpusService().get_reindex_job(job_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Reindex job not found")
    return response
