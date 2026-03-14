from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models import ChildProfile, Family, FamilyPolicyWeight, GlobalPolicyPrior, IncidentLog, KnowledgeChunk, Review, SegmentPolicyPrior
from app.schemas.domain import PolicyMemoryDiffRead, PolicyMemoryItemRead, PolicyMemorySnapshotRead
from app.services.review_learning import is_learnable_card_id

ALLOWED_TARGET_KINDS = {
    "card",
    "chunk",
    "evidence_unit",
    "scenario",
    "method",
    "timing",
    "handoff_pattern",
    "emotion_pattern",
    "overload_trigger",
    "successful_adjustment",
    "failed_adjustment",
}


class PolicyLearningService:
    def get_effective_weight_map(
        self,
        db: Session,
        family_id: int,
        target_kind: str,
        profile: ChildProfile | None,
    ) -> dict[str, float]:
        family_map = self.get_weight_map(db, family_id, target_kind)
        segment_key = self.segment_key_for_profile(profile)
        segment_map = self._segment_weight_map(db, segment_key, target_kind)
        global_map = self._global_weight_map(db, target_kind)

        keys = set(global_map) | set(segment_map) | set(family_map)
        combined: dict[str, float] = {}
        for key in keys:
            combined[key] = round(
                0.2 * global_map.get(key, 0.0)
                + 0.3 * segment_map.get(key, 0.0)
                + 0.5 * family_map.get(key, 0.0),
                4,
            )
        return combined

    def get_weight_map(self, db: Session, family_id: int, target_kind: str) -> dict[str, float]:
        rows = db.scalars(
            select(FamilyPolicyWeight).where(
                FamilyPolicyWeight.family_id == family_id,
                FamilyPolicyWeight.target_kind == target_kind,
            )
        ).all()
        return {row.target_key: row.weight for row in rows}

    def build_snapshot(self, db: Session, family_id: int) -> PolicyMemorySnapshotRead:
        family = db.get(Family, family_id)
        profile = family.child_profile if family is not None else None
        segment_key = self.segment_key_for_profile(profile)
        target_kinds = [
            "card",
            "chunk",
            "evidence_unit",
            "scenario",
            "method",
            "timing",
            "handoff_pattern",
            "emotion_pattern",
            "overload_trigger",
            "successful_adjustment",
            "failed_adjustment",
        ]
        items: list[PolicyMemoryItemRead] = []
        for target_kind in target_kinds:
            family_map = self.get_weight_map(db, family_id, target_kind)
            segment_map = self._segment_weight_map(db, segment_key, target_kind)
            global_map = self._global_weight_map(db, target_kind)
            for key in sorted(set(global_map) | set(segment_map) | set(family_map)):
                items.append(
                    PolicyMemoryItemRead(
                        target_kind=target_kind,  # type: ignore[arg-type]
                        target_key=key,
                        global_weight=round(global_map.get(key, 0.0), 4),
                        segment_weight=round(segment_map.get(key, 0.0), 4),
                        family_weight=round(family_map.get(key, 0.0), 4),
                        effective_weight=round(
                            0.2 * global_map.get(key, 0.0)
                            + 0.3 * segment_map.get(key, 0.0)
                            + 0.5 * family_map.get(key, 0.0),
                            4,
                        ),
                        source_evidence_count=self._source_evidence_count(db, family_id, target_kind, key),
                        recent_effect_window="recent_30d" if target_kind in {"method", "timing", "chunk"} else "lifetime",
                        top_supporting_chunk_ids=self._supporting_chunk_ids(db, family_id, target_kind, key),
                    )
                )

        items.sort(key=lambda item: abs(item.effective_weight), reverse=True)
        return PolicyMemorySnapshotRead(
            family_id=family_id,
            segment_key=segment_key,
            generated_at=utc_now(),
            items=items[:40],
        )

    def build_diff(self, db: Session, family_id: int) -> PolicyMemoryDiffRead:
        snapshot = self.build_snapshot(db, family_id)
        strongest_positive = [item for item in snapshot.items if item.effective_weight > 0][:5]
        strongest_negative = [item for item in snapshot.items if item.effective_weight < 0][:5]
        return PolicyMemoryDiffRead(
            family_id=family_id,
            segment_key=snapshot.segment_key,
            strongest_positive=strongest_positive,
            strongest_negative=strongest_negative,
        )

    def _source_evidence_count(self, db: Session, family_id: int, target_kind: str, target_key: str) -> int:
        if target_kind == "chunk":
            if not target_key.isdigit():
                return 0
            return 1 if db.scalar(select(KnowledgeChunk.id).where(KnowledgeChunk.id == int(target_key))) else 0
        if target_kind == "card":
            reviews = db.scalars(select(Review).where(Review.family_id == family_id)).all()
            return sum(1 for review in reviews if target_key in review.card_ids)
        if target_kind in {"method", "timing"}:
            return len(
                db.scalars(select(IncidentLog).where(IncidentLog.family_id == family_id)).all()
            )
        return 0

    def _supporting_chunk_ids(self, db: Session, family_id: int, target_kind: str, target_key: str) -> list[str]:
        if target_kind == "card":
            rows = db.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.card_id == target_key,
                    KnowledgeChunk.is_active.is_(True),
                )
            ).all()
            return [str(row.id) for row in rows[:3]]
        if target_kind == "chunk":
            return [target_key]
        if target_kind == "method":
            rows = db.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.family_id == family_id,
                    KnowledgeChunk.source_type == "review_summary",
                    KnowledgeChunk.is_active.is_(True),
                )
            ).all()
            return [str(row.id) for row in rows[:3]]
        return []

    def rebuild_card_weights(self, db: Session, family_id: int) -> dict[str, float]:
        reviews = db.scalars(select(Review).where(Review.family_id == family_id)).all()
        card_scores: dict[str, list[int]] = {}
        card_usage: dict[str, int] = {}
        now = utc_now()

        for review in reviews:
            for card_id in review.card_ids:
                if not is_learnable_card_id(card_id):
                    continue
                card_scores.setdefault(card_id, []).append(review.outcome_score)
                card_usage[card_id] = card_usage.get(card_id, 0) + 1

        existing = {
            row.target_key: row
            for row in db.scalars(
                select(FamilyPolicyWeight).where(
                    FamilyPolicyWeight.family_id == family_id,
                    FamilyPolicyWeight.target_kind == "card",
                )
            ).all()
        }

        for card_id, scores in card_scores.items():
            avg_score = sum(scores) / len(scores)
            row = existing.get(card_id)
            if row is None:
                row = FamilyPolicyWeight(
                    family_id=family_id,
                    target_kind="card",
                    target_key=card_id,
                )
                db.add(row)
                existing[card_id] = row
            row.weight = round(self._bounded_weight(avg_score / 2.0), 3)
            row.usage_count = card_usage[card_id]
            row.success_count = sum(1 for score in scores if score > 0)
            row.failure_count = sum(1 for score in scores if score < 0)
            row.recent_outcome_avg = round(avg_score, 3)
            row.last_feedback_at = now

        db.flush()
        return {card_id: row.weight for card_id, row in existing.items()}

    def record_review(
        self,
        db: Session,
        family_id: int,
        outcome_score: int,
        card_ids: list[str],
        scenario: str | None,
        response_action: str = "",
        occurred_at: datetime | None = None,
    ) -> None:
        family = db.get(Family, family_id)
        profile = family.child_profile if family is not None else None
        for card_id in card_ids:
            if is_learnable_card_id(card_id):
                self._apply_feedback(
                    db=db,
                    family_id=family_id,
                    target_kind="card",
                    target_key=card_id,
                    outcome_score=outcome_score,
                    profile=profile,
                    occurred_at=occurred_at,
                )

        if scenario:
            self._apply_feedback(
                db=db,
                family_id=family_id,
                target_kind="scenario",
                target_key=scenario,
                outcome_score=outcome_score,
                profile=profile,
                occurred_at=occurred_at,
            )

        method_key = response_action.strip()
        if method_key:
            self._apply_feedback(
                db=db,
                family_id=family_id,
                target_kind="method",
                target_key=method_key[:128],
                outcome_score=outcome_score,
                profile=profile,
                occurred_at=occurred_at,
            )

    def record_training_feedback(
        self,
        db: Session,
        family_id: int,
        outcome_score: int,
        area_key: str,
        task_title: str,
        task_date: str,
        occurred_at: datetime | None = None,
    ) -> None:
        family = db.get(Family, family_id)
        profile = family.child_profile if family is not None else None
        self._apply_feedback(
            db=db,
            family_id=family_id,
            target_kind="method",
            target_key=area_key,
            outcome_score=outcome_score,
            profile=profile,
            occurred_at=occurred_at,
        )
        self._apply_feedback(
            db=db,
            family_id=family_id,
            target_kind="timing",
            target_key=f"{task_date}:{task_title[:64]}",
            outcome_score=outcome_score,
            profile=profile,
            occurred_at=occurred_at,
        )

    def record_report_feedback(
        self,
        db: Session,
        family_id: int,
        target_kind: str,
        target_key: str,
        feedback: str,
        occurred_at: datetime | None = None,
    ) -> None:
        family = db.get(Family, family_id)
        profile = family.child_profile if family is not None else None
        mapped_kind = "method" if target_kind == "strategy" else "timing"
        outcome_score = {
            "effective": 2,
            "continue": 1,
            "adjust": -1,
            "not_effective": -2,
        }[feedback]
        self._apply_feedback(
            db=db,
            family_id=family_id,
            target_kind=mapped_kind,
            target_key=target_key,
            outcome_score=outcome_score,
            profile=profile,
            occurred_at=occurred_at,
        )

    def record_adaptive_feedback(
        self,
        db: Session,
        family_id: int,
        *,
        outcome_score: int,
        emotion_pattern: str,
        overload_trigger: str,
        handoff_pattern: str,
        adjustment_key: str,
        occurred_at: datetime | None = None,
    ) -> None:
        family = db.get(Family, family_id)
        profile = family.child_profile if family is not None else None
        self._apply_feedback(
            db=db,
            family_id=family_id,
            target_kind="emotion_pattern",
            target_key=emotion_pattern[:128],
            outcome_score=outcome_score,
            profile=profile,
            occurred_at=occurred_at,
        )
        self._apply_feedback(
            db=db,
            family_id=family_id,
            target_kind="overload_trigger",
            target_key=overload_trigger[:128],
            outcome_score=outcome_score,
            profile=profile,
            occurred_at=occurred_at,
        )
        if handoff_pattern.strip():
            self._apply_feedback(
                db=db,
                family_id=family_id,
                target_kind="handoff_pattern",
                target_key=handoff_pattern[:128],
                outcome_score=outcome_score,
                profile=profile,
                occurred_at=occurred_at,
            )
        self._apply_feedback(
            db=db,
            family_id=family_id,
            target_kind="successful_adjustment" if outcome_score > 0 else "failed_adjustment",
            target_key=adjustment_key[:128],
            outcome_score=outcome_score,
            profile=profile,
            occurred_at=occurred_at,
        )

    def _apply_feedback(
        self,
        db: Session,
        family_id: int,
        target_kind: str,
        target_key: str,
        outcome_score: int,
        profile: ChildProfile | None,
        occurred_at: datetime | None = None,
    ) -> None:
        if target_kind not in ALLOWED_TARGET_KINDS:
            return
        normalized_key = target_key.strip()
        if not normalized_key:
            return

        row = db.scalar(
            select(FamilyPolicyWeight).where(
                FamilyPolicyWeight.family_id == family_id,
                FamilyPolicyWeight.target_kind == target_kind,
                FamilyPolicyWeight.target_key == normalized_key,
            )
        )
        if row is None:
            row = FamilyPolicyWeight(
                family_id=family_id,
                target_kind=target_kind,
                target_key=normalized_key,
            )
            db.add(row)
            db.flush()

        previous_usage = row.usage_count
        row.usage_count += 1
        if outcome_score > 0:
            row.success_count += 1
        elif outcome_score < 0:
            row.failure_count += 1

        if previous_usage == 0:
            row.recent_outcome_avg = float(outcome_score)
        else:
            row.recent_outcome_avg = round(row.recent_outcome_avg * 0.65 + outcome_score * 0.35, 3)

        delta = outcome_score / 2.0
        if delta < 0:
            delta *= 0.6
        elif row.success_count >= 2 and row.recent_outcome_avg > 0:
            delta *= 1.1
        row.weight = round(self._bounded_weight(row.weight + delta * 0.22), 3)
        row.last_feedback_at = occurred_at or utc_now()

        segment_key = self.segment_key_for_profile(profile)
        self._apply_segment_feedback(
            db=db,
            segment_key=segment_key,
            target_kind=target_kind,
            target_key=normalized_key,
            outcome_score=outcome_score,
        )
        self._apply_global_feedback(
            db=db,
            target_kind=target_kind,
            target_key=normalized_key,
            outcome_score=outcome_score,
        )
        db.flush()

    @staticmethod
    def infer_review_scenario(db: Session, review: Review) -> str | None:
        incident = db.get(IncidentLog, review.incident_id)
        if incident is None:
            return None
        return incident.scenario

    @staticmethod
    def segment_key_for_profile(profile: ChildProfile | None) -> str:
        if profile is None:
            return "unknown"
        sensory = ",".join(sorted((profile.sensory_flags or [])[:3])) or "none"
        primary_scenario = (profile.high_friction_scenarios or ["transition"])[0]
        return f"{profile.age_band}|{profile.language_level}|{primary_scenario}|{sensory}"

    def _segment_weight_map(self, db: Session, segment_key: str, target_kind: str) -> dict[str, float]:
        rows = db.scalars(
            select(SegmentPolicyPrior).where(
                SegmentPolicyPrior.segment_key == segment_key,
                SegmentPolicyPrior.target_kind == target_kind,
            )
        ).all()
        return {row.target_key: row.weight for row in rows}

    def _global_weight_map(self, db: Session, target_kind: str) -> dict[str, float]:
        rows = db.scalars(
            select(GlobalPolicyPrior).where(
                GlobalPolicyPrior.target_kind == target_kind,
            )
        ).all()
        return {row.target_key: row.weight for row in rows}

    def _apply_global_feedback(self, db: Session, target_kind: str, target_key: str, outcome_score: int) -> None:
        row = db.scalar(
            select(GlobalPolicyPrior).where(
                GlobalPolicyPrior.target_kind == target_kind,
                GlobalPolicyPrior.target_key == target_key,
            )
        )
        if row is None:
            row = GlobalPolicyPrior(target_kind=target_kind, target_key=target_key)
            db.add(row)
            db.flush()
        row.usage_count += 1
        row.weight = round(self._bounded_weight(row.weight + outcome_score * 0.04), 3)

    def _apply_segment_feedback(
        self,
        db: Session,
        segment_key: str,
        target_kind: str,
        target_key: str,
        outcome_score: int,
    ) -> None:
        row = db.scalar(
            select(SegmentPolicyPrior).where(
                SegmentPolicyPrior.segment_key == segment_key,
                SegmentPolicyPrior.target_kind == target_kind,
                SegmentPolicyPrior.target_key == target_key,
            )
        )
        if row is None:
            row = SegmentPolicyPrior(segment_key=segment_key, target_kind=target_kind, target_key=target_key)
            db.add(row)
            db.flush()
        row.usage_count += 1
        row.weight = round(self._bounded_weight(row.weight + outcome_score * 0.08), 3)

    @staticmethod
    def _bounded_weight(value: float) -> float:
        return max(-1.5, min(1.5, value))
