from __future__ import annotations

import math
from collections import defaultdict
from time import perf_counter

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.vector import pgvector_available
from app.models import (
    ChildProfile,
    ChunkEmbedding,
    EvidenceUnit,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalCandidate,
    RetrievalRun,
    StrategyCard,
)
from app.schemas.domain import (
    CandidateScore,
    RetrievalEvidenceBundle,
    RetrievalFeatureAttribution,
    RetrievalQueryPlan,
    RetrievalSelectedSource,
)
from app.services.policy_learning import PolicyLearningService
from app.services.rag_providers import EmbeddingProviderRouter, simple_tokenize


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size]))
    right_norm = math.sqrt(sum(value * value for value in right[:size]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return _clamp(dot / (left_norm * right_norm), 0.0, 1.0)


def _overlap_score(query_tokens: set[str], target_text: str) -> float:
    target_tokens = set(simple_tokenize(target_text))
    if not query_tokens or not target_tokens:
        return 0.0
    return _clamp(len(query_tokens & target_tokens) / max(len(query_tokens), 1), 0.0, 1.0)


class RetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedding_router = EmbeddingProviderRouter()
        self.policy_learning = PolicyLearningService()

    def embed_text(self, text: str) -> list[float]:
        return self.embedding_router.embed(text).vector

    def compose_plan_cards(
        self,
        *,
        family_id: int,
        scenario: str,
        intensity: str,
        profile: ChildProfile | None,
        extra_context: str,
        max_cards: int = 3,
        intent: str = "plan",
        context_signal_keys: list[str] | None = None,
    ) -> list[StrategyCard]:
        selected_cards, _, _ = self.retrieve_bundle(
            family_id=family_id,
            scenario=scenario,
            intensity=intensity,
            profile=profile,
            extra_context=extra_context,
            max_cards=max_cards,
            intent=intent,
            context_signal_keys=context_signal_keys,
        )
        return selected_cards

    def retrieve_cards(
        self,
        *,
        family_id: int,
        scenario: str,
        intensity: str,
        profile: ChildProfile | None,
        extra_context: str,
        top_k: int = 10,
        intent: str = "plan",
        context_signal_keys: list[str] | None = None,
    ) -> list[StrategyCard]:
        _, _, ranked_cards = self.retrieve_bundle(
            family_id=family_id,
            scenario=scenario,
            intensity=intensity,
            profile=profile,
            extra_context=extra_context,
            max_cards=min(top_k, 3),
            top_k=top_k,
            intent=intent,
            context_signal_keys=context_signal_keys,
        )
        return ranked_cards[:top_k]

    def retrieve_bundle(
        self,
        *,
        family_id: int,
        scenario: str,
        intensity: str,
        profile: ChildProfile | None,
        extra_context: str,
        max_cards: int = 3,
        top_k: int = 10,
        intent: str = "script",
        context_signal_keys: list[str] | None = None,
        query_plan: RetrievalQueryPlan | None = None,
    ) -> tuple[list[StrategyCard], RetrievalEvidenceBundle, list[StrategyCard]]:
        started = perf_counter()
        cards = self.db.scalars(select(StrategyCard)).all()
        if not cards:
            empty_bundle = RetrievalEvidenceBundle(
                selected_card_ids=[],
                selected_evidence_unit_ids=[],
                selected_chunk_ids=[],
                candidate_scores=[],
                selection_reasons=["当前没有可用策略卡。"],
                rejected_reasons=[],
                counter_evidence=[],
                coverage_scores={"scenario": 0.0, "profile": 0.0, "safety": 0.0, "execution": 0.0},
                confidence_score=0.0,
                insufficient_evidence=True,
                missing_dimensions=["scenario", "profile", "safety", "execution"],
                ranking_summary="暂无可检索的策略卡。",
                query_plan=query_plan or self._build_query_plan(family_id, scenario, intensity, profile, extra_context, intent, context_signal_keys),
            )
            return [], empty_bundle, []

        query_plan = query_plan or self._build_query_plan(family_id, scenario, intensity, profile, extra_context, intent, context_signal_keys)
        query_text = self._build_query_text(scenario=scenario, intensity=intensity, profile=profile, extra_context=extra_context)
        query_tokens = set(simple_tokenize(query_text))
        query_embedding = self.embed_text(query_text)
        card_policy_map = self.policy_learning.get_effective_weight_map(self.db, family_id, "card", profile)
        scenario_policy_map = self.policy_learning.get_effective_weight_map(self.db, family_id, "scenario", profile)
        method_policy_map = self.policy_learning.get_effective_weight_map(self.db, family_id, "method", profile)
        memory_hits = self._family_memory_hits(family_id=family_id, query_embedding=query_embedding, query_tokens=query_tokens)
        candidate_cards = self._semantic_candidate_pool(cards=cards, query_embedding=query_embedding, limit=max(top_k * 4, 20))

        ranked_rows: list[tuple[StrategyCard, CandidateScore]] = []
        for card in candidate_cards:
            card_text = self._card_text(card)
            semantic_score = _cosine(query_embedding, card.embedding)
            lexical_score = _overlap_score(query_tokens, card_text)
            scenario_match = 1.0 if scenario in card.scenario_tags else 0.2 if any(tag in card.scenario_tags for tag in ("low_stim", "asdhack")) else 0.0
            profile_fit, personalization_notes = self._profile_fit(card=card, profile=profile, intensity=intensity)
            policy_weight = _clamp(card_policy_map.get(card.card_id, 0.0), -1.5, 1.5)
            historical_effect = _clamp(
                0.6 * max(scenario_policy_map.get(scenario, 0.0), 0.0)
                + 0.4 * max(method_policy_map.get(card.title, 0.0), 0.0),
                0.0,
                1.0,
            )
            execution_cost_bonus = self._execution_cost_bonus(card=card, intensity=intensity)
            risk_penalty = self._risk_penalty(card=card, intensity=intensity)
            taboo_conflict_penalty, hard_filter_tags = self._taboo_penalty(card=card, profile=profile)
            total_score = (
                0.32 * semantic_score
                + 0.18 * lexical_score
                + 0.15 * scenario_match
                + 0.12 * profile_fit
                + 0.08 * historical_effect
                + 0.1 * max(policy_weight, 0.0)
                + execution_cost_bonus
                - risk_penalty
                - taboo_conflict_penalty
            )
            why_selected: list[str] = []
            why_not_selected: list[str] = []
            if scenario_match >= 1.0:
                why_selected.append(f"场景与 {scenario} 直接匹配。")
            if profile_fit >= 0.75:
                why_selected.append("和孩子当前画像较匹配。")
            if policy_weight > 0:
                why_selected.append("历史反馈对这张卡更偏正向。")
            if taboo_conflict_penalty > 0:
                why_not_selected.append("和家庭禁忌存在冲突。")
            if risk_penalty >= 0.25:
                why_not_selected.append("当前风险/强度下这张卡偏激进。")
            if lexical_score < 0.15 and semantic_score < 0.2:
                why_not_selected.append("和当前上下文关联较弱。")

            ranked_rows.append(
                (
                    card,
                    CandidateScore(
                        card_id=card.card_id,
                        title=card.title,
                        total_score=round(total_score, 4),
                        semantic_score=round(semantic_score, 4),
                        lexical_score=round(lexical_score, 4),
                        scenario_match=round(scenario_match, 4),
                        profile_fit=round(profile_fit, 4),
                        historical_effect=round(historical_effect, 4),
                        policy_weight=round(policy_weight, 4),
                        execution_cost_bonus=round(execution_cost_bonus, 4),
                        risk_penalty=round(risk_penalty, 4),
                        taboo_conflict_penalty=round(taboo_conflict_penalty, 4),
                        selected=False,
                        why_selected=why_selected[:3],
                        why_not_selected=why_not_selected[:3],
                        selected_chunk_ids=[],
                        hard_filter_tags=hard_filter_tags[:4],
                        personalization_notes=personalization_notes[:3],
                    ),
                )
            )

        ranked_rows.sort(key=lambda item: item[1].total_score, reverse=True)

        selected_rows: list[tuple[StrategyCard, CandidateScore]] = []
        for row in ranked_rows:
            if len(selected_rows) >= max_cards:
                break
            if row[1].taboo_conflict_penalty >= 0.9:
                continue
            selected_rows.append(row)
        if not selected_rows:
            selected_rows = ranked_rows[:max_cards]

        selected_cards = [card for card, _ in selected_rows]
        selected_ids = {card.card_id for card in selected_cards}
        for _, candidate in ranked_rows:
            candidate.selected = candidate.card_id in selected_ids

        selected_unit_ids, selected_chunk_ids, coverage_scores = self._select_evidence(
            selected_cards=selected_cards,
            query_tokens=query_tokens,
            query_embedding=query_embedding,
        )
        missing_dimensions = [name for name, score in coverage_scores.items() if score < 0.5]
        counter_evidence = [
            f"{candidate.title} 未入选：{candidate.why_not_selected[0]}"
            for _, candidate in ranked_rows
            if not candidate.selected and candidate.why_not_selected
        ][:4]
        selection_reasons = [
            f"{candidate.title}：{candidate.why_selected[0] if candidate.why_selected else '综合得分更高。'}"
            for _, candidate in selected_rows
        ][:4]
        rejected_reasons = [
            f"{candidate.title}：{candidate.why_not_selected[0]}"
            for _, candidate in ranked_rows
            if not candidate.selected and candidate.why_not_selected
        ][:4]
        confidence_score = _clamp(
            0.35
            + 0.15 * len(selected_cards)
            + 0.1 * sum(1 for score in coverage_scores.values() if score >= 0.5)
            + 0.15 * (sum(candidate.total_score for _, candidate in selected_rows) / max(len(selected_rows), 1)),
            0.0,
            0.95,
        )
        selected_sources = [
            RetrievalSelectedSource(
                source_id=card.card_id,
                source_type="strategy_card",
                title=card.title,
                scope="global",
            )
            for card in selected_cards
        ]
        selected_sources.extend(
            RetrievalSelectedSource(
                source_id=str(chunk.id),
                source_type=chunk.source_type,
                title=str(chunk.metadata_json.get("title") or chunk.content[:48]),
                scope="family",
            )
            for chunk in memory_hits[:3]
        )
        feature_attribution = [
            RetrievalFeatureAttribution(
                target_id=candidate.card_id,
                target_kind="card",
                summary=" / ".join(candidate.why_selected[:2] or ["综合匹配度更高。"]),
                contribution=round(candidate.total_score, 4),
            )
            for _, candidate in selected_rows
        ]
        feature_attribution.extend(
            RetrievalFeatureAttribution(
                target_id=str(chunk.id),
                target_kind="family_memory",
                summary="近期家庭记忆命中",
                contribution=0.35,
            )
            for chunk in memory_hits[:3]
        )
        combined_selected_chunk_ids = list(dict.fromkeys([*selected_chunk_ids, *[str(chunk.id) for chunk in memory_hits[:3]]]))
        trace_chunks = self._build_trace_chunk_candidates(
            selected_chunk_ids=combined_selected_chunk_ids,
            memory_hits=memory_hits,
            query_embedding=query_embedding,
            query_tokens=query_tokens,
        )
        retrieval_latency_ms = max(1, int((perf_counter() - started) * 1000))
        bundle = RetrievalEvidenceBundle(
            selected_card_ids=[card.card_id for card in selected_cards],
            selected_evidence_unit_ids=selected_unit_ids[:8],
            selected_chunk_ids=combined_selected_chunk_ids[:12],
            candidate_scores=[candidate for _, candidate in ranked_rows],
            selection_reasons=selection_reasons or ["综合匹配到当前场景与画像。"],
            rejected_reasons=rejected_reasons or ["其余卡片与当前场景匹配度较低。"],
            counter_evidence=counter_evidence or ["已过滤更高风险或与禁忌冲突的候选。"],
            coverage_scores=coverage_scores,
            confidence_score=round(confidence_score, 2),
            insufficient_evidence=bool(missing_dimensions),
            missing_dimensions=missing_dimensions[:4],
            ranking_summary=f"从 {len(cards)} 张卡中筛出 {len(selected_cards)} 张更适合当前 {scenario}/{intensity} 场景的策略卡。",
            query_plan=query_plan,
            selected_sources=selected_sources,
            feature_attribution=feature_attribution,
            personalization_applied=self._personalization_applied(profile=profile, selected_rows=selected_rows, memory_hits=memory_hits),
            hard_filtered_reasons=[reason for reason in rejected_reasons if "冲突" in reason][:6],
            coverage_gaps=missing_dimensions[:6],
            knowledge_versions=list(dict.fromkeys([settings.corpus_version, *[chunk.knowledge_version for chunk in memory_hits]]) )[:6],
            retrieval_latency_ms=retrieval_latency_ms,
            retrieval_run_id=None,
        )
        bundle.retrieval_run_id = self._persist_retrieval_run(
            family_id=family_id,
            intent=intent,
            bundle=bundle,
            candidates=[candidate for _, candidate in ranked_rows[:top_k]],
            chunk_candidates=trace_chunks,
        )
        return selected_cards, bundle, [card for card, _ in ranked_rows]

    def _build_query_text(
        self,
        *,
        scenario: str,
        intensity: str,
        profile: ChildProfile | None,
        extra_context: str,
    ) -> str:
        profile_bits = []
        if profile is not None:
            profile_bits.extend(profile.triggers[:3])
            profile_bits.extend(profile.soothing_methods[:3])
            profile_bits.extend(profile.donts[:2])
            profile_bits.append(profile.language_level)
            profile_bits.append(profile.age_band)
        return " ".join([scenario, intensity, *profile_bits, extra_context]).strip()

    def _build_query_plan(
        self,
        family_id: int,
        scenario: str,
        intensity: str,
        profile: ChildProfile | None,
        extra_context: str,
        intent: str,
        context_signal_keys: list[str] | None,
    ) -> RetrievalQueryPlan:
        return RetrievalQueryPlan(
            intent=intent if intent in {"plan", "script", "friction", "report"} else "plan",
            scenario=scenario,
            intensity=intensity,
            family_id=family_id,
            profile_facets=[
                *(profile.triggers[:3] if profile else []),
                *(profile.sensory_flags[:2] if profile else []),
            ][:10],
            recent_context_signals=list(context_signal_keys or simple_tokenize(extra_context)[:10]),
            hard_exclusions=list(profile.donts[:4] if profile else []),
            time_window="recent",
            raw_query_text=self._build_query_text(scenario=scenario, intensity=intensity, profile=profile, extra_context=extra_context)[:400],
        )

    def _card_text(self, card: StrategyCard) -> str:
        return "\n".join(
            [
                card.title,
                " ".join(card.scenario_tags),
                " ".join(card.steps_json),
                " ".join(str(value) for value in card.scripts_json.values()),
                " ".join(card.donts_json),
                " ".join(card.escalate_json),
            ]
        )

    def _profile_fit(
        self,
        *,
        card: StrategyCard,
        profile: ChildProfile | None,
        intensity: str,
    ) -> tuple[float, list[str]]:
        if profile is None:
            return 0.5, []
        conditions = card.conditions_json or {}
        notes: list[str] = []
        score = 0.2
        if not conditions.get("age_bands") or profile.age_band in conditions.get("age_bands", []):
            score += 0.25
            notes.append("年龄段匹配")
        if not conditions.get("language_levels") or profile.language_level in conditions.get("language_levels", []):
            score += 0.25
            notes.append("语言水平匹配")
        if not conditions.get("sensory") or any(flag in conditions.get("sensory", []) for flag in profile.sensory_flags):
            score += 0.15
        if not conditions.get("intensity") or intensity in conditions.get("intensity", []):
            score += 0.15
        return _clamp(score, 0.0, 1.0), notes

    def _execution_cost_bonus(self, *, card: StrategyCard, intensity: str) -> float:
        cost_map = {"low": 0.12, "medium": 0.05, "high": -0.02}
        bonus = cost_map.get(card.cost_level, 0.0)
        if intensity == "heavy" and card.cost_level == "high":
            bonus -= 0.05
        return bonus

    def _risk_penalty(self, *, card: StrategyCard, intensity: str) -> float:
        risk_map = {"low": 0.02, "medium": 0.12, "high": 0.28}
        penalty = risk_map.get(card.risk_level, 0.1)
        if intensity == "heavy" and card.risk_level == "high":
            penalty += 0.12
        return penalty

    def _taboo_penalty(
        self,
        *,
        card: StrategyCard,
        profile: ChildProfile | None,
    ) -> tuple[float, list[str]]:
        if profile is None or not profile.donts:
            return 0.0, []
        text = self._card_text(card)
        taboo_aliases = {
            "不可触碰": ["触碰", "强拉", "拉走", "拽"],
            "不可大声": ["大声", "提高音量", "吼", "催促"],
        }
        hits: list[str] = []
        for item in profile.donts:
            if not item:
                continue
            alias_tokens = taboo_aliases.get(item, [item])
            if any(token in text for token in alias_tokens):
                hits.append(item)
        penalty = 0.45 * len(hits)
        return penalty, hits

    def _select_evidence(
        self,
        *,
        selected_cards: list[StrategyCard],
        query_tokens: set[str],
        query_embedding: list[float],
    ) -> tuple[list[str], list[str], dict[str, float]]:
        if not selected_cards:
            return [], [], {"scenario": 0.0, "profile": 0.0, "safety": 0.0, "execution": 0.0}

        card_ids = [card.card_id for card in selected_cards]
        units = self.db.scalars(select(EvidenceUnit).where(EvidenceUnit.card_id.in_(card_ids))).all()
        best_by_dimension: dict[str, tuple[float, EvidenceUnit]] = {}
        for unit in units:
            score = 0.35 + _overlap_score(query_tokens, unit.text)
            for dimension in unit.dimensions_json:
                current = best_by_dimension.get(dimension)
                if current is None or score > current[0]:
                    best_by_dimension[dimension] = (score, unit)

        selected_unit_ids: list[str] = []
        for dimension in ["scenario", "profile", "safety", "execution"]:
            best = best_by_dimension.get(dimension)
            if best is None:
                continue
            if best[1].id not in selected_unit_ids:
                selected_unit_ids.append(best[1].id)

        chunks = self._semantic_chunks_for_cards(card_ids=card_ids, query_embedding=query_embedding, limit=max(len(card_ids) * 3, 6))
        chunks_by_card: dict[str, list[str]] = defaultdict(list)
        for chunk in chunks:
            chunks_by_card[chunk.card_id or ""].append(str(chunk.id))
        selected_chunk_ids: list[str] = []
        for card in selected_cards:
            selected_chunk_ids.extend(chunks_by_card.get(card.card_id, [])[:2])

        coverage_scores = {
            "scenario": 1.0 if "scenario" in best_by_dimension else 0.0,
            "profile": 1.0 if "profile" in best_by_dimension else 0.0,
            "safety": 1.0 if "safety" in best_by_dimension else 0.0,
            "execution": 1.0 if "execution" in best_by_dimension else 0.0,
        }
        return selected_unit_ids, selected_chunk_ids, coverage_scores

    def _personalization_applied(
        self,
        *,
        profile: ChildProfile | None,
        selected_rows: list[tuple[StrategyCard, CandidateScore]],
        memory_hits: list[KnowledgeChunk],
    ) -> list[str]:
        notes: list[str] = []
        if profile is not None and profile.donts:
            notes.append(f"已过滤禁忌：{profile.donts[0]}")
        for _, candidate in selected_rows:
            notes.extend(candidate.personalization_notes[:1])
        if memory_hits:
            notes.append(f"命中 {min(len(memory_hits), 3)} 条近期家庭记忆")
        return list(dict.fromkeys(notes))[:6]

    def _semantic_candidate_pool(self, *, cards: list[StrategyCard], query_embedding: list[float], limit: int) -> list[StrategyCard]:
        bind = self.db.get_bind()
        if bind is None or bind.dialect.name != "postgresql" or not pgvector_available():
            return cards
        try:
            semantic_rows = self.db.scalars(
                select(StrategyCard).order_by(StrategyCard.embedding.cosine_distance(query_embedding)).limit(limit)
            ).all()
            if semantic_rows:
                return semantic_rows
        except Exception:
            return cards
        return cards

    def _family_memory_hits(
        self,
        *,
        family_id: int,
        query_embedding: list[float],
        query_tokens: set[str],
    ) -> list[KnowledgeChunk]:
        rows = self._semantic_family_chunks(family_id=family_id, query_embedding=query_embedding, limit=12)
        scored: list[tuple[float, KnowledgeChunk]] = []
        for row in rows:
            dense = _cosine(query_embedding, self._chunk_embedding(row))
            lexical = _overlap_score(query_tokens, row.content)
            scored.append((dense * 0.7 + lexical * 0.2 + row.source_confidence * 0.1, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:4]]

    def _semantic_family_chunks(self, *, family_id: int, query_embedding: list[float], limit: int) -> list[KnowledgeChunk]:
        bind = self.db.get_bind()
        fallback = self.db.scalars(
            self._active_chunk_query().where(
                KnowledgeChunk.family_id == family_id,
            )
        ).all()
        if bind is None or bind.dialect.name != "postgresql" or not pgvector_available():
            return fallback
        try:
            rows = self.db.scalars(
                self._active_chunk_query()
                .join(ChunkEmbedding, ChunkEmbedding.chunk_id == KnowledgeChunk.id)
                .where(
                    KnowledgeChunk.family_id == family_id,
                    ChunkEmbedding.active.is_(True),
                    ChunkEmbedding.rebuild_version == settings.corpus_version,
                )
                .order_by(ChunkEmbedding.vector_json.cosine_distance(query_embedding))
                .limit(limit)
            ).all()
            if rows:
                return rows
        except Exception:
            return fallback
        return []

    def _semantic_chunks_for_cards(self, *, card_ids: list[str], query_embedding: list[float], limit: int) -> list[KnowledgeChunk]:
        if not card_ids:
            return []
        bind = self.db.get_bind()
        fallback = self.db.scalars(self._active_chunk_query().where(KnowledgeChunk.card_id.in_(card_ids))).all()
        if bind is None or bind.dialect.name != "postgresql" or not pgvector_available():
            return fallback
        try:
            rows = self.db.scalars(
                self._active_chunk_query()
                .join(ChunkEmbedding, ChunkEmbedding.chunk_id == KnowledgeChunk.id)
                .where(
                    KnowledgeChunk.card_id.in_(card_ids),
                    ChunkEmbedding.active.is_(True),
                    ChunkEmbedding.rebuild_version == settings.corpus_version,
                )
                .order_by(ChunkEmbedding.vector_json.cosine_distance(query_embedding))
                .limit(limit)
            ).all()
            if rows:
                return rows
        except Exception:
            return fallback
        return fallback

    def _chunk_embedding(self, chunk: KnowledgeChunk) -> list[float]:
        active_embedding = next(
            (
                embedding
                for embedding in chunk.embeddings
                if embedding.active and embedding.rebuild_version == settings.corpus_version
            ),
            None,
        )
        if active_embedding is None:
            active_embedding = next((embedding for embedding in chunk.embeddings if embedding.active), None)
        return active_embedding.vector_json if active_embedding is not None else self.embed_text(chunk.content)

    def _build_trace_chunk_candidates(
        self,
        *,
        selected_chunk_ids: list[str],
        memory_hits: list[KnowledgeChunk],
        query_embedding: list[float],
        query_tokens: set[str],
    ) -> list[tuple[KnowledgeChunk, dict[str, float | bool | str | list[dict[str, float | str]]]]]:
        chunk_map: dict[int, KnowledgeChunk] = {}
        for raw_id in selected_chunk_ids:
            if not str(raw_id).isdigit():
                continue
            chunk = self.db.get(KnowledgeChunk, int(raw_id))
            if chunk is not None:
                chunk_map[chunk.id] = chunk
        for chunk in memory_hits[:6]:
            chunk_map[chunk.id] = chunk

        scored: list[tuple[KnowledgeChunk, dict[str, float | bool | str | list[dict[str, float | str]]]]] = []
        selected_ids = {int(raw_id) for raw_id in selected_chunk_ids if str(raw_id).isdigit()}
        for chunk in chunk_map.values():
            dense_score = round(_cosine(query_embedding, self._chunk_embedding(chunk)), 4)
            sparse_score = round(_overlap_score(query_tokens, chunk.content), 4)
            total_score = round(dense_score * 0.7 + sparse_score * 0.2 + chunk.source_confidence * 0.1, 4)
            selected = chunk.id in selected_ids
            filter_reason = "" if selected else "未进入最小证据包。"
            scored.append(
                (
                    chunk,
                    {
                        "total_score": total_score,
                        "dense_score": dense_score,
                        "sparse_score": sparse_score,
                        "profile_score": 0.0,
                        "history_score": round(chunk.source_confidence, 4),
                        "policy_score": 0.0,
                        "safety_penalty": 0.0,
                        "selected": selected,
                        "filter_reason": filter_reason,
                        "feature_attribution": [
                            {
                                "summary": str(chunk.metadata_json.get("title") or chunk.chunk_type),
                                "contribution": total_score,
                            }
                        ],
                    },
                )
            )
        scored.sort(key=lambda item: float(item[1]["total_score"]), reverse=True)
        return scored[:8]

    def _active_chunk_query(self) -> Select[tuple[KnowledgeChunk]]:
        return (
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(
                KnowledgeChunk.is_active.is_(True),
                KnowledgeChunk.knowledge_version == settings.corpus_version,
                KnowledgeDocument.status == "active",
                KnowledgeDocument.version == settings.corpus_version,
            )
        )

    def _persist_retrieval_run(
        self,
        *,
        family_id: int,
        intent: str,
        bundle: RetrievalEvidenceBundle,
        candidates: list[CandidateScore],
        chunk_candidates: list[tuple[KnowledgeChunk, dict[str, float | bool | str | list[dict[str, float | str]]]]],
    ) -> int | None:
        run = RetrievalRun(
            family_id=family_id,
            intent=intent,
            query_plan_json=bundle.query_plan.model_dump() if bundle.query_plan is not None else {},
            selected_sources_json=[item.model_dump() for item in bundle.selected_sources],
            selected_chunk_ids_json=list(bundle.selected_chunk_ids),
            hard_filtered_reasons_json=list(bundle.hard_filtered_reasons),
            knowledge_versions_json=list(bundle.knowledge_versions),
            feature_attribution_json=[item.model_dump() for item in bundle.feature_attribution],
            personalization_applied_json=list(bundle.personalization_applied),
            retrieval_latency_ms=bundle.retrieval_latency_ms,
            reranker_model="heuristic-rerank-v1",
            embedding_provider=self.embedding_router.primary,
            embedding_model=settings.openai_embedding_model if self.embedding_router.primary != "hash" else "hash-embedding",
            corpus_version=settings.corpus_version,
        )
        self.db.add(run)
        self.db.flush()
        for candidate in candidates:
            self.db.add(
                RetrievalCandidate(
                    run_id=run.id,
                    card_id=candidate.card_id,
                    title=candidate.title,
                    source_type="strategy_card",
                    total_score=candidate.total_score,
                    dense_score=candidate.semantic_score,
                    sparse_score=candidate.lexical_score,
                    profile_score=candidate.profile_fit,
                    history_score=candidate.historical_effect,
                    policy_score=candidate.policy_weight,
                    safety_penalty=max(candidate.risk_penalty, candidate.taboo_conflict_penalty),
                    selected=candidate.selected,
                    filter_reason="; ".join(candidate.why_not_selected),
                    feature_attribution_json=[
                        {"summary": note, "contribution": 0.0}
                        for note in candidate.personalization_notes[:2]
                    ],
                )
            )
        for chunk, score in chunk_candidates:
            self.db.add(
                RetrievalCandidate(
                    run_id=run.id,
                    chunk_id=chunk.id,
                    title=str(chunk.metadata_json.get("title") or chunk.content[:80]),
                    source_type=chunk.source_type,
                    total_score=float(score["total_score"]),
                    dense_score=float(score["dense_score"]),
                    sparse_score=float(score["sparse_score"]),
                    profile_score=float(score["profile_score"]),
                    history_score=float(score["history_score"]),
                    policy_score=float(score["policy_score"]),
                    safety_penalty=float(score["safety_penalty"]),
                    selected=bool(score["selected"]),
                    filter_reason=str(score["filter_reason"]),
                    feature_attribution_json=list(score["feature_attribution"]),
                )
            )
        self.db.flush()
        return run.id
