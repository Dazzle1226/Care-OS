from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.domain import BenchmarkRunRead
from app.services.benchmarking import BenchmarkService

router = APIRouter(prefix="/v2/benchmarks", tags=["v2-benchmarks"])


@router.get("/latest", response_model=BenchmarkRunRead)
def get_latest_benchmark(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BenchmarkRunRead:
    response = BenchmarkService().ensure_latest(db=db)
    db.commit()
    return response


@router.get("/{run_id}", response_model=BenchmarkRunRead)
def get_benchmark(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BenchmarkRunRead:
    response = BenchmarkService().get(db=db, run_id=run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return response


@router.post("/retrieval", response_model=BenchmarkRunRead)
def run_retrieval_benchmark(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BenchmarkRunRead:
    run = BenchmarkService().run(db=db)
    db.commit()
    return BenchmarkService().get(db=db, run_id=run.id)  # type: ignore[return-value]
