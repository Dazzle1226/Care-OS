from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import ChildProfile, Family
from app.schemas.domain import Plan48hResponse, ScriptResponse, SignalOutput
from app.services.llm_client import LLMClient, LLMUnavailableError
from app.services.retrieval import RetrievalService
from app.services.rule_fallback import build_fallback_plan, build_fallback_script


@dataclass(slots=True)
class PlanContext:
    family_id: int
    scenario: str | None
    intensity: str
    support_hint: str
    free_text: str


class PlanAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _scenario_candidates(self, profile: ChildProfile | None, scenario: str | None) -> list[str]:
        scenarios: list[str] = []
        if scenario:
            scenarios.append(scenario)
        if profile and profile.high_friction_scenarios:
            scenarios.extend(profile.high_friction_scenarios)
        if not scenarios:
            scenarios = ["transition", "bedtime"]
        # keep order and uniqueness
        return list(dict.fromkeys(scenarios))

    def _attempt_llm_plan(
        self,
        signal: SignalOutput,
        scenarios: list[str],
        cards: list,
        context: PlanContext,
        profile: ChildProfile | None,
    ) -> Plan48hResponse:
        card_bundle = [
            {
                "card_id": c.card_id,
                "title": c.title,
                "steps": c.steps_json,
                "scripts": c.scripts_json,
                "donts": c.donts_json,
                "escalate_when": c.escalate_json,
            }
            for c in cards
        ]

        system_prompt = "你是 ASD 家庭照护计划助手。只输出 JSON，不要解释。所有字段都必须是短句，不能写段落。"
        user_prompt = json.dumps(
            {
                "task": "生成48小时降负荷计划",
                "risk_level": signal.risk_level,
                "reasons": signal.reasons,
                "scenarios": scenarios,
                "support_hint": context.support_hint,
                "free_text": context.free_text,
                "profile": {
                    "age_band": getattr(profile, "age_band", None),
                    "language_level": getattr(profile, "language_level", None),
                    "sensory_flags": getattr(profile, "sensory_flags", []),
                    "donts": getattr(profile, "donts", []),
                },
                "cards": card_bundle,
                "constraints": {
                    "today_cut_list_max": 3,
                    "priority_scenarios_max": 2,
                    "exit_card_steps": 3,
                    "citations_required": True,
                    "each_item_brief": True,
                },
            },
            ensure_ascii=False,
        )

        raw = self.llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        if "citations" not in raw or not raw["citations"]:
            raw["citations"] = [card.card_id for card in cards]
        return Plan48hResponse.model_validate(raw)

    def _attempt_llm_script(
        self,
        scenario: str,
        intensity: str,
        cards: list,
        free_text: str,
    ) -> ScriptResponse:
        system_prompt = "你是 ASD 场景脚本助手。只输出 JSON，不要解释。所有步骤、禁忌和退场都要短句，避免段落。"
        user_prompt = json.dumps(
            {
                "task": "生成场景脚本",
                "scenario": scenario,
                "intensity": intensity,
                "free_text": free_text,
                "cards": [
                    {
                        "card_id": c.card_id,
                        "steps": c.steps_json,
                        "scripts": c.scripts_json,
                        "donts": c.donts_json,
                        "escalate_when": c.escalate_json,
                    }
                    for c in cards
                ],
                "constraints": {
                    "steps_exact": 3,
                    "donts_min": 2,
                    "citations_required": True,
                    "short_read_aloud_line": True,
                },
            },
            ensure_ascii=False,
        )

        raw = self.llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        if "citations" not in raw or not raw["citations"]:
            raw["citations"] = [card.card_id for card in cards]
        return ScriptResponse.model_validate(raw)

    def generate_48h_plan(self, db: Session, family: Family, signal: SignalOutput, context: PlanContext) -> Plan48hResponse:
        retrieval = RetrievalService(db)
        profile = family.child_profile
        scenarios = self._scenario_candidates(profile, context.scenario)

        cards = retrieval.compose_plan_cards(
            family_id=family.family_id,
            scenario=scenarios[0],
            intensity=context.intensity,
            profile=profile,
            extra_context=context.free_text,
            max_cards=3,
        )

        if not cards:
            raise ValueError("No strategy cards available")

        try:
            return self._attempt_llm_plan(signal, scenarios, cards, context, profile)
        except (LLMUnavailableError, ValueError, TypeError, json.JSONDecodeError):
            return build_fallback_plan(
                risk_level=signal.risk_level,
                scenarios=scenarios,
                cards=cards,
                support_hint=context.support_hint,
            )

    def generate_script(
        self,
        db: Session,
        family: Family,
        scenario: str,
        intensity: str,
        free_text: str,
    ) -> ScriptResponse:
        retrieval = RetrievalService(db)
        profile = family.child_profile

        cards = retrieval.compose_plan_cards(
            family_id=family.family_id,
            scenario=scenario,
            intensity=intensity,
            profile=profile,
            extra_context=free_text,
            max_cards=3,
        )

        if not cards:
            raise ValueError("No strategy cards available")

        try:
            return self._attempt_llm_script(scenario, intensity, cards, free_text)
        except (LLMUnavailableError, ValueError, TypeError, json.JSONDecodeError):
            return build_fallback_script(cards=cards, scenario=scenario, intensity=intensity)
