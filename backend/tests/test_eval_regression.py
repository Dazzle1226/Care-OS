from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import ChildProfile, DailyCheckin, Family, IncidentLog, Review


EVAL_CASES_DIR = Path(__file__).resolve().parents[1] / "evals" / "cases"
EVAL_CASE_PATHS = sorted(EVAL_CASES_DIR.glob("*.json"))


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "eval-runner", "role": "caregiver", "locale": "zh-CN"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _load_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _week_start(target: date) -> date:
    return target - timedelta(days=target.isoweekday() - 1)


def _occupied_checkin_dates(db_session: Session, family_id: int) -> set[date]:
    return set(db_session.scalars(select(DailyCheckin.date).where(DailyCheckin.family_id == family_id)).all())


def _first_available_dates(start: date, count: int, occupied: set[date], *, window_days: int) -> list[date]:
    available: list[date] = []
    for offset in range(window_days):
        candidate = start + timedelta(days=offset)
        if candidate in occupied:
            continue
        available.append(candidate)
        if len(available) == count:
            return available
    raise AssertionError("Not enough available dates for eval fixtures")


def _set_deep(target: dict[str, Any], key_path: str, value: Any) -> None:
    cursor = target
    parts = key_path.split(".")
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def _resolve_path(payload: Any, dotted_path: str) -> Any:
    cursor = payload
    for part in dotted_path.split("."):
        if part == "__len__":
            return len(cursor)
        if isinstance(cursor, list):
            cursor = cursor[int(part)]
            continue
        cursor = cursor[part]
    return cursor


