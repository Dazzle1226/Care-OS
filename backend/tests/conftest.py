from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

os.environ.setdefault("CARE_OS_DATABASE_URL", "sqlite:////tmp/care_os_test.db")
os.environ.setdefault("CARE_OS_FORCE_RULE_FALLBACK", "true")

from app.db.base import Base, SessionLocal, engine
from app.db.init_db import init_db
from app.models import ChildProfile, DailyCheckin, Family, User


@pytest.fixture()
def db_session() -> Session:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_path = Path(__file__).resolve().parents[1] / "seed" / "strategy_cards.json"
    init_db(seed_strategy_cards=True, seed_path=str(seed_path))

    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def seeded_family(db_session: Session) -> Family:
    user = User(identifier="tester", role="caregiver", locale="zh-CN")
    db_session.add(user)
    db_session.flush()

    family = Family(name="Test Family", timezone="Asia/Shanghai", owner_user_id=user.user_id)
    db_session.add(family)
    db_session.flush()

    profile = ChildProfile(
        family_id=family.family_id,
        age_band="7-9",
        language_level="short_sentence",
        sensory_flags=["sound"],
        triggers=["过渡", "等待"],
        soothing_methods=["提前预告", "安静角落"],
        donts=["不可触碰", "不可大声"],
        school_context={},
        high_friction_scenarios=["transition", "bedtime"],
    )
    db_session.add(profile)

    # baseline two-day history for signal agent tests
    today = date.today()
    db_session.add_all(
        [
            DailyCheckin(
                family_id=family.family_id,
                date=today - timedelta(days=1),
                child_sleep_hours=5.0,
                meltdown_count=2,
                transition_difficulty=8.0,
                sensory_overload_level="medium",
                caregiver_stress=8.0,
                caregiver_sleep_hours=5.0,
                support_available="none",
                env_changes=["行程变动"],
            ),
            DailyCheckin(
                family_id=family.family_id,
                date=today,
                child_sleep_hours=5.5,
                meltdown_count=3,
                transition_difficulty=8.5,
                sensory_overload_level="heavy",
                caregiver_stress=8.2,
                caregiver_sleep_hours=5.3,
                support_available="none",
                env_changes=["学校事件"],
            ),
        ]
    )

    db_session.commit()
    db_session.refresh(family)
    return family
