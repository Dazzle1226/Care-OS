from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from sqlalchemy.orm import Session

from app.models import ChildProfile, Family, StrategyCard
from app.schemas.domain import (
    MicroRespiteGenerateRequest,
    MicroRespiteOption,
    MicroRespitePlan,
    SignalOutput,
)
from app.services.retrieval import RetrievalService


@dataclass(slots=True)
class RespiteState:
    low_stim_only: bool
    intensity: str
    max_duration_minutes: int


@dataclass(slots=True)
class RespiteCandidate:
    score: float
    option: MicroRespiteOption


class RespiteAgent:
    def generate_plan(
        self,
        db: Session,
        family: Family,
        signal: SignalOutput,
        payload: MicroRespiteGenerateRequest,
    ) -> MicroRespitePlan:
        profile = family.child_profile
        state = self._derive_state(payload, signal)
        cards = self._retrieve_cards(db=db, family=family, profile=profile, payload=payload, state=state)
        if not cards:
            raise ValueError("No respite strategy cards available")

        card_pool = self._card_iterator(cards)
        candidates = [
            self._build_quiet_anchor(payload, profile, state, next(card_pool)),
            self._build_task_free_reset(payload, profile, state, next(card_pool)),
        ]

        if payload.support_available != "none":
            candidates.append(self._build_support_handoff(payload, profile, state, next(card_pool)))
        elif (
            payload.child_emotional_state in {"calm", "fragile"}
            and payload.sensory_overload_level != "heavy"
            and payload.meltdown_count <= 1
        ):
            candidates.append(self._build_independent_station(payload, profile, state, next(card_pool)))
        else:
            candidates.append(self._build_co_regulation_reset(payload, profile, state, next(card_pool)))

        if payload.transition_difficulty >= 6:
            candidates.append(self._build_transition_buffer(payload, profile, state, next(card_pool)))

        if (
            not state.low_stim_only
            and (
                payload.caregiver_stress <= 6
                and payload.child_emotional_state in {"calm", "fragile"}
                and payload.sensory_overload_level != "heavy"
            )
        ):
            candidates.append(self._build_breathing_reset(payload, profile, state, next(card_pool)))

        candidates.sort(key=lambda item: item.score, reverse=True)
        options: list[MicroRespiteOption] = []
        seen_option_ids: set[str] = set()
        for candidate in candidates:
            if candidate.option.option_id in seen_option_ids:
                continue
            seen_option_ids.add(candidate.option.option_id)
            options.append(candidate.option)
            if len(options) == 3:
                break

        while len(options) < 3:
            fallback = self._build_task_free_reset(payload, profile, state, next(card_pool), suffix=f"_{len(options) + 1}")
            options.append(fallback.option)

        return MicroRespitePlan(
            headline=self._headline(payload, state),
            context_summary=self._context_summary(payload, signal, state),
            low_stimulation_only=state.low_stim_only,
            safety_notes=self._plan_safety_notes(payload, profile, state),
            options=options[:3],
            feedback_prompt="完成后告诉我是否有效、是否符合预期；系统会据此调整下次排序和时长。",
        )

    def _derive_state(self, payload: MicroRespiteGenerateRequest, signal: SignalOutput) -> RespiteState:
        low_stim_only = (
            payload.caregiver_stress >= 8
            or payload.child_emotional_state in {"escalating", "meltdown_risk"}
            or payload.sensory_overload_level in {"medium", "heavy"}
            or payload.meltdown_count >= 2
            or signal.risk_level == "red"
        )

        if payload.child_emotional_state == "meltdown_risk" or payload.sensory_overload_level == "heavy":
            intensity = "heavy"
        elif low_stim_only or payload.transition_difficulty >= 7 or payload.caregiver_stress >= 7:
            intensity = "medium"
        else:
            intensity = "light"

        base_duration = {"none": 15, "one": 20, "two_plus": 30}[payload.support_available]
        if low_stim_only and payload.support_available == "none":
            base_duration = 10

        return RespiteState(
            low_stim_only=low_stim_only,
            intensity=intensity,
            max_duration_minutes=base_duration,
        )

    def _retrieve_cards(
        self,
        db: Session,
        family: Family,
        profile: ChildProfile | None,
        payload: MicroRespiteGenerateRequest,
        state: RespiteState,
    ) -> list[StrategyCard]:
        retrieval = RetrievalService(db)
        context = " ".join(
            [
                "respite",
                payload.child_emotional_state,
                payload.sensory_overload_level,
                f"stress:{payload.caregiver_stress:g}",
                f"transition:{payload.transition_difficulty:g}",
                f"meltdown:{payload.meltdown_count}",
                " ".join(getattr(profile, "soothing_methods", [])[:2]),
                " ".join(getattr(profile, "triggers", [])[:2]),
                payload.notes,
            ]
        ).strip()

        ranked = retrieval.retrieve_cards(
            family_id=family.family_id,
            scenario="respite",
            intensity=state.intensity,
            profile=profile,
            extra_context=context,
            top_k=64,
        )
        respite_cards = [card for card in ranked if "respite" in card.scenario_tags]
        if not respite_cards:
            respite_cards = ranked

        risk_order = {"low": 0, "medium": 1, "high": 2}
        if state.low_stim_only:
            low_only = [card for card in respite_cards if card.risk_level == "low"]
            if low_only:
                respite_cards = low_only

        respite_cards.sort(
            key=lambda card: (
                risk_order.get(card.risk_level, 1),
                0 if card.cost_level == "low" else 1,
            )
        )
        return respite_cards[:6]

    @staticmethod
    def _card_iterator(cards: list[StrategyCard]) -> Iterator[StrategyCard]:
        idx = 0
        while True:
            yield cards[idx % len(cards)]
            idx += 1

    @staticmethod
    def _pick(values: list[str] | None, default: str, idx: int = 0) -> str:
        if not values:
            return default
        if idx >= len(values):
            return values[-1]
        return values[idx]

    @staticmethod
    def _label_emotion(value: str) -> str:
        return {
            "calm": "平稳",
            "fragile": "脆弱易波动",
            "escalating": "正在升级",
            "meltdown_risk": "接近失控",
        }.get(value, value)

    @staticmethod
    def _label_sensory(value: str) -> str:
        return {
            "none": "无",
            "light": "轻微",
            "medium": "中等",
            "heavy": "严重",
        }.get(value, value)

    @staticmethod
    def _label_support(value: str) -> str:
        return {
            "none": "无人可接手",
            "one": "有 1 位支持者",
            "two_plus": "有 2 位以上支持者",
        }.get(value, value)

    def _base_safety_notes(self, card: StrategyCard, profile: ChildProfile | None, state: RespiteState) -> list[str]:
        primary_dont = self._pick(getattr(profile, "donts", []), "不要强拉身体")
        notes = [
            f"先遵守孩子禁忌：{primary_dont}。",
            "只做可随时中断的低门槛活动，出现升级立即结束。",
        ]
        if state.low_stim_only:
            notes.append("今天不安排高强度运动、长时间独处或复杂外出。")
        elif card.risk_level == "high":
            notes.append("这条建议风险较高，需要先人工复核再执行。")
        else:
            notes.append("先把灯光、噪音和指令量降下来，再开始计时。")
        return notes[:3]

    def _support_plan(self, payload: MicroRespiteGenerateRequest, state: RespiteState, short_text: str) -> str:
        if payload.support_available == "none":
            return f"当前{self._label_support(payload.support_available)}，{short_text}"
        return f"{self._label_support(payload.support_available)}，交接前先说清触发点、安抚方式和返回时间。"

    def _candidate_option(
        self,
        *,
        option_id: str,
        title: str,
        summary: str,
        fit_reason: str,
        duration_minutes: int,
        child_focus: str,
        parent_focus: str,
        setup_steps: list[str],
        instructions: list[str],
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
    ) -> MicroRespiteOption:
        return MicroRespiteOption(
            option_id=option_id,
            title=title,
            summary=summary,
            fit_reason=fit_reason,
            duration_minutes=min(duration_minutes, state.max_duration_minutes),
            child_focus=child_focus,
            parent_focus=parent_focus,
            setup_steps=setup_steps[:4],
            instructions=instructions[:4],
            safety_notes=self._base_safety_notes(card, profile, state),
            support_plan=self._support_plan(payload, state, "建议把时长控制在 10-15 分钟，并保持可见范围。"),
            source_card_ids=[card.card_id],
            low_stimulation_only=state.low_stim_only,
            requires_manual_review=card.risk_level == "high",
        )

    def _build_quiet_anchor(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
    ) -> RespiteCandidate:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        trigger = self._pick(getattr(profile, "triggers", []), "过渡")
        duration = 10 if state.low_stim_only else 15
        score = 3.0
        if state.low_stim_only:
            score += 2.0
        if payload.sensory_overload_level in {"medium", "heavy"}:
            score += 1.2
        if payload.child_emotional_state in {"escalating", "meltdown_risk"}:
            score += 1.0

        option = self._candidate_option(
            option_id="quiet_anchor",
            title="安静角落并行喘息",
            summary=f"先让孩子在 {soothing_place} 附近稳定下来，家长只做陪伴与恢复，不再推进任务。",
            fit_reason=f"当前孩子情绪{self._label_emotion(payload.child_emotional_state)}、感官负荷{self._label_sensory(payload.sensory_overload_level)}，适合先降刺激。",
            duration_minutes=duration,
            child_focus=f"孩子只做一个安静动作，比如待在 {soothing_place}、翻绘本或摆弄熟悉物品。",
            parent_focus="家长坐在一臂距离内，先喝水、放松肩膀，不解释、不教学。",
            setup_steps=[
                "先把灯光、声音和围观者降到最少。",
                f"用一句话预告：先到 {soothing_place} 待一会儿。",
                "把计时器调到可见但不刺眼。",
            ],
            instructions=[
                "只给两个低刺激选项，不追问原因。",
                "若孩子愿意，重复一个熟悉安抚动作 2-3 次。",
                f"把今天最容易卡住的点暂时搁置，尤其是 {trigger} 相关要求。",
            ],
            payload=payload,
            profile=profile,
            state=state,
            card=card,
        )
        return RespiteCandidate(score=score, option=option)

    def _build_support_handoff(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
    ) -> RespiteCandidate:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        dont = self._pick(getattr(profile, "donts", []), "不要强拉身体")
        duration = 20 if payload.support_available == "one" else 30
        score = 2.8
        if payload.caregiver_stress >= 7:
            score += 1.5
        if payload.caregiver_sleep_quality <= 4:
            score += 1.0
        if payload.support_available == "two_plus":
            score += 0.5

        option = self._candidate_option(
            option_id="support_handoff",
            title="家人接手微喘息",
            summary="既然今天有人能接手，就把恢复时间换成真正离场，不在场解决问题。",
            fit_reason="你当前压力偏高且有支持者在场，最有效的不是硬扛，而是做一次完整交接。",
            duration_minutes=duration,
            child_focus=f"支持者只带孩子做一项熟悉的低刺激活动，比如去 {soothing_place} 或使用固定安抚物。",
            parent_focus="家长离开主要刺激源，不处理消息、不做决定，只做恢复。",
            setup_steps=[
                "交接前用 30 秒说清触发点、安抚方式和不能做的事。",
                "明确返回时间，并约定只在升级时联系你。",
                "把今天暂停的任务一并交代成“先不做”。",
            ],
            instructions=[
                f"支持者先复述一遍禁忌：{dont}。",
                "家长离场后至少前 10 分钟不回头干预。",
                "结束前 2 分钟再由支持者做过渡预告，避免突然切换。",
            ],
            payload=payload,
            profile=profile,
            state=state,
            card=card,
        )
        return RespiteCandidate(score=score, option=option)

    def _build_independent_station(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
    ) -> RespiteCandidate:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静桌")
        duration = 15 if payload.support_available == "none" else 20
        score = 1.6
        if payload.child_emotional_state == "calm":
            score += 1.8
        if payload.child_emotional_state == "fragile":
            score += 0.8
        if payload.sensory_overload_level in {"none", "light"}:
            score += 0.7
        if payload.meltdown_count == 0:
            score += 0.5

        option = self._candidate_option(
            option_id="independent_station",
            title="孩子独立安静盒",
            summary="当孩子相对稳定时，把活动缩到一个安静盒里，家长在旁边短暂休整。",
            fit_reason="当前孩子还处在可引导区间，可以尝试短时独立活动，但仍保持可见范围。",
            duration_minutes=duration,
            child_focus=f"孩子在 {soothing_place} 做一件熟悉的小活动，例如贴纸、拼图或翻书。",
            parent_focus="家长坐在同一区域休息，不开启新任务，不趁机补工作。",
            setup_steps=[
                "提前把活动限制为 1 盒 / 1 本 / 1 样玩具。",
                "先说清楚什么时候结束，并把计时器放在孩子能看到的位置。",
            ],
            instructions=[
                "先确认孩子愿意开始，再退到旁边的位置。",
                "中途只做一次简短提醒，不连续催促。",
                "结束后立刻回到熟悉流程，不临时追加任务。",
            ],
            payload=payload,
            profile=profile,
            state=state,
            card=card,
        )
        return RespiteCandidate(score=score, option=option)

    def _build_co_regulation_reset(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
    ) -> RespiteCandidate:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        score = 2.4
        if payload.child_emotional_state in {"escalating", "meltdown_risk"}:
            score += 1.4
        if payload.sensory_overload_level in {"medium", "heavy"}:
            score += 1.0

        option = self._candidate_option(
            option_id="co_regulation_reset",
            title="低刺激共处喘息",
            summary="孩子现在不适合长时间独立，先做一段低刺激共处，家长只保安全和陪伴。",
            fit_reason="当前孩子波动较大，没有支持者时，最稳妥的是把要求降到最低，先一起稳定下来。",
            duration_minutes=10,
            child_focus=f"孩子留在 {soothing_place} 附近，只做熟悉且可中断的安静动作。",
            parent_focus="家长不离场、不教学，只用短句陪伴并让身体慢下来。",
            setup_steps=[
                "先取消这一段时间里的新要求和新任务。",
                f"把孩子带到 {soothing_place} 或其他熟悉低刺激位置。",
            ],
            instructions=[
                "只做陪伴和观察，不连续讲话。",
                "若孩子需要，重复一个熟悉安抚动作或固定句子。",
                "10 分钟后再判断是否进入下一步，而不是立刻恢复原计划。",
            ],
            payload=payload,
            profile=profile,
            state=state,
            card=card,
        )
        return RespiteCandidate(score=score, option=option)

    def _build_transition_buffer(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
    ) -> RespiteCandidate:
        trigger = self._pick(getattr(profile, "triggers", []), "过渡")
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "固定等待点")
        score = 2.1 + (payload.transition_difficulty / 10)

        option = self._candidate_option(
            option_id="transition_buffer",
            title="过渡缓冲微喘息",
            summary="今天最容易卡住的是切换，不如先做一次过渡缓冲，把下一次爆点降下来。",
            fit_reason=f"过渡难度 {payload.transition_difficulty:g}/10，先处理 {trigger} 比直接硬撑更划算。",
            duration_minutes=12,
            child_focus=f"孩子先在 {soothing_place} 完成一个固定的“结束前动作”。",
            parent_focus="家长趁固定动作进行时坐下休息，不额外讲道理。",
            setup_steps=[
                "把下一件事缩成“先做一步”。",
                "准备一个 first/then 提示或简单口头预告。",
            ],
            instructions=[
                "先用一句话说清现在和下一步，不展开解释。",
                "给两个可接受选项，让孩子选切换方式。",
                "完成这次缓冲后，再决定是否继续原计划。",
            ],
            payload=payload,
            profile=profile,
            state=state,
            card=card,
        )
        return RespiteCandidate(score=score, option=option)

    def _build_breathing_reset(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
    ) -> RespiteCandidate:
        score = 1.8
        if 3 <= payload.caregiver_stress <= 6:
            score += 1.2
        if payload.child_emotional_state == "calm":
            score += 0.8

        option = self._candidate_option(
            option_id="breathing_reset",
            title="短时呼气 / 冥想重置",
            summary="只有在孩子相对稳定、家长还扛得住时，才值得做一轮短时呼气或冥想。",
            fit_reason="当前家长压力还没到极限，短时呼吸练习更可能真正起效。",
            duration_minutes=12,
            child_focus="孩子做一项熟悉且安静的短活动，家长不离开可见范围。",
            parent_focus="家长做 4 轮长呼气，或跟着 5 分钟引导音频闭眼休息。",
            setup_steps=[
                "先确认孩子此刻是平稳或可等待的状态。",
                "把手机调成勿扰，只保留计时器。",
            ],
            instructions=[
                "先做 1 分钟长呼气，再决定是否继续到 5-12 分钟。",
                "一旦听到孩子升级，立即结束练习，不勉强撑满时间。",
                "结束后先喝水，再回到孩子身边。",
            ],
            payload=payload,
            profile=profile,
            state=state,
            card=card,
        )
        option.low_stimulation_only = False
        return RespiteCandidate(score=score, option=option)

    def _build_task_free_reset(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
        card: StrategyCard,
        suffix: str = "",
    ) -> RespiteCandidate:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "固定座位")
        score = 2.2
        if payload.caregiver_stress >= 7:
            score += 1.2
        if payload.caregiver_sleep_quality <= 4:
            score += 1.0

        option = self._candidate_option(
            option_id=f"task_free_reset{suffix}",
            title="任务清零恢复",
            summary="如果你现在已经很累，最有效的微喘息通常不是“做点什么”，而是把任务全部清零 10 分钟。",
            fit_reason="家长压力或睡眠状态偏差时，越简单、越无任务的恢复越容易执行。",
            duration_minutes=10,
            child_focus=f"孩子留在 {soothing_place} 附近，只保持安全和低刺激，不新增要求。",
            parent_focus="家长只做 3 件事：坐下、补水、闭嘴，不刷消息不处理待办。",
            setup_steps=[
                "把接下来 10 分钟的任务全部延期。",
                "准备水、纸巾或热毛巾，坐到固定位置。",
            ],
            instructions=[
                "先把身体停下来，再决定是否继续今天的事。",
                "如果孩子来找你，只用短句回应，不重新展开任务。",
                "10 分钟后只恢复一个最小目标。",
            ],
            payload=payload,
            profile=profile,
            state=state,
            card=card,
        )
        return RespiteCandidate(score=score, option=option)

    def _headline(self, payload: MicroRespiteGenerateRequest, state: RespiteState) -> str:
        if state.low_stim_only:
            return "先保低刺激，再挤出一小段恢复时间"
        if payload.support_available != "none":
            return "今天适合做一次可交接的微喘息"
        return "今天以短时、低门槛的微喘息为主"

    def _context_summary(
        self,
        payload: MicroRespiteGenerateRequest,
        signal: SignalOutput,
        state: RespiteState,
    ) -> str:
        low_stim_text = "仅推荐低刺激方案" if state.low_stim_only else "可尝试短时恢复方案"
        return (
            f"家长压力 {payload.caregiver_stress:g}/10，睡眠质量 {payload.caregiver_sleep_quality:g}/10；"
            f"孩子情绪 {self._label_emotion(payload.child_emotional_state)}，感官负荷 {self._label_sensory(payload.sensory_overload_level)}，"
            f"过渡难度 {payload.transition_difficulty:g}/10，冲突 {payload.meltdown_count} 次。"
            f"综合今日风险 {signal.risk_level}，{low_stim_text}。"
        )

    def _plan_safety_notes(
        self,
        payload: MicroRespiteGenerateRequest,
        profile: ChildProfile | None,
        state: RespiteState,
    ) -> list[str]:
        dont = self._pick(getattr(profile, "donts", []), "不要强拉身体")
        notes = [
            f"所有建议都优先遵守孩子禁忌：{dont}。",
            "若出现持续升级、自伤或他伤风险，立即停止微喘息并切换到安全处置。",
        ]
        if state.low_stim_only:
            notes.append("今天不会推荐高强度运动、长时间独立活动或刺激性外出。")
        else:
            notes.append("若支持者接手，请先完成交接再离场，不做突然消失。")
        return notes[:3]