def _render_template(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        rendered = value
        for key, replacement in context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(replacement))
        return rendered
    if isinstance(value, list):
        return [_render_template(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render_template(item, context) for key, item in value.items()}
    return value


def _seed_review_entries(db_session: Session, family: Family, entries: list[dict[str, Any]]) -> None:
    for item in entries:
        incident = IncidentLog(
            family_id=family.family_id,
            ts=datetime.combine(date.today(), time(hour=18)),
            scenario=item["scenario"],
            intensity=item["intensity"],
            triggers=["等待", "噪音"],
            selected_resources={},
            high_risk_flag=False,
            notes=item["notes"],
        )
        db_session.add(incident)
        db_session.flush()
        db_session.add(
            Review(
                incident_id=incident.id,
                family_id=family.family_id,
                card_ids=item["card_ids"],
                outcome_score=item["outcome_score"],
                child_state_after=item["child_state_after"],
                caregiver_state_after=item["caregiver_state_after"],
                recommendation=item["recommendation"],
                notes=item["notes"],
                followup_action=item["followup_action"],
            )
        )
    db_session.commit()


def _seed_weekly_report_fixture(db_session: Session, family: Family) -> date:
    week_start = _week_start(date.today())
    occupied = _occupied_checkin_dates(db_session, family.family_id)
    weekly_dates = _first_available_dates(week_start, 2, occupied, window_days=7)

    db_session.add_all(
        [
            DailyCheckin(
                family_id=family.family_id,
                date=weekly_dates[0],
                child_sleep_hours=6.5,
                meltdown_count=1,
                transition_difficulty=7.0,
                sensory_overload_level="medium",
                caregiver_stress=7.0,
                caregiver_sleep_hours=5.0,
                support_available="one",
                env_changes=["噪音"],
            ),
            DailyCheckin(
                family_id=family.family_id,
                date=weekly_dates[1],
                child_sleep_hours=7.0,
                meltdown_count=0,
                transition_difficulty=5.0,
                sensory_overload_level="light",
                caregiver_stress=5.0,
                caregiver_sleep_hours=6.0,
                support_available="two_plus",
                env_changes=["换环境"],
            ),
        ]
    )

    incident = IncidentLog(
        family_id=family.family_id,
        ts=datetime.combine(weekly_dates[0], time(hour=18)),
        scenario="transition",
        intensity="medium",
        triggers=["等待", "噪音"],
        selected_resources={},
        high_risk_flag=False,
        notes="放学回家后卡住",
    )
    db_session.add(incident)
    db_session.flush()
    db_session.add(
        Review(
            incident_id=incident.id,
            family_id=family.family_id,
            card_ids=["CARD-0001", "CARD-0002"],
            outcome_score=1,
            notes="提前预告后稍有改善",
            followup_action="保留睡前过渡预告",
            created_at=datetime.combine(weekly_dates[1], time(hour=9)),
        )
    )
    db_session.commit()
    return week_start


def _apply_setup(db_session: Session, family: Family, setup: dict[str, Any], context: dict[str, Any]) -> None:
    profile = db_session.scalar(select(ChildProfile).where(ChildProfile.family_id == family.family_id))
    assert profile is not None

    profile_patch = setup.get("profile_patch")
    if profile_patch:
        for key, value in profile_patch.items():
            setattr(profile, key, value)

    extra_checkins = setup.get("extra_checkins") or []
    for item in extra_checkins:
        db_session.add(
            DailyCheckin(
                family_id=family.family_id,
                **item,
            )
        )

    db_session.commit()

    review_entries = setup.get("review_entries") or []
    if review_entries:
        _seed_review_entries(db_session, family, review_entries)

    if setup.get("weekly_report_fixture"):
        context["week_start"] = _seed_weekly_report_fixture(db_session, family).isoformat()


def _assert_expectations(payload: dict[str, Any], expectations: dict[str, Any]) -> None:
    for path, expected in expectations.get("json_paths", {}).items():
        assert _resolve_path(payload, path) == expected, f"{path} expected {expected!r}"

    for path, minimum in expectations.get("min_lengths", {}).items():
        value = _resolve_path(payload, path)
        assert len(value) >= minimum, f"{path} should have length >= {minimum}"

    for path in expectations.get("non_empty", []):
        value = _resolve_path(payload, path)
        assert value not in ("", None, [], {}), f"{path} should be non-empty"

    for path, expected_targets in expectations.get("contains_targets", {}).items():
        values = _resolve_path(payload, path)
        actual_targets = [item["target"] for item in values]
        assert actual_targets == expected_targets, f"{path} expected targets {expected_targets!r}"

    for path, expected_options in expectations.get("any_contains", {}).items():
        value = str(_resolve_path(payload, path))
        assert any(option in value for option in expected_options), f"{path} should contain one of {expected_options!r}"


@pytest.mark.parametrize("case_path", EVAL_CASE_PATHS, ids=lambda path: path.stem)
def test_eval_regression_suite(case_path: Path, db_session: Session, seeded_family: Family) -> None:
    case = _load_case(case_path)
    context: dict[str, Any] = {
        "family_id": seeded_family.family_id,
        "today": date.today().isoformat(),
    }
    setup = case.get("setup") or {}
    _apply_setup(db_session, seeded_family, setup, context)

    responses: dict[str, Any] = {}
    with TestClient(app) as client:
        headers = _auth_headers(client)
        for step in case["steps"]:
            step_context = dict(context)
            for response_name, response_body in responses.items():
                if isinstance(response_body, dict):
                    for key_path in [
                        "today_tasks.0.task_instance_id",
                    ]:
                        try:
                            step_context[f"{response_name}.{key_path}"] = _resolve_path(response_body, key_path)
                        except (KeyError, IndexError, TypeError, ValueError):
                            continue

            path = _render_template(step["path"], step_context)
            body = _render_template(deepcopy(step.get("body")), step_context)
            method = step["method"].upper()

            if method == "GET":
                response = client.get(path, headers=headers)
            elif method == "POST":
                response = client.post(path, json=body, headers=headers)
            else:
                raise AssertionError(f"Unsupported method: {method}")

            assert response.status_code == step["expect"]["status"], f"{case['id']}::{step['name']} failed"
            payload = response.json()
            _assert_expectations(payload, step["expect"])
            responses[step["name"]] = payload
