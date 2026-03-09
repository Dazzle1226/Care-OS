from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Review
from app.services.rule_fallback import build_fallback_coach_tip


class CoachAgent:
    def today_one_thing(self, risk_level: str, recent_scenario: str | None = None) -> str:
        base = build_fallback_coach_tip(risk_level)
        if recent_scenario:
            return f"{base}（优先场景：{recent_scenario}）"
        return base

    def update_preference_weights(self, db: Session, family_id: int) -> dict[str, float]:
        db.flush()
        reviews = db.scalars(select(Review).where(Review.family_id == family_id)).all()
        bucket: dict[str, list[int]] = defaultdict(list)
        for review in reviews:
            for card_id in review.card_ids:
                bucket[card_id].append(review.outcome_score)

        weights: dict[str, float] = {}
        for card_id, scores in bucket.items():
            weights[card_id] = round(sum(scores) / len(scores), 3)

        payload = json.dumps({"family_id": family_id, "weights": weights}, sort_keys=True, ensure_ascii=False)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        db.add(AuditLog(family_id=family_id, event_type="coach_weight_update", payload_hash=payload_hash))
        db.flush()

        return weights
