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

    def _fallback_reason(self, exc: Exception) -> str:
        attempts = getattr(self.llm, "last_attempts", None) or []
        if not attempts:
            return str(exc)
        summary = " | ".join(
            f"{item.get('provider', 'unknown')}:{item.get('status', 'failed')}"
            + (f"({item.get('reason')})" if item.get("reason") else "")
            for item in attempts
        )
        return summary

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

    @staticmethod
    def _list_of_strings(value: object, *, minimum: int = 0) -> list[str]:
        if not isinstance(value, list):
            return []
        items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return items if len(items) >= minimum else []

    def _normalize_llm_script(self, raw: dict, cards: list, scenario: str, intensity: str) -> dict:
        normalized = dict(raw)

        if not normalized.get("script_line"):
            scripts = normalized.get("scripts")
            if isinstance(scripts, dict):
                parent_line = scripts.get("parent")
                if isinstance(parent_line, str) and parent_line.strip():
                    normalized["script_line"] = f"[{scenario}/{intensity}] {parent_line.strip()}"

        exit_plan = self._list_of_strings(normalized.get("exit_plan"), minimum=1)
        if not exit_plan:
            exit_plan = self._list_of_strings(normalized.get("escalate_when"), minimum=1)
        if exit_plan:
            normalized["exit_plan"] = exit_plan[:3]

        steps = self._list_of_strings(normalized.get("steps"), minimum=3)
        if steps:
            normalized["steps"] = steps[:3]

        donts = self._list_of_strings(normalized.get("donts"), minimum=2)
        if donts:
            normalized["donts"] = donts[:3]

        citations = self._list_of_strings(normalized.get("citations"), minimum=1)
        if not citations:
            citations = [card.card_id for card in cards]
        normalized["citations"] = citations

        # Drop common extra keys returned by some providers before pydantic validation.
        for key in ["scenario", "intensity", "free_text", "scripts", "escalate_when"]:
            normalized.pop(key, None)
        return normalized

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
        normalized = self._normalize_llm_script(raw=raw, cards=cards, scenario=scenario, intensity=intensity)
        return ScriptResponse.model_validate(normalized)

    def generate_48h_plan_with_meta(
        self,
        db: Session,
        family: Family,
        signal: SignalOutput,
        context: PlanContext,
        cards: list | None = None,
    ) -> tuple[Plan48hResponse, str | None]:
        retrieval = RetrievalService(db)
        profile = family.child_profile
        scenarios = self._scenario_candidates(profile, context.scenario)

        selected_cards = cards or retrieval.compose_plan_cards(
            family_id=family.family_id,
            scenario=scenarios[0],
            intensity=context.intensity,
            profile=profile,
            extra_context=context.free_text,
            max_cards=3,
        )

        if not selected_cards:
            raise ValueError("No strategy cards available")

        try:
            return self._attempt_llm_plan(signal, scenarios, selected_cards, context, profile), None
        except (LLMUnavailableError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return (
                build_fallback_plan(
                    risk_level=signal.risk_level,
                    scenarios=scenarios,
                    cards=selected_cards,
                    support_hint=context.support_hint,
                ),
                self._fallback_reason(exc),
            )

    def generate_48h_plan(self, db: Session, family: Family, signal: SignalOutput, context: PlanContext) -> Plan48hResponse:
        plan, _ = self.generate_48h_plan_with_meta(db=db, family=family, signal=signal, context=context)
        return plan

    def generate_script_with_meta(
        self,
        db: Session,
        family: Family,
        scenario: str,
        intensity: str,
        free_text: str,
        cards: list | None = None,
    ) -> tuple[ScriptResponse, str | None]:
        retrieval = RetrievalService(db)
        profile = family.child_profile

        selected_cards = cards or retrieval.compose_plan_cards(
            family_id=family.family_id,
            scenario=scenario,
            intensity=intensity,
            profile=profile,
            extra_context=free_text,
            max_cards=3,
        )

        if not selected_cards:
            raise ValueError("No strategy cards available")

        try:
            return self._attempt_llm_script(scenario, intensity, selected_cards, free_text), None
        except (LLMUnavailableError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return build_fallback_script(cards=selected_cards, scenario=scenario, intensity=intensity), self._fallback_reason(exc)

    def generate_script(
        self,
        db: Session,
        family: Family,
        scenario: str,
        intensity: str,
        free_text: str,
    ) -> ScriptResponse:
        script, _ = self.generate_script_with_meta(
            db=db,
            family=family,
            scenario=scenario,
            intensity=intensity,
            free_text=free_text,
        )
        return script
