from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Review, StrategyCard
from app.schemas.domain import StrategyCardSeed


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^\w\u4e00-\u9fa5]+", text.lower()) if t]


def hash_embedding(text: str, dim: int = 256) -> list[float]:
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec

    for tok in tokens:
        idx = abs(hash(tok)) % dim
        sign = 1.0 if (hash(tok + "_sign") % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(length))


class RetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _openai_embedding(self, text: str) -> list[float] | None:
        if not settings.openai_api_key:
            return None

        payload = {
            "model": settings.openai_embedding_model,
            "input": text,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{settings.openai_base_url.rstrip('/')}/embeddings",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            vector: list[float] = body["data"][0]["embedding"]
            return vector[: settings.embedding_dim]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
            return None

    def embed_text(self, text: str) -> list[float]:
        provider = settings.embedding_provider.lower()
        if provider == "openai" or (provider == "auto" and settings.openai_api_key):
            vec = self._openai_embedding(text)
            if vec is not None:
                return vec
        return hash_embedding(text, dim=settings.embedding_dim)

    @staticmethod
    def _card_text(card: StrategyCardSeed) -> str:
        fields = [
            card.title,
            " ".join(card.scenario_tags),
            " ".join(card.steps),
            " ".join(card.donts),
            " ".join(card.escalate_when),
            " ".join(card.scripts.values()),
        ]
        return "\n".join(fields)

    def ingest_strategy_cards(self, seed_path: str | Path) -> int:
        path = Path(seed_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        inserted = 0

        for row in data:
            seed = StrategyCardSeed.model_validate(row)
            embedding = self.embed_text(self._card_text(seed))

            model = self.db.get(StrategyCard, seed.id)
            if model is None:
                model = StrategyCard(card_id=seed.id)
                self.db.add(model)
                inserted += 1

            model.title = seed.title
            model.scenario_tags = seed.scenario_tags
            model.conditions_json = seed.applicable_conditions
            model.steps_json = seed.steps
            model.scripts_json = seed.scripts
            model.donts_json = seed.donts
            model.escalate_json = seed.escalate_when
            model.cost_level = seed.cost_level
            model.risk_level = seed.risk_level
            model.evidence_tag = seed.evidence_tag
            model.embedding = embedding

        return inserted

    def _history_effect_map(self, family_id: int) -> dict[str, float]:
        rows = self.db.scalars(select(Review).where(Review.family_id == family_id)).all()
        grouped: dict[str, list[int]] = defaultdict(list)
        for review in rows:
            for card_id in review.card_ids:
                grouped[card_id].append(review.outcome_score)

        result: dict[str, float] = {}
        for card_id, scores in grouped.items():
            if not scores:
                result[card_id] = 0.0
                continue
            # normalize -2..2 -> -1..1
            result[card_id] = sum(scores) / len(scores) / 2.0
        return result

    @staticmethod
    def _risk_penalty(level: str) -> float:
        return {"low": 0.1, "medium": 0.5, "high": 1.0}.get(level, 0.5)

    @staticmethod
    def _cost_bonus(level: str) -> float:
        return {"low": 1.0, "medium": 0.5, "high": 0.0}.get(level, 0.2)

    @staticmethod
    def _scenario_match(card: StrategyCard, scenario: str) -> float:
        if not scenario:
            return 0.4
        tags = set(card.scenario_tags)
        if scenario in tags:
            return 1.0
        if scenario in {"transition", "outing"} and any(t in tags for t in ["sensory", "transition", "outing"]):
            return 0.7
        return 0.2

    @staticmethod
    def _profile_pass(card: StrategyCard, profile: Any | None) -> bool:
        if profile is None:
            return True
        cond = card.conditions_json or {}
        age_bands = cond.get("age_bands") or []
        lang_levels = cond.get("language_levels") or []
        if age_bands and profile.age_band not in age_bands:
            return False
        if lang_levels and profile.language_level not in lang_levels:
            return False
        return True

    def retrieve_cards(
        self,
        family_id: int,
        scenario: str,
        intensity: str,
        profile: Any | None = None,
        extra_context: str = "",
        top_k: int = 12,
    ) -> list[StrategyCard]:
        cards = self.db.scalars(select(StrategyCard)).all()
        if not cards:
            return []

        filtered = [card for card in cards if self._profile_pass(card, profile)]
        if not filtered:
            filtered = cards

        query_text = f"{scenario} {intensity} {extra_context}".strip()
        query_vec = self.embed_text(query_text)
        history = self._history_effect_map(family_id)

        scored: list[tuple[float, StrategyCard]] = []
        for card in filtered:
            sim = cosine_similarity(query_vec, card.embedding)
            history_effect = history.get(card.card_id, 0.0)
            scenario_match = self._scenario_match(card, scenario)
            low_cost_bonus = self._cost_bonus(card.cost_level)
            risk_penalty = self._risk_penalty(card.risk_level)

            score = (
                0.5 * sim
                + 0.2 * history_effect
                + 0.15 * scenario_match
                + 0.1 * low_cost_bonus
                - 0.25 * risk_penalty
            )
            scored.append((score, card))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [card for _, card in scored[:top_k]]

    def compose_plan_cards(
        self,
        family_id: int,
        scenario: str,
        intensity: str,
        profile: Any | None,
        extra_context: str,
        max_cards: int = 3,
    ) -> list[StrategyCard]:
        ranked = self.retrieve_cards(
            family_id=family_id,
            scenario=scenario,
            intensity=intensity,
            profile=profile,
            extra_context=extra_context,
            top_k=12,
        )
        used: set[str] = set()
        selected: list[StrategyCard] = []
        for card in ranked:
            if card.card_id in used:
                continue
            used.add(card.card_id)
            selected.append(card)
            if len(selected) >= max_cards:
                break
        return selected
