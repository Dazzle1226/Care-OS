from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import User, WeeklyReport
from app.schemas.domain import (
    ExportRequest,
    ExportResponse,
    MonthlyReportResponse,
    ReportFeedbackCreate,
    ReportFeedbackResponse,
    WeeklyReportResponse,
)
from app.services.reporting import (
    compute_monthly_report,
    compute_weekly_report,
    normalize_week_start,
    save_report_feedback,
)

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/weekly/{family_id}", response_model=WeeklyReportResponse)
def get_weekly_report(
    family_id: int,
    week_start: date,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> WeeklyReportResponse:
    report = compute_weekly_report(db, family_id, week_start)
    db.commit()
    return report


@router.get("/monthly/{family_id}", response_model=MonthlyReportResponse)
def get_monthly_report(
    family_id: int,
    month_start: date,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MonthlyReportResponse:
    report = compute_monthly_report(db, family_id, month_start)
    db.commit()
    return report


@router.post("/feedback", response_model=ReportFeedbackResponse)
def submit_report_feedback(
    payload: ReportFeedbackCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ReportFeedbackResponse:
    response = save_report_feedback(db, payload)
    db.commit()
    return response


@router.post("/export", response_model=ExportResponse)
def export_weekly_report(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ExportResponse:
    week_start = normalize_week_start(payload.week_start)
    row = db.scalar(
        select(WeeklyReport).where(WeeklyReport.family_id == payload.family_id, WeeklyReport.week_start == week_start)
    )
    if row is None:
        compute_weekly_report(db, payload.family_id, week_start)
        row = db.scalar(
            select(WeeklyReport).where(WeeklyReport.family_id == payload.family_id, WeeklyReport.week_start == week_start)
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Weekly report not found")

    row.export_count += 1
    db.commit()

    return ExportResponse(
        ok=True,
        export_count=row.export_count,
        artifact=f"support://weekly/{payload.family_id}/{week_start.isoformat()}.pdf",
    )
