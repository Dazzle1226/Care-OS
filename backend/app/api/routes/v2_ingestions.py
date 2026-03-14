from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.domain import MultimodalIngestionRequest, MultimodalIngestionResponse
from app.services.multimodal_file_parser import MultimodalExtractionError, MultimodalFileParser
from app.services.multimodal_ingestion import MultimodalIngestionService

router = APIRouter(prefix="/v2/ingestions", tags=["v2-ingestions"])


@router.post("/document", response_model=MultimodalIngestionResponse)
def ingest_document(
    payload: MultimodalIngestionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MultimodalIngestionResponse:
    if payload.source_type != "document":
        raise HTTPException(status_code=400, detail="source_type must be document")
    response = MultimodalIngestionService().ingest(db=db, payload=payload)
    db.commit()
    return response


@router.post("/audio", response_model=MultimodalIngestionResponse)
def ingest_audio(
    payload: MultimodalIngestionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MultimodalIngestionResponse:
    if payload.source_type != "audio":
        raise HTTPException(status_code=400, detail="source_type must be audio")
    response = MultimodalIngestionService().ingest(db=db, payload=payload)
    db.commit()
    return response


@router.post("/document-file", response_model=MultimodalIngestionResponse)
async def ingest_document_file(
    family_id: int = Form(...),
    content_name: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MultimodalIngestionResponse:
    payload = await file.read()
    try:
        extracted = MultimodalFileParser().extract_document(
            family_id=family_id,
            filename=file.filename or "upload-document",
            content_type=file.content_type,
            payload=payload,
            content_name=content_name,
        )
    except MultimodalExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    response = MultimodalIngestionService().ingest_extracted(db=db, extracted=extracted)
    db.commit()
    return response


@router.post("/audio-file", response_model=MultimodalIngestionResponse)
async def ingest_audio_file(
    family_id: int = Form(...),
    content_name: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MultimodalIngestionResponse:
    payload = await file.read()
    try:
        extracted = MultimodalFileParser().extract_audio(
            family_id=family_id,
            filename=file.filename or "upload-audio",
            content_type=file.content_type,
            payload=payload,
            content_name=content_name,
        )
    except MultimodalExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    response = MultimodalIngestionService().ingest_extracted(db=db, extracted=extracted)
    db.commit()
    return response


@router.get("/{ingestion_id}", response_model=MultimodalIngestionResponse)
def get_ingestion(
    ingestion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MultimodalIngestionResponse:
    response = MultimodalIngestionService().get(db=db, ingestion_id=ingestion_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Ingestion not found")
    return response
