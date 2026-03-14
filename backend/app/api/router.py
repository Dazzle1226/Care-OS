from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    auth,
    checkin,
    decision_trace,
    family,
    onboarding,
    plan,
    profile,
    report,
    respite,
    review,
    scripts,
    supportcard,
    training,
    v2_benchmarks,
    v2_generation,
    v2_ingestions,
    v2_knowledge,
    v2_policy_memory,
    v2_retrieval,
    v3_friction_sessions,
    v3_training_sessions,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(onboarding.router)
api_router.include_router(family.router)
api_router.include_router(profile.router)
api_router.include_router(checkin.router)
api_router.include_router(decision_trace.router)
api_router.include_router(plan.router)
api_router.include_router(respite.router)
api_router.include_router(scripts.router)
api_router.include_router(review.router)
api_router.include_router(report.router)
api_router.include_router(supportcard.router)
api_router.include_router(training.router)
api_router.include_router(v2_generation.router)
api_router.include_router(v2_ingestions.router)
api_router.include_router(v2_knowledge.router)
api_router.include_router(v2_policy_memory.router)
api_router.include_router(v2_benchmarks.router)
api_router.include_router(v2_retrieval.router)
api_router.include_router(v3_friction_sessions.router)
api_router.include_router(v3_training_sessions.router)
