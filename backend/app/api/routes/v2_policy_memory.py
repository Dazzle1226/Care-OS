from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.domain import PolicyMemoryDiffRead, PolicyMemorySnapshotRead
from app.services.policy_learning import PolicyLearningService

router = APIRouter(prefix="/v2/policy-memory", tags=["v2-policy-memory"])


@router.get("/{family_id}", response_model=PolicyMemorySnapshotRead)
def get_policy_memory(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PolicyMemorySnapshotRead:
    return PolicyLearningService().build_snapshot(db=db, family_id=family_id)


@router.get("/{family_id}/diff", response_model=PolicyMemoryDiffRead)
def get_policy_memory_diff(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PolicyMemoryDiffRead:
    return PolicyLearningService().build_diff(db=db, family_id=family_id)
