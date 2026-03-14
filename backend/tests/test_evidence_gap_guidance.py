from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.schemas.domain import CandidateScore, RetrievalEvidenceBundle, RetrievalQueryPlan, RetrievalSelectedSource
from app.services.decision_orchestrator import DecisionOrchestrator


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "guidance-tester", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _bundle_with_gaps() -> RetrievalEvidenceBundle:
    return RetrievalEvidenceBundle(
        selected_card_ids=["CARD-0001"],
        selected_evidence_unit_ids=["EU-1"],
        selected_chunk_ids=["CH-1"],
        candidate_scores=[
            CandidateScore(
                card_id="CARD-0001",
                title="过渡前先预告",
                total_score=0.91,
                semantic_score=0.88,
                lexical_score=0.72,
                scenario_match=0.95,
                profile_fit=0.42,
                historical_effect=0.51,
                execution_cost_bonus=0.2,
                risk_penalty=0.0,
                taboo_conflict_penalty=0.0,
                selected=True,
                why_selected=["过渡场景匹配"],
            )
        ],
        selection_reasons=["命中过渡场景的低刺激策略。"],
        rejected_reasons=["高语言负荷方案被排除。"],
        counter_evidence=[],
        coverage_scores={"scenario": 0.9, "safety": 0.7, "profile": 0.2, "execution": 0.1},
        confidence_score=0.62,
        insufficient_evidence=True,
        missing_dimensions=["profile", "execution"],
        ranking_summary="命中过渡低刺激卡，但画像和执行反馈仍不足。",
        query_plan=RetrievalQueryPlan(
            intent="script",
            scenario="transition",
            intensity="medium",
            family_id=1,
        ),
        selected_sources=[
            RetrievalSelectedSource(
                source_id="card:CARD-0001",
                source_type="strategy_card",
                title="过渡前先预告",
            )
        ],
        feature_attribution=[],
        personalization_applied=[],
        hard_filtered_reasons=[],
        coverage_gaps=["profile", "execution"],
        knowledge_versions=["seed-v1"],
        retrieval_latency_ms=18,
    )


def test_build_evidence_gap_guidance_returns_actionable_structure() -> None:
    guidance = DecisionOrchestrator._build_evidence_gap_guidance(_bundle_with_gaps(), output_kind="script")

    assert guidance.provisional_recommendation
    assert any("孩子画像" in item for item in guidance.uncertain_areas)
    assert any("执行反馈" in item for item in guidance.uncertain_areas)
    assert len(guidance.safe_next_steps) == 3
    assert len(guidance.info_to_collect) >= 2


def test_script_generation_includes_guidance_when_evidence_is_insufficient(
    db_session: Session,
    seeded_family,
    monkeypatch,
) -> None:
    original = DecisionOrchestrator._evidence_stage

    def wrapped(self, *args, **kwargs):
        selected_cards, bundle, ranked_cards = original(self, *args, **kwargs)
        patched_bundle = bundle.model_copy(
            update={
                "insufficient_evidence": True,
                "missing_dimensions": ["profile", "execution"],
                "coverage_scores": {**bundle.coverage_scores, "profile": 0.1, "execution": 0.2},
            }
        )
        return selected_cards, patched_bundle, ranked_cards

    monkeypatch.setattr(DecisionOrchestrator, "_evidence_stage", wrapped)

    with TestClient(app) as client:
        response = client.post(
            "/api/scripts/generate",
            json={
                "family_id": seeded_family.family_id,
                "scenario": "transition",
                "intensity": "medium",
                "free_text": "放学回家后卡在换鞋这一步。",
            },
            headers=_auth_headers(client),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["blocked"] is False
    guidance = body["script"]["evidence_gap_guidance"]
    assert guidance is not None
    assert "可回退" in guidance["recommendation_conditions"][1]
    assert any("执行后" in item for item in guidance["info_to_collect"])
