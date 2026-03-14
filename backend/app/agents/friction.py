from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.respite import RespiteAgent
from app.models import ChildProfile, Family, Review, StrategyCard
from app.schemas.domain import (
    FRICTION_PRESET_LABELS,
    FrictionCrisisCard,
    FrictionLowStimMode,
    FrictionRespiteSuggestion,
    FrictionSupportGenerateRequest,
    FrictionSupportPlan,
    FrictionSupportStep,
    MicroRespiteGenerateRequest,
    PlanMessage,
    RetrievalEvidenceBundle,
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
        cards: list[StrategyCard] | None = None,
        evidence_bundle: RetrievalEvidenceBundle | None = None,
    ) -> FrictionSupportPlan:
        profile = family.child_profile
        state = self._derive_state(payload, signal)
        selected_cards = cards or self._retrieve_cards(db=db, family=family, profile=profile, payload=payload, state=state)
        if not selected_cards:
            raise ValueError("No friction support cards available")

        respite = self._build_respite_suggestion(db=db, family=family, signal=signal, payload=payload)
        action_plan = self._action_plan(cards=selected_cards, profile=profile, payload=payload, state=state)
        donts = self._donts(cards=selected_cards, profile=profile, state=state)
        say_this = self._say_this(action_plan=action_plan, state=state)
        exit_plan = self._exit_plan(profile=profile, payload=payload, state=state)
        low_stim_mode = self._low_stim_mode(profile=profile, payload=payload, state=state)

        return FrictionSupportPlan(
            preset_label=self._preset_label(payload),
            headline=self._headline(payload, signal, state),
            situation_summary=self._situation_summary(payload, signal),
            child_signals=self._child_signals(payload),
            caregiver_signals=self._caregiver_signals(payload),
            why_this_plan=self._why_this_plan(
                db=db,
                cards=selected_cards,
                profile=profile,
                payload=payload,
                signal=signal,
                state=state,
                evidence_bundle=evidence_bundle,
            ),
            excluded_actions=self._excluded_actions(profile=profile, payload=payload, state=state),
            action_plan=action_plan,
            donts=donts,
            say_this=say_this,
            voice_guidance=self._voice_guidance(payload, state),
            exit_plan=exit_plan,
            low_stim_mode=low_stim_mode,
            crisis_card=self._crisis_card(
                payload=payload,
                signal=signal,
                state=state,
                action_plan=action_plan,
                donts=donts,
                say_this=say_this,
                exit_plan=exit_plan,
                low_stim_mode=low_stim_mode,
            ),
            respite_suggestion=respite,
            personalized_strategies=self._personalized_strategies(db=db, cards=selected_cards, profile=profile, payload=payload),
            school_message=self._school_message(cards=selected_cards, profile=profile, payload=payload),
            handoff_messages=self._handoff_messages(cards=selected_cards, profile=profile, payload=payload, state=state),
            feedback_prompt="执行 5-10 分钟后告诉我：孩子是否更稳定、你是否更能跟住方案；系统会据此调整下次推荐顺序。",
            citations=[card.card_id for card in selected_cards],
            source_card_ids=[card.card_id for card in selected_cards],
        )

    def _derive_state(self, payload: FrictionSupportGenerateRequest, signal: SignalOutput) -> FrictionState:
        low_stim_only = (
            payload.low_stim_mode_requested
            or payload.child_state in {"sensory_overload", "meltdown"}
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
            payload.child_state in {"sensory_overload", "meltdown"}
            or payload.child_state in {"conflict", "meltdown"}
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
        scenario_label = self._preset_label(payload)
        if state.low_stim_only:
            return f"{scenario_label}高摩擦时刻：先保安全，再退场"
        if signal.risk_level == "yellow":
            return f"{scenario_label}高摩擦时刻：先稳住，再做一步"
        return f"{scenario_label}高摩擦时刻：先停住，再推进"

    def _situation_summary(self, payload: FrictionSupportGenerateRequest, signal: SignalOutput) -> str:
        reason = signal.reasons[0] if signal.reasons else "当前负荷偏高"
        return f"{reason}。现在先照行动卡做，不临时加码，不讲长道理。"

    def _child_signals(self, payload: FrictionSupportGenerateRequest) -> list[str]:
        return [
            f"孩子：{self.child_state_labels[payload.child_state]}",
            f"感官：{self.sensory_labels[payload.sensory_overload_level]}",
            f"今日升级 {payload.meltdown_count} 次",
        ]

    def _caregiver_signals(self, payload: FrictionSupportGenerateRequest) -> list[str]:
        return [
            f"家长压力 {payload.caregiver_stress:g}/10，疲劳 {payload.caregiver_fatigue:g}/10",
            f"信心 {payload.confidence_to_follow_plan:g}/10，睡眠 {payload.caregiver_sleep_quality:g}/10",
            self.support_labels[payload.support_available],
        ]

    def _why_this_plan(
        self,
        db: Session,
        cards: list[StrategyCard],
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
        signal: SignalOutput,
        state: FrictionState,
        evidence_bundle: RetrievalEvidenceBundle | None = None,
    ) -> list[str]:
        if evidence_bundle is not None and evidence_bundle.selection_reasons:
            return self._unique_lines(list(evidence_bundle.selection_reasons), limit=4)

        reasons: list[str] = []
        if state.low_stim_only:
            reasons.append("当前孩子已接近过载或升级，系统优先给低刺激、可快速退场的动作。")
        elif signal.risk_level == "yellow":
            reasons.append("近几天负荷偏高，系统优先选择能先稳住现场、再推进一步的方案。")
        else:
            reasons.append("当前仍可推进，但系统只保留最短三步，避免现场信息过载。")

        if payload.support_available == "none":
            reasons.append("当前无人可接手，系统优先保留单人也能执行的短句和退场动作。")
        elif payload.support_available == "one":
            reasons.append("当前只有 1 位支持者，系统优先选择容易交接、不依赖多人配合的做法。")
        else:
            reasons.append("当前有人可接手，系统保留了更容易分段交接的动作顺序。")

        history = self._history_effect_map(db=db, family_id=payload.family_id)
        positive = next((card for card in cards if history.get(card.card_id, 0.0) > 0.5), None)
        negative = next((card for card in cards if history.get(card.card_id, 0.0) < 0), None)
        if positive is not None:
            reasons.append(f"历史反馈显示“{positive.title}”这类做法更常有效，所以这次继续排在前面。")
        elif negative is not None:
            reasons.append(f"过去“{negative.title}”这类做法反馈一般，所以这次只保留可快速退出的版本。")

        profile_donts = getattr(profile, "donts", [])
        if profile_donts:
            reasons.append(f"系统已对照档案禁忌“{profile_donts[0]}”过滤不合适动作。")
        return self._unique_lines(reasons, limit=4)

    def _excluded_actions(
        self,
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
        state: FrictionState,
    ) -> list[str]:
        exclusions: list[str] = []
        donts = getattr(profile, "donts", [])
        if any("触" in item or "碰" in item for item in donts):
            exclusions.append("已排除身体介入类做法：档案标记了不可触碰。")
        if any("大声" in item or "吼" in item for item in donts):
            exclusions.append("已排除提高音量或连续催促：档案标记了不可大声。")
        if any("追问" in item or "为什么" in item for item in donts):
            exclusions.append("已排除追问原因和长解释：这会把孩子重新推回对抗。")
        if state.low_stim_only:
            exclusions.append("已排除继续推进原任务：当前先保安全、降刺激和可退出。")
        if payload.meltdown_count >= 2 or payload.child_state == "meltdown":
            exclusions.append("已排除需要连续配合的训练式做法：当前状态更适合先退场恢复。")
        if payload.support_available == "none":
            exclusions.append("已排除依赖多人接手的方案：当前现场只有一位照护者。")
        if len(exclusions) < 2:
            exclusions.append("已排除临时加码和多步命令：当前只保留最短三步动作。")
        return self._unique_lines(exclusions, limit=4)

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

    @staticmethod
    def _unique_lines(values: list[str], *, limit: int) -> list[str]:
        deduped = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        return deduped[:limit]

    @staticmethod
    def _custom_scenario_label(payload: FrictionSupportGenerateRequest) -> str:
        return payload.custom_scenario.strip()

    def _preset_label(self, payload: FrictionSupportGenerateRequest) -> str:
        custom_label = self._custom_scenario_label(payload)
        if custom_label:
            return custom_label
        if payload.quick_preset:
            return FRICTION_PRESET_LABELS[payload.quick_preset]
        return self.scenario_labels[payload.scenario]

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
            "先停一下，你是安全的，我会陪你。",
            "现在只选一个：你自己来，还是我陪你？",
            f"这件事先暂停，我们先去 {soothing_place}。",
        ]
        why_bits = [
            "先停住，能避免继续往上冲。",
            "两个选项比一长串解释更容易跟上。",
            "先保安全和关系，不硬做完任务。",
        ]
        action_lines = [
            "停下当前要求，先降声音和灯光。",
            "只给一个边界和两个选项，然后等 5 秒。",
            f"若仍卡住，转去 {soothing_place} 或直接退场。",
        ]

        plan: list[FrictionSupportStep] = []
        titles = self._step_titles(state)
        for idx, _card in enumerate(cards[:3]):
            script = cards[0].scripts_json.get("parent") if idx == 0 else base_scripts[idx]
            if not script:
                script = base_scripts[idx]
            plan.append(
                FrictionSupportStep(
                    title=titles[idx],
                    action=action_lines[idx],
                    parent_script=script,
                    why_it_fits=why_bits[idx],
                )
            )

        while len(plan) < 3:
            idx = len(plan)
            plan.append(
                FrictionSupportStep(
                    title=titles[idx],
                    action=action_lines[idx],
                    parent_script=base_scripts[idx],
                    why_it_fits=why_bits[idx],
                )
            )
        return plan[:3]

    def _donts(self, cards: list[StrategyCard], profile: ChildProfile | None, state: FrictionState) -> list[str]:
        profile_donts = getattr(profile, "donts", [])
        donts: list[str] = []
        if any("触" in item or "碰" in item for item in profile_donts):
            donts.append("不要碰身体或强拉。")
        if any("大声" in item or "吼" in item for item in profile_donts):
            donts.append("不要提高音量。")
        if any("追问" in item or "为什么" in item for item in profile_donts):
            donts.append("不要追问原因。")

        for card in cards:
            donts.extend(item if item.endswith("。") else f"{item}。" for item in card.donts_json[:2])

        if state.needs_fast_exit:
            donts.append("不要一边升级一边硬做完任务。")
        donts.extend(["不要连续换很多说法。", "不要同时提多个要求。"])
        return self._unique_lines(donts, limit=4)[:4]

    def _say_this(self, action_plan: list[FrictionSupportStep], state: FrictionState) -> list[str]:
        lines = [step.parent_script for step in action_plan[:2]]
        lines.append("这件事现在先暂停，我们先把身体稳下来。" if state.needs_fast_exit else "先做完这一步，别的等会儿再说。")
        return self._unique_lines(lines, limit=3)

    def _low_stim_mode(
        self,
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
        state: FrictionState,
    ) -> FrictionLowStimMode:
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        active = state.low_stim_only or payload.low_stim_mode_requested
        headline = "低刺激模式已开启" if active else "建议一键切到低刺激模式"
        actions = [
            "关掉额外声音和强光。",
            "只留一位沟通者，短句低声。",
            f"先去 {soothing_place} 或保持原地低刺激陪伴。",
        ]
        if payload.support_available != "none":
            actions.append("必要时让支持者接手 10-15 分钟。")
        return FrictionLowStimMode(active=active, headline=headline, actions=actions[:4])

    def _crisis_card(
        self,
        payload: FrictionSupportGenerateRequest,
        signal: SignalOutput,
        state: FrictionState,
        action_plan: list[FrictionSupportStep],
        donts: list[str],
        say_this: list[str],
        exit_plan: list[str],
        low_stim_mode: FrictionLowStimMode,
    ) -> FrictionCrisisCard:
        help_now = []
        if payload.support_available != "none":
            help_now.append("联系支持者接手 10-15 分钟。")
        else:
            help_now.append("联系家里可到场的人或学校支持联系人。")
        if signal.risk_level == "red" or payload.high_risk_selected:
            help_now.append("若有人身风险，立即联系当地急救或危机热线。")
        else:
            help_now.append("若 10 分钟仍持续升级，立即求助。")
        badges = [
            f"场景 {self._preset_label(payload)}",
            f"风险 {signal.risk_level.upper()}",
            "低刺激" if low_stim_mode.active else "标准",
        ]
        if state.needs_fast_exit:
            badges.append("优先退场")
        return FrictionCrisisCard(
            title=f"{self._preset_label(payload)}危机卡",
            badges=badges[:4],
            first_do=[step.action for step in action_plan[:3]],
            donts=self._unique_lines(donts, limit=3),
            say_this=self._unique_lines(say_this, limit=3),
            exit_plan=exit_plan[:3],
            help_now=help_now[:2],
        )

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
            f"今天孩子在{self._preset_label(payload)}场景负荷偏高，请统一采用短句、先预告再切换的方式。"
            f"{teacher_script} 若出现升级，请先降噪、给两个选项，并允许去 {soothing_place} 缓冲 5-10 分钟。"
            f"{env_note}"
        ).strip()

    def _handoff_messages(
        self,
        cards: list[StrategyCard],
        profile: ChildProfile | None,
        payload: FrictionSupportGenerateRequest,
        state: FrictionState,
    ) -> list[PlanMessage]:
        scenario_label = self._preset_label(payload)
        soothing_place = self._pick(getattr(profile, "soothing_methods", []), "安静角落")
        caregiver_message = (
            f"现在先按 {scenario_label} 行动卡做：先停住当前要求，只给一个边界和两个选择；"
            f"如果 5 分钟内还在升级，就直接转去 {soothing_place}，不要继续讲道理。"
        )
        supporter_message = (
            f"如果你现在接手，请先复述同一句短指令，不要换说法；"
            f"当前目标不是把事情做完，而是先陪孩子回到能跟上的状态。"
        )
        if payload.support_available == "none":
            supporter_message = (
                f"如果有人能临时接手，请只帮忙清场、降噪或把其他任务拿走；"
                f"主沟通者仍保持 1 位，避免多人同时说话。"
            )
        teacher_message = self._school_message(cards=cards, profile=profile, payload=payload)

        messages = [
            PlanMessage(target="family", text=caregiver_message),
            PlanMessage(target="supporter", text=supporter_message),
            PlanMessage(target="teacher", text=teacher_message),
        ]
        if state.low_stim_only:
            messages[0].text = (
                f"现在先按低刺激模式处理 {scenario_label}：减少口头解释，先保安全和陪伴；"
                f"若孩子继续升级，直接转去 {soothing_place}，暂停原任务。"
            )
        return messages
