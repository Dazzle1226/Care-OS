from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvidenceUnit, StrategyCard
from app.services.rag_providers import EmbeddingProviderRouter


def _dimensions_for_kind(kind: str) -> list[str]:
    if kind in {"step", "script"}:
        return ["execution"]
    if kind in {"dont", "escalate_when"}:
        return ["safety"]
    return ["profile", "scenario"]


def sync_evidence_units(db: Session) -> int:
    cards = db.scalars(select(StrategyCard)).all()
    embedding_router = EmbeddingProviderRouter()
    inserted = 0
    existing_units = {row.id: row for row in db.scalars(select(EvidenceUnit)).all()}

    for card in cards:
        unit_specs: list[tuple[str, str, str]] = []
        for idx, text in enumerate(card.steps_json):
            unit_specs.append(("step", f"step_{idx}", text))
        for key, text in card.scripts_json.items():
            unit_specs.append(("script", f"script_{key}", text))
        for idx, text in enumerate(card.donts_json):
            unit_specs.append(("dont", f"dont_{idx}", text))
        for idx, text in enumerate(card.escalate_json):
            unit_specs.append(("escalate_when", f"escalate_{idx}", text))

        conditions = card.conditions_json or {}
        for key, values in conditions.items():
            if not values:
                continue
            value_text = ", ".join(str(item) for item in values)
            unit_specs.append(("fit_condition", f"fit_{key}", f"{key}: {value_text}"))

        for unit_kind, unit_key, text in unit_specs:
            unit_id = f"{card.card_id}:{unit_key}"
            model = existing_units.get(unit_id)
            if model is None:
                model = EvidenceUnit(id=unit_id, card_id=card.card_id)
                db.add(model)
                existing_units[unit_id] = model
                inserted += 1
            model.unit_kind = unit_kind
            model.unit_key = unit_key
            model.text = text
            model.dimensions_json = _dimensions_for_kind(unit_kind)
            model.metadata_json = {"title": card.title, "scenario_tags": card.scenario_tags}
            model.embedding = embedding_router.embed(f"{card.title}\n{text}").vector

    return inserted
