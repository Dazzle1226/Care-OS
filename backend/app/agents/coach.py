from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.schemas.domain import TodayFocusResponse
from app.services.llm_client import LLMClient, LLMUnavailableError
from app.services.policy_learning import PolicyLearningService
from app.services.rule_fallback import build_fallback_coach_tip, build_fallback_today_focus


@dataclass(slots=True)
class TodayFocusContext:
    risk_level: str
    reasons: list[str]
    recent_scenario: str | None
    sensory_overload_level: str
    meltdown_count: int
    transition_difficulty: float | None
    child_sleep_hours: float
    caregiver_sleep_quality: float
    caregiver_stress: float
    support_available: str
    child_mood_state: str
    negative_emotions: list[str]
    today_activities: list[str]
    today_learning_tasks: list[str]


class CoachAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _attempt_llm_today_focus(self, context: TodayFocusContext) -> TodayFocusResponse:
        system_prompt = (
            "你是 ASD 家庭今日聚焦助手。只输出 JSON，不要解释。"
            "所有内容必须是中文、极简指令、立刻可执行。"
            "不要泛泛鼓励，不要复用固定三挡句式，除非签到内容只能落到那个判断。"
        )
        user_prompt = json.dumps(
            {
                "task": "基于今日签到生成首页聚焦文案",
                "context": asdict(context),
                "output_contract": {
                    "today_one_thing": "一句最重要的行动指令",
                    "headline": "一句行动卡标题",
                    "reminders": [
                        {
                            "eyebrow": "短标签",
                            "title": "这次最容易做偏的边界",
                            "body": "一句具体提醒",
                        },
                        {
                            "eyebrow": "短标签",
                            "title": "现场开始卡住时的第一反应",
                            "body": "一句具体提醒",
                        },
                    ],
                },
                "constraints": {
                    "reminders_exact": 2,
                    "style": "极简指令",
                    "no_long_paragraphs": True,
                    "mention_only_current_day": True,
                },
            },
            ensure_ascii=False,
        )
        raw = self.llm.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        return TodayFocusResponse.model_validate(raw)

    def today_one_thing(self, risk_level: str, recent_scenario: str | None = None) -> str:
        base = build_fallback_coach_tip(risk_level)
        return base

    def generate_today_focus(self, context: TodayFocusContext) -> TodayFocusResponse:
        try:
            return self._attempt_llm_today_focus(context)
        except (LLMUnavailableError, ValidationError, ValueError, TypeError, json.JSONDecodeError):
            return build_fallback_today_focus(asdict(context))

    def update_preference_weights(self, db: Session, family_id: int) -> dict[str, float]:
        db.flush()
        weights = PolicyLearningService().rebuild_card_weights(db=db, family_id=family_id)

        payload = json.dumps({"family_id": family_id, "weights": weights}, sort_keys=True, ensure_ascii=False)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        db.add(AuditLog(family_id=family_id, event_type="coach_weight_update", payload_hash=payload_hash))
        db.flush()

        return weights
