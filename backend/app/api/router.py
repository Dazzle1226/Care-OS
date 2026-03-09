from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import auth, checkin, family, onboarding, plan, profile, report, respite, review, scripts, supportcard, training

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(onboarding.router)
api_router.include_router(family.router)
api_router.include_router(profile.router)
api_router.include_router(checkin.router)
api_router.include_router(plan.router)
api_router.include_router(respite.router)
api_router.include_router(scripts.router)
api_router.include_router(review.router)
api_router.include_router(report.router)
api_router.include_router(supportcard.router)
api_router.include_router(training.router)
