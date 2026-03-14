from __future__ import annotations

from dataclasses import dataclass

from app.agents.safety import SafetyDecision
from app.schemas.domain import AgentProposal, CoordinationDecision, CriticReview, EmotionAssessment, FrictionSupportPlan


@dataclass(slots=True)
class CoordinationResult:
    support: FrictionSupportPlan
    decision: CoordinationDecision
    proposals: list[AgentProposal]
    changed_fields: list[str]


class CoordinatorAgent:
    def coordinate(
        self,
        support: FrictionSupportPlan,
        emotion: EmotionAssessment,
        safety: SafetyDecision,
        evidence_review: CriticReview,
        support_available: str,
        prefer_lighter: bool = False,
        prefer_handoff: bool = False,
    ) -> CoordinationResult:
        proposals = self._build_proposals(
            support=support,
            emotion=emotion,
            safety=safety,
            evidence_review=evidence_review,
            support_available=support_available,
            prefer_lighter=prefer_lighter,
            prefer_handoff=prefer_handoff,
        )
        selected = max(proposals, key=lambda item: (item.priority, item.confidence))
        adapted_support, changed_fields = self._adapt_support(support, selected.proposal_kind)
        decision = CoordinationDecision(
            selected_proposal_id=selected.proposal_id,
            alternative_proposal_ids=[item.proposal_id for item in proposals if item.proposal_id != selected.proposal_id][:3],
            decision_reason=selected.rationale,
            weight_summary=[
                f"{item.agent_name} -> {item.proposal_kind}: 权重 {item.priority:.2f} / 置信度 {item.confidence:.2f}"
                for item in proposals[:3]
            ],
            replan_triggers=[
                "风险等级变化",
                "照护者负荷跨阈值",
                "孩子过载跨阈值",
                "3-5 分钟后仍无改善",
                "用户主动要求换更轻方案",
            ],
            active_mode="blocked" if selected.proposal_kind == "block" else selected.proposal_kind,
            now_step=adapted_support.action_plan[0].action,
            now_script=adapted_support.action_plan[0].parent_script,
            next_if_not_working=adapted_support.exit_plan[0],
            summary=adapted_support.situation_summary,
        )
        return CoordinationResult(
            support=adapted_support,
            decision=decision,
            proposals=proposals,
            changed_fields=changed_fields,
        )

    def _build_proposals(
        self,
        *,
        support: FrictionSupportPlan,
        emotion: EmotionAssessment,
        safety: SafetyDecision,
        evidence_review: CriticReview,
        support_available: str,
        prefer_lighter: bool,
        prefer_handoff: bool,
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        if safety.blocked:
            proposals.append(
                AgentProposal(
                    proposal_id="safety-block",
                    agent_name="SafetyCriticAgent",
                    proposal_kind="block",
                    payload={"blocked": True},
                    confidence=1.0,
                    priority=9.0,
                    rationale=safety.block.block_reason if safety.block else "安全规则命中，必须阻断。",
                    depends_on=["safety_critic"],
                )
            )
            return proposals

        continue_priority = 0.8
        lighter_priority = 0.6
        handoff_priority = 0.5

        if evidence_review.decision == "needs_clarification":
            lighter_priority += 0.15
        if emotion.child_overload_level == "high":
            lighter_priority += 0.35
        elif emotion.child_overload_level == "medium":
            lighter_priority += 0.15
        if emotion.caregiver_overload_level == "high":
            lighter_priority += 0.25
            handoff_priority += 0.3
            continue_priority -= 0.2
        elif emotion.caregiver_overload_level == "medium":
            handoff_priority += 0.15
        if emotion.confidence_drift == "critical":
            lighter_priority += 0.25
            continue_priority -= 0.15
        elif emotion.confidence_drift == "dropping":
            lighter_priority += 0.1
        if support_available != "none":
            handoff_priority += 0.15
        if prefer_lighter:
            lighter_priority += 0.4
        if prefer_handoff:
            handoff_priority += 0.7
            continue_priority -= 0.1
            lighter_priority -= 0.05

        proposals.extend(
            [
                AgentProposal(
                    proposal_id="proposal-continue",
                    agent_name="PlanProposalAgent",
                    proposal_kind="continue",
                    payload={"headline": support.headline},
                    confidence=max(0.55, 0.78 - max(lighter_priority - continue_priority, 0)),
                    priority=max(0.1, continue_priority),
                    rationale="当前计划仍可执行，优先保留原有结构以减少现场切换成本。",
                    depends_on=["candidate_generation", "emotion_eval"],
                ),
                AgentProposal(
                    proposal_id="proposal-lighter",
                    agent_name="EmotionAgent",
                    proposal_kind="lighter",
                    payload={"mode": "low_stim"},
                    confidence=min(0.95, 0.65 + lighter_priority * 0.2),
                    priority=lighter_priority,
                    rationale="当前负荷偏高，应优先压缩成一步并降低语言密度。",
                    depends_on=["emotion_eval", "evidence_critic"],
                ),
                AgentProposal(
                    proposal_id="proposal-handoff",
                    agent_name="CoordinatorAgent",
                    proposal_kind="handoff",
                    payload={"support_available": support_available},
                    confidence=min(0.95, 0.6 + handoff_priority * 0.2),
                    priority=handoff_priority,
                    rationale="现场更需要提前准备交接和退场，避免继续僵持。",
                    depends_on=["emotion_eval", "policy_adjust_hint"],
                ),
            ]
        )
        proposals.sort(key=lambda item: item.priority, reverse=True)
        return proposals

    def _adapt_support(self, support: FrictionSupportPlan, mode: str) -> tuple[FrictionSupportPlan, list[str]]:
        if mode == "continue":
            return support, []

        if mode == "lighter":
            first_step = support.action_plan[0].model_copy(
                update={
                    "title": "先做这一小步",
                    "action": support.action_plan[0].action,
                    "parent_script": support.say_this[0] if support.say_this else support.action_plan[0].parent_script,
                    "why_it_fits": "当前优先减负，只保留最容易执行的一步。",
                }
            )
            adapted = support.model_copy(
                update={
                    "headline": f"{support.preset_label}高摩擦时刻：先压缩成一步",
                    "situation_summary": f"{support.situation_summary} 现在先不要展开全部步骤。",
                    "action_plan": [first_step, *support.action_plan[1:]],
                    "why_this_plan": ["当前先保安全和可执行性，再考虑推进。"] + support.why_this_plan[:2],
                    "voice_guidance": support.voice_guidance[:2] + ["一句话后停 3 秒，先看孩子反应。"][:1],
                    "feedback_prompt": "先执行这一小步，3 分钟后再告诉我是否更稳定；如无改善，我会自动切换更轻方案。",
                }
            )
            return adapted, ["coordination", "support"]

        first_handoff = support.handoff_messages[1].text if len(support.handoff_messages) > 1 else support.handoff_messages[0].text
        adapted = support.model_copy(
            update={
                "headline": f"{support.preset_label}高摩擦时刻：先交接，再保安全",
                "situation_summary": "当前更适合尽快减少对抗，把注意力放到交接和退场。",
                "action_plan": [
                    support.action_plan[0].model_copy(
                        update={
                            "title": "先发起交接",
                            "action": "用最短一句话发起交接或明确谁来接下一步。",
                            "parent_script": first_handoff,
                            "why_it_fits": "当前更需要减少持续消耗，先让支持者接住局面。",
                        }
                    ),
                    *support.action_plan[1:],
                ],
                "feedback_prompt": "如果已经交接成功，告诉我谁接手、孩子是否更稳定；系统会记住更有效的交接方式。",
            }
        )
        return adapted, ["coordination", "support"]
