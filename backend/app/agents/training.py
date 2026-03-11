from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Family
from app.schemas.domain import TrainingDashboardResponse, TrainingDomainDetailResponse
from app.services.training_system import TrainingSystemService


class TrainingAgent:
    def __init__(self) -> None:
        self.service = TrainingSystemService()

    def generate_plan(self, db: Session, family: Family, extra_context: str = "", force_regenerate: bool = False) -> TrainingDashboardResponse:
        return self.service.get_dashboard(
            db=db,
            family=family,
            extra_context=extra_context,
            force_regenerate=force_regenerate,
        )

    def get_domain_detail(self, db: Session, family: Family, area_key: str) -> TrainingDomainDetailResponse:
        return self.service.get_domain_detail(db=db, family=family, area_key=area_key)
