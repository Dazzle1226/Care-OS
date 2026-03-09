from __future__ import annotations

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import DailyCheckin, IncidentLog
from app.schemas.domain import SignalOutput


class SignalAgent:
    def evaluate(self, db: Session, family_id: int, target_date: date | None = None, manual_trigger: bool = False) -> SignalOutput:
        stmt = select(DailyCheckin).where(DailyCheckin.family_id == family_id).order_by(desc(DailyCheckin.date)).limit(7)
        checkins = db.scalars(stmt).all()
        if target_date is not None:
            checkins = [c for c in checkins if c.date <= target_date]

        if not checkins:
            return SignalOutput(risk_level="yellow", reasons=["缺少近7天签到，默认进入谨慎模式"], trigger_48h=manual_trigger, confidence=0.55)

        latest = checkins[0]
        recent_incidents = db.scalars(
            select(IncidentLog)
            .where(IncidentLog.family_id == family_id)
            .order_by(desc(IncidentLog.ts))
            .limit(5)
        ).all()

        score = 0
        reasons: list[str] = []

        if len(checkins) >= 2 and checkins[0].caregiver_stress >= 7 and checkins[1].caregiver_stress >= 7:
            score += 2
            reasons.append("连续两天照护者压力>=7")

        if latest.caregiver_sleep_hours < 6 and latest.meltdown_count >= 2:
            score += 2
            reasons.append("睡眠不足且崩溃次数升高")

        if latest.transition_difficulty >= 7 and latest.meltdown_count >= 2:
            score += 2
            reasons.append("高难度过渡并伴随多次崩溃")

        avg_stress = sum(c.caregiver_stress for c in checkins[:3]) / min(3, len(checkins))
        if avg_stress >= 6:
            score += 1
            reasons.append("近3天平均压力偏高")

        if any(inc.intensity == "heavy" for inc in recent_incidents):
            score += 1
            reasons.append("近期发生重度事件")

        if score >= 4:
            risk_level = "red"
        elif score >= 2:
            risk_level = "yellow"
        else:
            risk_level = "green"

        trigger_48h = manual_trigger or (
            (len(checkins) >= 2 and checkins[0].caregiver_stress >= 7 and checkins[1].caregiver_stress >= 7)
            or (latest.caregiver_sleep_hours < 6 and latest.meltdown_count >= 2)
            or (latest.transition_difficulty >= 7 and latest.meltdown_count >= 2)
        )

        confidence = max(0.55, min(0.95, 0.55 + score * 0.08))
        compact_reasons = reasons[:2] if reasons else ["当前信号稳定，维持低刺激策略"]

        return SignalOutput(
            risk_level=risk_level,
            reasons=compact_reasons,
            trigger_48h=trigger_48h,
            confidence=round(confidence, 2),
        )
