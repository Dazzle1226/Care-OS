from __future__ import annotations

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import DailyCheckin, IncidentLog
from app.schemas.domain import SignalOutput


class SignalAgent:
    def evaluate(self, db: Session, family_id: int, target_date: date | None = None, manual_trigger: bool = False) -> SignalOutput:
        stmt = select(DailyCheckin).where(DailyCheckin.family_id == family_id)
        if target_date is not None:
            stmt = stmt.where(DailyCheckin.date <= target_date)
        checkins = db.scalars(stmt.order_by(desc(DailyCheckin.date)).limit(7)).all()

        if not checkins:
            return SignalOutput(
                risk_level="yellow",
                reasons=["缺少近7天签到，默认进入谨慎模式"],
                trigger_48h=manual_trigger,
                confidence=0.35,
            )

        latest = checkins[0]
        recent_three = checkins[:3]
        recent_two = checkins[:2]
        recent_incidents = db.scalars(
            select(IncidentLog)
            .where(IncidentLog.family_id == family_id)
            .order_by(desc(IncidentLog.ts))
            .limit(5)
        ).all()

        risk_signals: list[tuple[int, str, bool]] = []
        protection_signals: list[tuple[int, str]] = []

        if len(recent_two) >= 2 and all(item.caregiver_stress >= 7 for item in recent_two):
            risk_signals.append((2, "连续两天照护者压力>=7", True))

        if latest.caregiver_sleep_hours < 6 and latest.caregiver_stress >= 7:
            risk_signals.append((2, "照护者睡眠不足且压力偏高", True))

        if latest.transition_difficulty >= 7 and latest.meltdown_count >= 2:
            risk_signals.append((2, "高难度过渡并伴随多次崩溃", True))

        if latest.meltdown_count >= 3:
            risk_signals.append((2, "当天崩溃次数明显偏多", True))

        if latest.child_sleep_hours < 6 and latest.meltdown_count >= 2:
            risk_signals.append((1, "孩子睡眠不足后更易升级", False))

        if latest.sensory_overload_level in {"medium", "heavy"} and latest.meltdown_count >= 2:
            risk_signals.append((1, "感官负荷偏高，现场更容易卡住", False))

        avg_stress = sum(item.caregiver_stress for item in recent_three) / len(recent_three)
        if avg_stress >= 6.5:
            risk_signals.append((1, "近3天平均压力偏高", False))

        avg_meltdown = sum(item.meltdown_count for item in recent_three) / len(recent_three)
        if avg_meltdown >= 2:
            risk_signals.append((1, "近3天崩溃次数持续偏高", False))

        has_recent_heavy_incident = any(inc.intensity == "heavy" for inc in recent_incidents)
        if has_recent_heavy_incident:
            risk_signals.append((2, "近期发生重度事件", True))

        if latest.env_changes and latest.transition_difficulty >= 7:
            risk_signals.append((1, "今日有环境变化，过渡成本更高", False))

        if latest.support_available == "two_plus":
            protection_signals.append((1, "今天有可接手支持，可分段减负"))
        elif latest.support_available == "one" and latest.caregiver_stress < 7:
            protection_signals.append((1, "今天有人可协助，可先按低负荷推进"))

        if len(recent_two) >= 2 and all(item.caregiver_stress < 6 and item.meltdown_count <= 1 for item in recent_two):
            protection_signals.append((1, "近两天总体稳定，可维持当前节奏"))

        if latest.caregiver_sleep_hours >= 7 and latest.meltdown_count == 0:
            protection_signals.append((1, "照护者恢复较好，今天可先守住稳定节奏"))

        risk_score = sum(weight for weight, _, _ in risk_signals)
        protection_score = sum(weight for weight, _ in protection_signals)
        net_score = max(0, risk_score - protection_score)

        if net_score >= 5:
            risk_level = "red"
        elif net_score >= 2:
            risk_level = "yellow"
        else:
            risk_level = "green"
        if has_recent_heavy_incident and risk_level == "green":
            risk_level = "yellow"

        acute_risk_count = sum(1 for _, _, acute in risk_signals if acute)
        trigger_48h = manual_trigger or acute_risk_count >= 2 or has_recent_heavy_incident

        coverage_ratio = min(len(checkins), 7) / 7
        signal_density = min(len(risk_signals) + len(protection_signals), 5) / 5
        confidence = 0.35 + coverage_ratio * 0.4 + signal_density * 0.2
        confidence = max(0.35, min(0.95, confidence))

        if risk_level == "green":
            compact_reasons = [reason for _, reason in protection_signals[:2]]
            if not compact_reasons:
                compact_reasons = ["当前信号稳定，维持低刺激策略"]
        else:
            sorted_risk_reasons = [reason for _, reason, _ in sorted(risk_signals, key=lambda item: item[0], reverse=True)]
            compact_reasons = sorted_risk_reasons[:2] if sorted_risk_reasons else ["当前负荷偏高，先减任务再推进"]

        return SignalOutput(
            risk_level=risk_level,
            reasons=compact_reasons,
            trigger_48h=trigger_48h,
            confidence=round(confidence, 2),
        )
