from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import engine
from app.db.init_db import init_db
from app.models import ChildProfile, DailyCheckin, Family, IncidentLog, Review, SupportNetwork, User


def main() -> None:
    init_db(seed_strategy_cards=True)

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.identifier == "demo@careos"))
        if user is None:
            user = User(identifier="demo@careos", role="caregiver", locale="zh-CN")
            db.add(user)
            db.flush()

        family = db.scalar(select(Family).where(Family.name == "Demo Family"))
        if family is None:
            family = Family(name="Demo Family", timezone="Asia/Shanghai", owner_user_id=user.user_id)
            db.add(family)
            db.flush()

        profile = db.scalar(select(ChildProfile).where(ChildProfile.family_id == family.family_id))
        if profile is None:
            profile = ChildProfile(
                family_id=family.family_id,
                age_band="7-9",
                language_level="short_sentence",
                sensory_flags=["sound", "crowd"],
                triggers=["过渡", "等待", "噪音"],
                soothing_methods=["提前预告", "安静角落", "耳罩"],
                donts=["不可强拉", "不可大声", "不可连续追问"],
                school_context={"class": "2A", "teacher": "王老师"},
                high_friction_scenarios=["transition", "bedtime", "homework"],
            )
            db.add(profile)

        if not db.scalars(select(SupportNetwork).where(SupportNetwork.family_id == family.family_id)).all():
            db.add_all(
                [
                    SupportNetwork(
                        family_id=family.family_id,
                        contact_name="妈妈",
                        relation="parent",
                        availability_slots=["晚间", "周末"],
                        notes="优先接手睡前流程",
                    ),
                    SupportNetwork(
                        family_id=family.family_id,
                        contact_name="外婆",
                        relation="grandparent",
                        availability_slots=["下午"],
                        notes="可接手30分钟陪伴",
                    ),
                ]
            )

        existing_checkins = db.scalars(select(DailyCheckin).where(DailyCheckin.family_id == family.family_id)).all()
        if len(existing_checkins) < 14:
            base = date.today() - timedelta(days=13)
            for i in range(14):
                day = base + timedelta(days=i)
                db.merge(
                    DailyCheckin(
                        family_id=family.family_id,
                        date=day,
                        child_sleep_hours=round(random.uniform(5.0, 8.5), 1),
                        meltdown_count=random.choice([0, 1, 2, 3]),
                        transition_difficulty=round(random.uniform(3.0, 9.0), 1),
                        sensory_overload_level=random.choice(["none", "light", "medium", "heavy"]),
                        caregiver_stress=round(random.uniform(3.0, 9.5), 1),
                        caregiver_sleep_hours=round(random.uniform(4.5, 8.0), 1),
                        support_available=random.choice(["none", "one", "two_plus"]),
                        env_changes=random.sample(["学校活动", "外出", "来客", "行程变动"], k=random.randint(0, 2)),
                    )
                )

        incidents = db.scalars(select(IncidentLog).where(IncidentLog.family_id == family.family_id)).all()
        if not incidents:
            incident = IncidentLog(
                family_id=family.family_id,
                ts=datetime.utcnow() - timedelta(days=1),
                scenario="transition",
                intensity="medium",
                triggers=["停止玩具", "临时变更"],
                selected_resources={"adult_count": 1, "earmuff": True},
                high_risk_flag=False,
                notes="放学回家过渡冲突",
            )
            db.add(incident)
            db.flush()

            db.add(
                Review(
                    incident_id=incident.id,
                    family_id=family.family_id,
                    card_ids=["CARD-0001", "CARD-0002"],
                    outcome_score=1,
                    notes="预告有效，仍有拖延",
                    followup_action="提前把视觉提示贴在门口",
                )
            )

        db.commit()

        print("Seed complete")
        print(f"Demo user: demo@careos (user_id={user.user_id})")
        print(f"Demo family_id: {family.family_id}")


if __name__ == "__main__":
    main()
