from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.respite import RespiteAgent
from app.models import ChildProfile, Family, Review, StrategyCard
from app.schemas.domain import (
    FrictionRespiteSuggestion,
    FrictionSupportGenerateRequest,
    FrictionSupportPlan,
    FrictionSupportStep,
    MicroRespiteGenerateRequest,
    SignalOutput,
)
from app.services.retrieval import RetrievalService


@dataclass(slots=True)
class FrictionState:
    intensity: str
    low_stim_only: bool
    retrieval_scenario: str
    needs_fast_exit: bool


class FrictionAgent:
    scenario_labels = {
        "transition": "过渡",
        "bedtime": "睡前",
        "homework": "作业",
        "outing": "外出",
        "meltdown": "情绪失控",
    }
    child_state_labels = {
        "emotional_wave": "情绪波动明显",
        "sensory_overload": "感官过载",
        "conflict": "冲突正在升级",
        "meltdown": "已经接近或进入崩溃",
        "transition_block": "卡在过渡点",
    }
    sensory_labels = {
        "none": "无",
        "light": "轻微",
        "medium": "中等",
        "heavy": "严重",
    }
    support_labels = {
        "none": "当前无人可接手",
        "one": "当前有 1 位支持者",
        "two_plus": "当前有 2 位以上支持者",
    }

    def generate_support(
        self,
        db: Session,
        family: Family,
        signal: SignalOutput,
        payload: FrictionSupportGenerateRequest,
    ) -> FrictionSupportPlan:
        profile = family.child_profile
        state = self._derive_state(payload, signal)
        cards = self._retrieve_cards(db=db, family=family, profile=profile, payload=payload, state=state)
        if not cards:
            raise ValueError("No friction support cards available")

        respite = self._build_respite_suggestion(db=db, family=family, signal=signal, payload=payload)

        return FrictionSupportPlan(
            headline=self._headline(payload, signal, state),
            situation_summary=self._situation_summary(payload, signal),
            child_signals=self._child_signals(payload),
            caregiver_signals=self._caregiver_signals(payload),
            action_plan=self._action_plan(cards=cards, profile=profile, payload=payload, state=state),
            voice_guidance=self._voice_guidance(payload, state),
            exit_plan=self._exit_plan(profile=profile, payload=payload, state=state),
            respite_suggestion=respite,
            personalized_strategies=self._personalized_strategies(db=db, cards=cards, profile=profile, payload=payload),
            school_message=self._school_message(cards=cards, profile=profile, payload=payload),
            feedback_prompt="执行 5-10 分钟后告诉我：孩子是否更稳定、你是否更能跟住方案；系统会据此调整下次推荐顺序。",
            citations=[card.card_id for card in cards],
            source_card_ids=[card.card_id for card in cards],
        )

    def _derive_state(self, payload: FrictionSupportGenerateRequest, signal: SignalOutput) -> FrictionState:
        low_stim_only = (
            payload.child_state in {"sensory_overload", "meltdown"}
            or payload.sensory_overload_level in {"medium", "heavy"}
            or payload.meltdown_count >= 2
            or payload.caregiver_stress >= 8
            or signal.risk_level == "red"
        )

        if payload.child_state == "meltdown" or payload.sensory_overload_level == "heavy":
            intensity = "heavy"
        elif low_stim_only or payload.transition_difficulty >= 7 or payload.caregiver_fatigue >= 7:
            intensity = "medium"
        else:
            intensity = "light"

        retrieval_scenario = payload.scenario
        if retrieval_scenario == "meltdown":
            retrieval_scenario = "outing" if payload.sensory_overload_level in {"medium", "heavy"} else "transition"

        needs_fast_exit = (
            payload.child_state in {"conflict", "meltdown"}
            or payload.caregiver_stress >= 9
            or payload.confidence_to_follow_plan <= 3
        )
        return FrictionState(
            intensity=intensity,
            low_stim_only=low_stim_only,
            retrieval_scenario=retrieval_scenario,
            needs_fast_exit=needs_fast_exit,
        )

    def _retrieve_cards(
        self,
        db: Session,
        family: Family,
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
        state: FrictionState,
    ) -> list[StrategyCard]:
        retrieval = RetrievalService(db)
        context = " ".join(
            [
                self.child_state_labels[payload.child_state],
                self.sensory_labels[payload.sensory_overload_level],
                f"transition:{payload.transition_difficulty:g}",
                f"meltdown:{payload.meltdown_count}",
                f"stress:{payload.caregiver_stress:g}",
                f"fatigue:{payload.caregiver_fatigue:g}",
                " ".join(payload.env_changes[:3]),
                " ".join(getattr(profile, "triggers", [])[:2]),
                " ".join(getattr(profile, "soothing_methods", [])[:2]),
                payload.free_text,
            ]
        ).strip()

        return retrieval.compose_plan_cards(
            family_id=family.family_id,
            scenario=state.retrieval_scenario,
            intensity=state.intensity,
            profile=profile,
            extra_context=context,
            max_cards=3,
        )

    def _headline(self, payload: FrictionSupportGenerateRequest, signal: SignalOutput, state: FrictionState) -> str:
        scenario_label = self.scenario_labels[payload.scenario]
        if state.low_stim_only:
            return f"{scenario_label}高摩擦时刻：先保安全，再降刺激"
        if signal.risk_level == "yellow":
            return f"{scenario_label}高摩擦时刻：先稳住，再推进下一步"
        return f"{scenario_label}高摩擦时刻：先给清晰步骤，不讲道理"

    def _situation_summary(self, payload: FrictionSupportGenerateRequest, signal: SignalOutput) -> str:
        reason = signal.reasons[0] if signal.reasons else "当前负荷偏高"
        return (
            f"{reason}。孩子当前{self.child_state_labels[payload.child_state]}，感官负荷"
            f"{self.sensory_labels[payload.sensory_overload_level]}，过渡难度 {payload.transition_difficulty:g}/10；"
            f"家长压力 {payload.caregiver_stress:g}/10，疲劳 {payload.caregiver_fatigue:g}/10。"
        )

    def _child_signals(self, payload: FrictionSupportGenerateRequest) -> list[str]:
        return [
            f"当前状态：{self.child_state_labels[payload.child_state]}",
            f"感官负荷：{self.sensory_labels[payload.sensory_overload_level]}",
            f"今日冲突/崩溃 {payload.meltdown_count} 次，过渡难度 {payload.transition_difficulty:g}/10",
        ]

    def _caregiver_signals(self, payload: FrictionSupportGenerateRequest) -> list[str]:
        return [
            f"家长压力 {payload.caregiver_stress:g}/10，疲劳 {payload.caregiver_fatigue:g}/10",
            f"睡眠质量 {payload.caregiver_sleep_quality:g}/10，执行信心 {payload.confidence_to_follow_plan:g}/10",
            self.support_labels[payload.support_available],
        ]

    @staticmethod
    def _clean_step_text(text: str) -> str:
        return text.split("：", 1)[-1].strip() if "：" in text else text.strip()

    @staticmethod
    def _pick(values: list[str] | None, default: str, idx: int = 0) -> str:
        if not values:
            return default
        if idx >= len(values):
            return values[-1]
        return values[idx]

    def _step_titles(self, state: FrictionState) -> list[str]:
        first = "先停住并降刺激" if state.low_stim_only else "先停住当前任务"
        return [first, "给边界和两个选择", "切到恢复或收尾"]

    def _action_plan(
        self,
        cards: list[StrategyCard],
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
        state: FrictionState,
    ) -> list[FrictionSupportStep]:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        base_scripts = [
            "我在这里，你是安全的，我们先停一下。",
            "现在只做一个小选择：你想自己来，还是我陪你一起？",
            f"这件事先暂停，我们先去 {soothing_place}，等身体稳下来再回来。",
        ]
        why_bits = [
            f"孩子现在{self.child_state_labels[payload.child_state]}，先降刺激比解释更有效。",
            "高摩擦时刻大脑更难处理长指令，缩成一个边界加两个选项更容易跟上。",
            "如果前两步仍无效，先保护关系和安全，不要硬把任务做完。",
        ]
        action_suffix = [
            "先把灯光、声音和围观者降下来，只保留一个要求。",
            "说完后等 5 秒，不追问、不补充第二段解释。",
            f"若仍卡住，直接转去 {soothing_place} 或执行退场。",
        ]

        plan: list[FrictionSupportStep] = []
        titles = self._step_titles(state)
        for idx, card in enumerate(cards[:3]):
            raw_step = card.steps_json[min(idx, len(card.steps_json) - 1)] if card.steps_json else "先把目标缩成一步。"
            action = f"{self._clean_step_text(raw_step)} {action_suffix[idx]}".strip()
            script = card.scripts_json.get("parent") if idx == 0 else base_scripts[idx]
            if not script:
                script = base_scripts[idx]
            plan.append(
                FrictionSupportStep(
                    title=titles[idx],
                    action=action,
                    parent_script=script,
                    why_it_fits=why_bits[idx],
                )
            )

        while len(plan) < 3:
            idx = len(plan)
            plan.append(
                FrictionSupportStep(
                    title=titles[idx],
                    action=action_suffix[idx],
                    parent_script=base_scripts[idx],
                    why_it_fits=why_bits[idx],
                )
            )
        return plan[:3]

    def _voice_guidance(self, payload: FrictionSupportGenerateRequest, state: FrictionState) -> list[str]:
        third_line = "如果继续升级，直接执行退场，不跟孩子争输赢。" if state.needs_fast_exit else "只推进下一步，不要同时处理三个问题。"
        if payload.support_available != "none" and payload.caregiver_stress >= 7:
            third_line = "如果你开始跟不上节奏，马上让支持者接手 10-15 分钟。"
        return [
            "先停 5 秒，放低音量，只说一句话。",
            "现在的目标不是讲清道理，而是让身体先降下来。",
            third_line,
        ]

    def _exit_plan(
        self,
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
        state: FrictionState,
    ) -> list[str]:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        support_line = (
            "如果孩子和你都还在升级，立即联系支持者接手 10-15 分钟。"
            if payload.support_available != "none"
            else "如果你也快失控，先把要求全部暂停，留在可见范围内做最小陪伴。"
        )
        return [
            "立刻停止当前要求，移开围观者和额外刺激源。",
            f"带孩子去 {soothing_place} 或其他安静处，只重复同一句安抚话。",
            support_line if state.needs_fast_exit else "若 10 分钟后仍不稳，直接转入低刺激恢复，不再坚持原任务。",
        ]

    def _map_child_emotion(self, child_state: str) -> str:
        return {
            "emotional_wave": "fragile",
            "sensory_overload": "escalating",
            "conflict": "escalating",
            "meltdown": "meltdown_risk",
            "transition_block": "fragile",
        }[child_state]

    def _build_respite_suggestion(
        self,
        db: Session,
        family: Family,
        signal: SignalOutput,
        payload: FrictionSupportGenerateRequest,
    ) -> FrictionRespiteSuggestion:
        try:
            plan = RespiteAgent().generate_plan(
                db=db,
                family=family,
                signal=signal,
                payload=MicroRespiteGenerateRequest(
                    family_id=payload.family_id,
                    caregiver_stress=payload.caregiver_stress,
                    caregiver_sleep_quality=payload.caregiver_sleep_quality,
                    support_available=payload.support_available,
                    child_emotional_state=self._map_child_emotion(payload.child_state),
                    sensory_overload_level=payload.sensory_overload_level,
                    transition_difficulty=payload.transition_difficulty,
                    meltdown_count=payload.meltdown_count,
                    notes=payload.free_text,
                    high_risk_selected=payload.high_risk_selected,
                ),
            )
            option = plan.options[0]
            return FrictionRespiteSuggestion(
                title=option.title,
                summary=option.summary,
                duration_minutes=option.duration_minutes,
                support_plan=option.support_plan,
            )
        except ValueError:
            duration = 15 if payload.support_available == "none" else 20
            return FrictionRespiteSuggestion(
                title="短时降负荷喘息",
                summary="先把目标降到只保留安全与陪伴，给家长一个可控的恢复窗口。",
                duration_minutes=duration,
                support_plan=self.support_labels[payload.support_available],
            )

    def _history_effect_map(self, db: Session, family_id: int) -> dict[str, float]:
        rows = db.scalars(select(Review).where(Review.family_id == family_id)).all()
        grouped: dict[str, list[int]] = defaultdict(list)
        for review in rows:
            for card_id in review.card_ids:
                grouped[card_id].append(review.outcome_score)
        result: dict[str, float] = {}
        for card_id, scores in grouped.items():
            result[card_id] = sum(scores) / len(scores) if scores else 0.0
        return result

    def _personalized_strategies(
        self,
        db: Session,
        cards: list[StrategyCard],
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
    ) -> list[str]:
        notes: list[str] = []
        soothing = getattr(profile, "soothing_methods", [])
        triggers = getattr(profile, "triggers", [])
        if soothing:
            notes.append(f"孩子平时更容易被“{soothing[0]}”带回稳定，今天把它提前到前 5 分钟。")
        if triggers:
            notes.append(f"你们家常见触发点包括“{triggers[0]}”，现在先别追加解释和催促。")
        if payload.env_changes:
            notes.append(f"今天还有环境变化：{'、'.join(payload.env_changes[:2])}，先把非必要要求降一级。")

        history = self._history_effect_map(db=db, family_id=payload.family_id)
        positive = next((card for card in cards if history.get(card.card_id, 0.0) > 0.5), None)
        negative = next((card for card in cards if history.get(card.card_id, 0.0) < 0), None)
        if positive is not None:
            notes.append(f"历史反馈里，{positive.title} 这类做法更常有效，本次继续优先保留。")
        elif negative is not None:
            notes.append(f"过去对 {negative.title} 的反馈一般，这次若 5 分钟无效就尽快切换退场。")

        if len(notes) < 2:
            notes.append("如果第一轮没起效，不要连续换很多说法，先减少目标再重复同一句提示。")
        if len(notes) < 3:
            notes.append("先追求情绪回稳，不追求把事情一次做完。")
        return notes[:4]

    def _school_message(
        self,
        cards: list[StrategyCard],
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
    ) -> str:
        teacher_script = next((card.scripts_json.get("teacher", "") for card in cards if card.scripts_json.get("teacher")), "")
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        env_note = ""
        if payload.env_changes:
            env_note = f" 今天还有{'、'.join(payload.env_changes[:2])}等变化，请减少临时调整。"
        return (
            f"今天孩子在{self.scenario_labels[payload.scenario]}场景负荷偏高，请统一采用短句、先预告再切换的方式。"
            f"{teacher_script} 若出现升级，请先降噪、给两个选项，并允许去 {soothing_place} 缓冲 5-10 分钟。"
            f"{env_note}"
        ).strip()
