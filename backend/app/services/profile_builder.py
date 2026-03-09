from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def normalize_list(values: Iterable[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
        if len(normalized) >= limit:
            break
    return normalized


def split_text_list(value: str, limit: int = 8) -> list[str]:
    if not value.strip():
        return []
    chunks = value.replace("；", ",").replace(";", ",").replace("\n", ",").replace("，", ",").split(",")
    return normalize_list(chunks, limit=limit)


def to_age_band(child_age: int | None) -> str:
    if child_age is None:
        return "4-6"
    if child_age <= 3:
        return "0-3"
    if child_age <= 6:
        return "4-6"
    if child_age <= 9:
        return "7-9"
    return "10-12"


def build_soothing_methods(
    triggers: list[str],
    sensory_flags: list[str],
    communication_level: str,
    custom_methods: list[str] | None = None,
) -> list[str]:
    items: list[str] = custom_methods[:] if custom_methods else []
    joined = " ".join([*triggers, *sensory_flags])

    if "过渡" in joined:
        items.append("提前预告 + 视觉倒计时")
    if "噪音" in joined or "声音" in joined:
        items.append("耳罩或降低环境噪音")
    if "光" in joined:
        items.append("调暗灯光或避开强光")
    if "触" in joined:
        items.append("先口头提醒，再决定是否接触")
    if "陌生环境" in joined or "外出" in joined:
        items.append("先看图片或先走一圈再进入")
    if communication_level in {"none", "single_word"}:
        items.append("一句一指令 + 配图手势")
    if communication_level == "short_sentence":
        items.append("短句确认 + 给两个选择")
    items.extend(["安静角落短暂停留", "先共情再提出下一步"])
    return normalize_list(items, limit=6)


def build_donts(
    taboo_behaviors: str,
    triggers: list[str],
    sensory_flags: list[str],
    dislikes: list[str],
    behavior_risks: list[str],
) -> list[str]:
    items = split_text_list(taboo_behaviors, limit=6)
    joined = " ".join([*triggers, *sensory_flags, *dislikes, *behavior_risks, *items])

    if "触" in joined:
        items.append("不要未经提醒直接触碰")
    if "噪音" in joined or "声音" in joined:
        items.append("不要突然提高音量")
    if "过渡" in joined:
        items.append("不要临时强拉离开当前活动")
    if "焦虑" in joined or "恐惧" in joined:
        items.append("不要连续追问原因")
    items.append("不要在多人围观下催促")
    return normalize_list(items, limit=6)


def build_high_friction_scenarios(
    child_age: int | None,
    triggers: list[str],
    behavior_risks: list[str],
    school_notes: str,
    selected_scenarios: list[str] | None = None,
) -> list[str]:
    scenarios: list[str] = selected_scenarios[:] if selected_scenarios else []
    joined = " ".join([*triggers, *behavior_risks, school_notes])
    if "过渡" in joined:
        scenarios.append("transition")
    if "睡" in joined or "夜醒" in joined:
        scenarios.append("bedtime")
    if "作业" in joined or "学习" in joined or (child_age is not None and child_age >= 6):
        scenarios.append("homework")
    if "陌生环境" in joined or "外出" in joined or "社交" in joined:
        scenarios.append("outing")
    if not scenarios:
        scenarios.append("transition")
    return normalize_list(scenarios, limit=4)


def build_school_context(source: Mapping[str, Any], onboarding_source: str | None = None) -> dict[str, Any]:
    context = {
        "child_name": str(source.get("child_name") or "").strip(),
        "child_age": source.get("child_age") if isinstance(source.get("child_age"), int) else None,
        "child_gender": source.get("child_gender"),
        "primary_caregiver": source.get("primary_caregiver"),
        "diagnosis_status": source.get("diagnosis_status"),
        "diagnosis_notes": str(source.get("diagnosis_notes") or "").strip(),
        "coexisting_conditions": normalize_list(source.get("coexisting_conditions") or [], limit=8),
        "family_members": normalize_list(source.get("family_members") or [], limit=8),
        "interests": normalize_list(source.get("interests") or [], limit=8),
        "likes": normalize_list(source.get("likes") or [], limit=8),
        "dislikes": normalize_list(source.get("dislikes") or [], limit=8),
        "sleep_challenges": normalize_list(source.get("sleep_challenges") or [], limit=8),
        "food_preferences": normalize_list(source.get("food_preferences") or [], limit=8),
        "allergies": normalize_list(source.get("allergies") or [], limit=8),
        "medical_needs": normalize_list(source.get("medical_needs") or [], limit=8),
        "medications": normalize_list(source.get("medications") or [], limit=8),
        "health_conditions": normalize_list(source.get("health_conditions") or [], limit=8),
        "behavior_patterns": normalize_list(source.get("behavior_patterns") or [], limit=8),
        "behavior_risks": normalize_list(source.get("behavior_risks") or [], limit=8),
        "emotion_patterns": normalize_list(source.get("emotion_patterns") or [], limit=8),
        "learning_needs": normalize_list(source.get("learning_needs") or [], limit=8),
        "school_type": source.get("school_type"),
        "social_training": normalize_list(source.get("social_training") or [], limit=8),
        "school_notes": str(source.get("school_notes") or "").strip(),
        "parent_schedule": normalize_list(source.get("parent_schedule") or [], limit=8),
        "parent_stressors": normalize_list(source.get("parent_stressors") or [], limit=8),
        "parent_support_actions": normalize_list(source.get("parent_support_actions") or [], limit=8),
        "parent_emotional_supports": normalize_list(source.get("parent_emotional_supports") or [], limit=8),
        "available_supporters": normalize_list(source.get("available_supporters") or [], limit=8),
        "taboo_behaviors": str(source.get("taboo_behaviors") or "").strip(),
    }
    if onboarding_source:
        context["onboarding_source"] = onboarding_source
    return context


def build_profile_fields(source: Mapping[str, Any], onboarding_source: str | None = None) -> dict[str, Any]:
    child_age = source.get("child_age")
    child_age_int = child_age if isinstance(child_age, int) else None
    communication_level = str(source.get("communication_level") or "short_sentence")
    triggers = normalize_list(source.get("triggers") or [], limit=8)
    sensory_flags = normalize_list(source.get("sensory_flags") or [], limit=8)
    custom_soothing = normalize_list(source.get("soothing_methods") or [], limit=8)
    context = build_school_context(source, onboarding_source=onboarding_source)
    behavior_risks = context["behavior_risks"]
    school_notes = str(context["school_notes"])
    taboo_behaviors = str(context["taboo_behaviors"])
    dislikes = context["dislikes"]

    return {
        "age_band": to_age_band(child_age_int),
        "language_level": communication_level,
        "sensory_flags": sensory_flags,
        "triggers": triggers,
        "soothing_methods": build_soothing_methods(
            triggers=triggers,
            sensory_flags=sensory_flags,
            communication_level=communication_level,
            custom_methods=custom_soothing,
        ),
        "donts": build_donts(
            taboo_behaviors=taboo_behaviors,
            triggers=triggers,
            sensory_flags=sensory_flags,
            dislikes=dislikes,
            behavior_risks=behavior_risks,
        ),
        "school_context": context,
        "high_friction_scenarios": build_high_friction_scenarios(
            child_age=child_age_int,
            triggers=triggers,
            behavior_risks=behavior_risks,
            school_notes=school_notes,
            selected_scenarios=normalize_list(source.get("high_friction_scenarios") or [], limit=4),
        ),
    }
