from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models import AdaptiveSession, Family, SessionEvent
from app.schemas.domain import (
    AdaptiveSessionRead,
    ContextSignalRead,
    CoordinationDecision,
    DecisionGraphStageRun,
    EmotionAssessment,
    SessionEventRead,
    SignalOutput,
    TrainingDashboardResponse,
    V3TrainingSessionCloseRequest,
    V3TrainingSessionCloseResponse,
    V3TrainingSessionEventRequest,
    V3TrainingSessionEventResponse,
    V3TrainingSessionStartRequest,
    V3TrainingSessionStartResponse,
)
from app.services.decision_state import build_decision_state
from app.services.multimodal_ingestion import MultimodalIngestionService
from app.services.policy_learning import PolicyLearningService
from app.services.training_coordination import TrainingCoordinationResult, TrainingCoordinationService
from app.services.training_system import TrainingSystemService


class AdaptiveTrainingSessionService:
    def __init__(self) -> None:
        self.training_system = TrainingSystemService()
        self.training_coordination = TrainingCoordinationService()
        self.ingestion_service = MultimodalIngestionService()
        self.policy_learning = PolicyLearningService()

    def start(self, db: Session, family: Family, payload: V3TrainingSessionStartRequest) -> V3TrainingSessionStartResponse:
        dashboard, coordination, trace_summary, context_signals = self._run_cycle(
            db=db,
            family=family,
            extra_context=payload.extra_context,
            ingestion_ids=payload.ingestion_ids,
            force_regenerate=payload.force_regenerate,
        )
        coordination_decision = self._coordination_decision(coordination, dashboard)
        active_plan_summary = self._active_plan_summary(dashboard, coordination_decision)
        session = AdaptiveSession(
            family_id=family.family_id,
            incident_id=None,
            chain="training_support",
            status="active",
            current_state_version=1,
            current_state_json=self._build_state_payload(
                payload=payload,
                dashboard=dashboard,
                coordination=coordination,
                coordination_decision=coordination_decision,
                trace_summary=trace_summary,
                context_signals=context_signals,
                adaptation_history=[],
            ),
            active_plan_summary_json=active_plan_summary,
            next_check_in_hint="执行后如果孩子更抗拒或你更累了，直接点“状态没改善”或“我需要更轻”。",
            last_trace_id=None,
        )
        db.add(session)
        db.flush()
        decision_state = self._decision_state_from_session(session)
        return V3TrainingSessionStartResponse(
            session=self._session_read(session),
            decision_state=decision_state,
            dashboard=dashboard,
            coordination=coordination_decision,
            trace_id=None,
            trace_summary=trace_summary,
        )

    def add_event(
        self,
        db: Session,
        family: Family,
        session: AdaptiveSession,
        payload: V3TrainingSessionEventRequest,
    ) -> V3TrainingSessionEventResponse:
        state = dict(session.current_state_json or {})
        base_payload = V3TrainingSessionStartRequest.model_validate(state["payload"])
        ingestion_ids = list(state.get("ingestion_ids", []))
        if payload.ingestion_id is not None and payload.ingestion_id not in ingestion_ids:
            ingestion_ids.append(payload.ingestion_id)
        merged_context = " ".join(part for part in [base_payload.extra_context, payload.raw_text.strip()] if part).strip()
        prefer_lighter = payload.event_kind in {"request_lighter", "caregiver_overloaded", "no_improvement"}

        dashboard, coordination, trace_summary, context_signals = self._run_cycle(
            db=db,
            family=family,
            extra_context=merged_context,
            ingestion_ids=ingestion_ids,
            force_regenerate=True,
            prefer_lighter=prefer_lighter,
        )
        coordination_decision = self._coordination_decision(coordination, dashboard)
        active_plan_summary = self._active_plan_summary(dashboard, coordination_decision)

        previous_dashboard = TrainingDashboardResponse.model_validate(state["dashboard"])
        changed_fields = self._changed_fields(previous_dashboard, dashboard, state.get("coordination_decision", {}), coordination_decision)

        event = SessionEvent(
            session_id=session.id,
            source_type=payload.source_type,
            event_kind=payload.event_kind,
            raw_text=payload.raw_text.strip(),
            ingestion_id=payload.ingestion_id,
            payload_json={"ingestion_ids": ingestion_ids},
            replanned=bool(changed_fields),
        )
        db.add(event)
        db.flush()

        session.current_state_version += 1
        session.current_state_json = self._build_state_payload(
            payload=base_payload.model_copy(update={"extra_context": merged_context}),
            dashboard=dashboard,
            coordination=coordination,
            coordination_decision=coordination_decision,
            trace_summary=trace_summary,
            context_signals=context_signals,
            adaptation_history=[
                *list(state.get("adaptation_history", [])),
                coordination.readiness_reason,
            ][-8:],
        )
        session.active_plan_summary_json = active_plan_summary
        session.next_check_in_hint = "先照当前最小动作执行；如果还是卡住，就继续请求更轻方案。"
        db.flush()
        return V3TrainingSessionEventResponse(
            session=self._session_read(session),
            event=self._event_read(event),
            replanned=bool(changed_fields),
            changed_fields=changed_fields,
            decision_state=self._decision_state_from_session(session),
            dashboard=dashboard,
            coordination=coordination_decision,
            trace_id=None,
            trace_summary=trace_summary,
        )

    def close(
        self,
        db: Session,
        family: Family,
        session: AdaptiveSession,
        payload: V3TrainingSessionCloseRequest,
    ) -> V3TrainingSessionCloseResponse:
        state = dict(session.current_state_json or {})
        dashboard = TrainingDashboardResponse.model_validate(state["dashboard"])
        coordination = CoordinationDecision.model_validate(state["coordination_decision"])
        outcome_score = {"helpful": 2, "somewhat": 1, "not_helpful": -1}[payload.effectiveness]
        emotion = state.get("emotion", {})
        self.policy_learning.record_adaptive_feedback(
            db=db,
            family_id=family.family_id,
            outcome_score=outcome_score,
            emotion_pattern=f"{emotion.get('child_emotion', 'unknown')}|{emotion.get('caregiver_emotion', 'unknown')}",
            overload_trigger=f"training|{state.get('readiness_status', 'ready')}",
            handoff_pattern="",
            adjustment_key=f"training:{coordination.active_mode}",
        )
        updated_weights = self.policy_learning.rebuild_card_weights(db=db, family_id=family.family_id)

        event = SessionEvent(
            session_id=session.id,
            source_type="system",
            event_kind="close",
            raw_text=payload.notes.strip() or payload.effectiveness,
            payload_json={"effectiveness": payload.effectiveness},
            replanned=False,
        )
        db.add(event)
        session.status = "closed"
        session.next_check_in_hint = "本次训练支持会话已关闭。系统会把今天的减负策略记到下次推荐里。"
        state["adaptation_history"] = [
            *list(state.get("adaptation_history", [])),
            payload.notes.strip() or "训练支持会话已结束。",
        ][-8:]
        session.current_state_json = state
        db.flush()
        return V3TrainingSessionCloseResponse(
            session=self._session_read(session),
            decision_state=self._decision_state_from_session(session),
            dashboard=dashboard,
            learning_summary=[
                f"今天的训练协调模式已记录：{state.get('readiness_status', 'ready')}",
                f"系统会记住这次{coordination.active_mode}方案的效果。",
            ],
            updated_weights=updated_weights,
        )

    def _run_cycle(
        self,
        *,
        db: Session,
        family: Family,
        extra_context: str,
        ingestion_ids: list[int],
        force_regenerate: bool,
        prefer_lighter: bool = False,
    ) -> tuple[TrainingDashboardResponse, TrainingCoordinationResult, list[DecisionGraphStageRun], list[ContextSignalRead]]:
        stage_runs: list[DecisionGraphStageRun] = []
        merged_context, valid_ingestion_ids = self.ingestion_service.merge_context(db, ingestion_ids)
        fused_context = " ".join(part for part in [extra_context.strip(), merged_context] if part).strip()
        context_signals: list[ContextSignalRead] = []
        for ingestion_id in valid_ingestion_ids:
            item = self.ingestion_service.get(db, ingestion_id)
            if item is not None:
                context_signals.extend(item.context_signals[:2])
        stage_runs.append(self._stage("context_ingestion", {"ingestion_ids": valid_ingestion_ids, "summary": merged_context}, "training-session"))
        stage_runs.append(
            self._stage(
                "context_fusion",
                {"summary": fused_context, "context_signals": [item.model_dump() for item in context_signals]},
                f"family:{family.family_id}",
            )
        )

        started = perf_counter()
        dashboard = self.training_system.get_dashboard(db=db, family=family, extra_context=fused_context, force_regenerate=force_regenerate)
        coordination = self.training_coordination.assess(
            db=db,
            family=family,
            extra_context=fused_context,
            proposed_load_level=dashboard.summary.current_load_level,
            prefer_lighter=prefer_lighter,
        )
        coordination_decision = self._coordination_decision(coordination, dashboard)
        stage_runs.append(self._stage("signal_eval", coordination.signal.model_dump(), f"family:{family.family_id}"))
        stage_runs.append(self._stage("emotion_eval", coordination.emotion.model_dump(), "training-context"))
        stage_runs.append(self._stage("coordination", coordination_decision.model_dump(), "training-coordinator"))
        stage_runs.append(
            self._stage(
                "policy_adjust_hint",
                {"used_memory_signals": coordination.used_memory_signals, "latency_ms": max(1, int((perf_counter() - started) * 1000))},
                f"family:{family.family_id}",
            )
        )
        stage_runs.append(
            self._stage(
                "finalizer",
                {"readiness_status": coordination.readiness_status, "task_count": len(dashboard.today_tasks)},
                "training-dashboard",
            )
        )
        return dashboard, coordination, stage_runs, context_signals[:6]

    def _coordination_decision(self, coordination: TrainingCoordinationResult, dashboard: TrainingDashboardResponse) -> CoordinationDecision:
        if dashboard.today_tasks:
            first_task = dashboard.today_tasks[0]
            now_step = first_task.steps[0]
            now_script = first_task.parent_script
            next_if_not_working = first_task.fallback_plan
        else:
            now_step = coordination.recommended_action
            now_script = coordination.readiness_reason
            next_if_not_working = "今天先暂停正式训练，改为低负荷陪伴或高摩擦支持。"
        return self.training_coordination.to_decision(
            result=coordination,
            now_step=now_step,
            now_script=now_script,
            next_if_not_working=next_if_not_working,
        )

    def _active_plan_summary(self, dashboard: TrainingDashboardResponse, coordination: CoordinationDecision) -> dict[str, Any]:
        first_task = dashboard.today_tasks[0] if dashboard.today_tasks else None
        return {
            "mode": coordination.active_mode,
            "summary": coordination.summary,
            "now_step": coordination.now_step,
            "now_script": coordination.now_script,
            "task_title": first_task.title if first_task else "",
            "today_goal": first_task.today_goal if first_task else dashboard.summary.recommended_action,
        }

    def _build_state_payload(
        self,
        *,
        payload: V3TrainingSessionStartRequest,
        dashboard: TrainingDashboardResponse,
        coordination: TrainingCoordinationResult,
        coordination_decision: CoordinationDecision,
        trace_summary: list[DecisionGraphStageRun],
        context_signals: list[ContextSignalRead],
        adaptation_history: list[str],
    ) -> dict[str, Any]:
        return {
            "payload": payload.model_dump(),
            "dashboard": dashboard.model_dump(),
            "risk": coordination.signal.model_dump(),
            "emotion": coordination.emotion.model_dump(),
            "coordination_decision": coordination_decision.model_dump(),
            "readiness_status": coordination.readiness_status,
            "used_memory_signals": coordination.used_memory_signals,
            "context_signals": [item.model_dump() for item in context_signals],
            "trace_summary": [item.model_dump() for item in trace_summary],
            "ingestion_ids": list(payload.ingestion_ids),
            "adaptation_history": adaptation_history,
        }

    def _changed_fields(
        self,
        previous_dashboard: TrainingDashboardResponse,
        next_dashboard: TrainingDashboardResponse,
        previous_coordination: dict[str, Any],
        next_coordination: CoordinationDecision,
    ) -> list[str]:
        changed: list[str] = []
        if previous_dashboard.summary.readiness_status != next_dashboard.summary.readiness_status:
            changed.append("readiness")
        if len(previous_dashboard.today_tasks) != len(next_dashboard.today_tasks):
            changed.append("task_count")
        previous_task = previous_dashboard.today_tasks[0].title if previous_dashboard.today_tasks else ""
        next_task = next_dashboard.today_tasks[0].title if next_dashboard.today_tasks else ""
        if previous_task != next_task:
            changed.append("task_focus")
        if previous_coordination.get("active_mode") != next_coordination.active_mode:
            changed.append("coordination")
        return changed

    def _decision_state_from_session(self, session: AdaptiveSession):
        state = dict(session.current_state_json or {})
        return build_decision_state(
            session_id=session.id,
            family_id=session.family_id,
            chain=session.chain,
            state_version=session.current_state_version,
            latest_inputs=dict(state.get("payload", {})),
            context_signals=[ContextSignalRead.model_validate(item) for item in state.get("context_signals", [])],
            risk_assessment=SignalOutput.model_validate(state["risk"]) if state.get("risk") else None,
            emotion_assessment=EmotionAssessment.model_validate(state["emotion"]) if state.get("emotion") else None,
            retrieval_bundle=None,
            coordination=CoordinationDecision.model_validate(state["coordination_decision"]),
            active_plan_summary=dict(session.active_plan_summary_json or {}),
            used_memory_signals=list(state.get("used_memory_signals", [])),
            adaptation_history=list(state.get("adaptation_history", [])),
            trace_summary=[DecisionGraphStageRun.model_validate(item) for item in state.get("trace_summary", [])],
        )

    def _session_read(self, session: AdaptiveSession) -> AdaptiveSessionRead:
        return AdaptiveSessionRead(
            session_id=session.id,
            incident_id=session.incident_id,
            family_id=session.family_id,
            chain=session.chain,  # type: ignore[arg-type]
            status=session.status,  # type: ignore[arg-type]
            current_state_version=session.current_state_version,
            active_plan_summary=session.active_plan_summary_json,
            next_check_in_hint=session.next_check_in_hint,
            last_trace_id=session.last_trace_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def _event_read(self, event: SessionEvent) -> SessionEventRead:
        return SessionEventRead(
            event_id=event.id,
            source_type=event.source_type,  # type: ignore[arg-type]
            event_kind=event.event_kind,  # type: ignore[arg-type]
            raw_text=event.raw_text,
            ingestion_id=event.ingestion_id,
            replanned=event.replanned,
            created_at=event.created_at,
        )

    def _stage(self, stage: str, output: dict[str, Any], input_ref: str) -> DecisionGraphStageRun:
        return DecisionGraphStageRun(
            stage=stage,  # type: ignore[arg-type]
            status="success",
            input_ref=input_ref,
            output=output,
            latency_ms=1,
            fallback_used=False,
            retry_count=0,
        )
