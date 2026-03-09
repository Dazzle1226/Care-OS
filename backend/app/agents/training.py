from __future__ import annotations

import json
from collections import defaultdict
from datetime import date as date_type, timedelta
from typing import Any, cast

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ChildProfile, DailyCheckin, Family, TrainingTaskFeedback
from app.schemas.domain import (
    TrainingAdjustment,
    TrainingFeedbackRead,
    TrainingFocusArea,
    TrainingGoal,
    TrainingPlanResponse,
    TrainingProgressItem,
    TrainingTask,
)
from app.services.llm_client import LLMClient, LLMUnavailableError

AREA_DEFS: dict[str, dict[str, str]] = {
    "emotion_regulation": {
        "title": "情绪调节与共调",
        "long_term_value": "先把情绪识别和降温做稳，后面的语言、社交和学习训练才有进入窗口。",
    },
    "communication": {
        "title": "沟通表达与理解",
        "long_term_value": "把需求表达从哭闹或拉扯转成可理解的表达，是很多场景稳定下来的基础。",
    },
    "social_interaction": {
        "title": "社交互动与共同注意",
        "long_term_value": "稳定的轮流、回应和共同注意，会直接提升家庭协作和外出适应。",
    },
    "sensory_regulation": {
        "title": "感官调节与自我安抚",
        "long_term_value": "先识别过载前兆并提前降刺激，可以减少很多升级和崩溃。",
    },
    "transition_flexibility": {
        "title": "过渡与灵活切换",
        "long_term_value": "过渡能力更稳后，作息、外出、学习和家庭合作都会更顺。",
    },
    "daily_living": {
        "title": "日常自理与任务执行",
        "long_term_value": "把任务拆成可起步的小步骤，有助于建立独立性和可持续家庭节奏。",
    },
}

SCENARIO_LABELS = {
    "transition": "活动切换/出门前",
    "bedtime": "睡前流程",
    "homework": "学习或坐下任务前",
    "outing": "外出或社交活动前",
}


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _first(values: list[str], fallback: str) -> str:
    for value in values:
        if value:
            return value
    return fallback


def _unique_trim(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def _contains_any(items: list[str], keywords: list[str]) -> bool:
    joined = " ".join(items)
    return any(keyword in joined for keyword in keywords)


def _scenario_label(key: str | None) -> str:
    return SCENARIO_LABELS.get(key or "", "日常关键场景")


def _serialize_feedback(item: TrainingTaskFeedback) -> TrainingFeedbackRead:
    return TrainingFeedbackRead(
        feedback_id=item.id,
        date=item.date,
        task_key=item.task_key,
        task_title=item.task_title,
        area_key=cast(Any, item.area_key),
        completion_status=cast(Any, item.completion_status),
        child_response=cast(Any, item.child_response),
        difficulty_rating=cast(Any, item.difficulty_rating),
        effect_score=item.effect_score,
        parent_confidence=item.parent_confidence,
        notes=item.notes,
    )


class TrainingAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _recent_checkins(self, db: Session, family_id: int, days: int = 7) -> list[DailyCheckin]:
        start_date = date_type.today() - timedelta(days=days - 1)
        return db.scalars(
            select(DailyCheckin)
            .where(DailyCheckin.family_id == family_id, DailyCheckin.date >= start_date)
            .order_by(desc(DailyCheckin.date))
        ).all()

    def _recent_feedbacks(self, db: Session, family_id: int, days: int = 14) -> list[TrainingTaskFeedback]:
        start_date = date_type.today() - timedelta(days=days - 1)
        return db.scalars(
            select(TrainingTaskFeedback)
            .where(TrainingTaskFeedback.family_id == family_id, TrainingTaskFeedback.date >= start_date)
            .order_by(desc(TrainingTaskFeedback.date), desc(TrainingTaskFeedback.id))
        ).all()

    def _fallback_plan(
        self,
        family: Family,
        profile: ChildProfile,
        checkins: list[DailyCheckin],
        feedbacks: list[TrainingTaskFeedback],
        extra_context: str,
    ) -> TrainingPlanResponse:
        context = profile.school_context or {}
        child_name = str(context.get("child_name") or "").strip() or "孩子"
        child_age = context.get("child_age")
        age_text = f"{child_age} 岁" if isinstance(child_age, int) else f"{profile.age_band} 岁段"
        interests = [str(item) for item in context.get("interests", []) if isinstance(item, str)]
        likes = [str(item) for item in context.get("likes", []) if isinstance(item, str)]
        learning_needs = [str(item) for item in context.get("learning_needs", []) if isinstance(item, str)]
        behavior_patterns = [str(item) for item in context.get("behavior_patterns", []) if isinstance(item, str)]
        emotion_patterns = [str(item) for item in context.get("emotion_patterns", []) if isinstance(item, str)]
        social_training = [str(item) for item in context.get("social_training", []) if isinstance(item, str)]
        supporters = [str(item) for item in context.get("available_supporters", []) if isinstance(item, str)]
        school_notes = str(context.get("school_notes") or "").strip()
        preferred_item = _first(interests + likes, "喜欢的物品")
        supporter = _first(supporters, "家长")
        soothing_primary = _first(profile.soothing_methods, "安静角落短暂停留")
        soothing_secondary = _first(profile.soothing_methods[1:], "短句确认 + 给两个选择")
        top_scenario = profile.high_friction_scenarios[0] if profile.high_friction_scenarios else "transition"
        scenario_text = _scenario_label(top_scenario)

        scores: dict[str, int] = {key: 0 for key in AREA_DEFS}
        reasons: dict[str, list[str]] = {key: [] for key in AREA_DEFS}
        profile_signals: dict[str, list[str]] = {key: [] for key in AREA_DEFS}
        recent_signals: dict[str, list[str]] = {key: [] for key in AREA_DEFS}

        def bump(area: str, score: int, reason: str, bucket: str) -> None:
            scores[area] = min(100, scores[area] + score)
            if reason not in reasons[area]:
                reasons[area].append(reason)
            target = profile_signals if bucket == "profile" else recent_signals
            if reason not in target[area]:
                target[area].append(reason)

        language_boost = {
            "none": 34,
            "single_word": 26,
            "short_sentence": 16,
            "fluent": 6,
        }.get(profile.language_level, 10)
        bump("communication", language_boost, f"当前语言水平为 {profile.language_level}，沟通支持仍需持续搭桥。", "profile")

        if _contains_any(learning_needs + [school_notes], ["表达", "沟通", "理解", "语言", "请求", "指令", "回应"]):
            bump("communication", 18, "档案里已经记录到沟通/理解相关训练需求。", "profile")
        if _contains_any(social_training + learning_needs + [school_notes], ["社交", "同伴", "轮流", "共同注意", "回应"]):
            bump("social_interaction", 18, "档案显示当前正在关注同伴互动、轮流或共同注意。", "profile")
        if social_training:
            bump("social_interaction", 8, "已经有社交训练目标，说明这一能力对当前生活影响较大。", "profile")
        if emotion_patterns or _contains_any(profile.triggers, ["焦虑", "恐惧", "崩溃", "情绪"]):
            bump("emotion_regulation", 14, "档案中存在明显情绪波动或触发器记录。", "profile")
        if profile.sensory_flags:
            bump(
                "sensory_regulation",
                min(24, len(profile.sensory_flags) * 7),
                f"已记录 {len(profile.sensory_flags)} 项感官敏感线索，需要预先降刺激。",
                "profile",
            )
        if _contains_any(profile.triggers, ["过渡", "等待", "变动", "排队"]) or "transition" in profile.high_friction_scenarios:
            bump("transition_flexibility", 24, "高摩擦点集中在过渡、等待或计划变化。", "profile")
        if "homework" in profile.high_friction_scenarios or "bedtime" in profile.high_friction_scenarios:
            bump("daily_living", 14, "作业/睡前流程已经成为高摩擦场景，需要拆步执行。", "profile")
        if _contains_any(learning_needs + behavior_patterns + [school_notes], ["自理", "穿衣", "刷牙", "吃饭", "作业", "专注", "坐定", "执行"]):
            bump("daily_living", 18, "档案中已有自理或任务执行相关需求。", "profile")

        avg_meltdown = _average([float(item.meltdown_count) for item in checkins])
        avg_transition = _average([item.transition_difficulty for item in checkins])
        caregiver_stress = _average([item.caregiver_stress for item in checkins])
        heavy_sensory_days = sum(1 for item in checkins if item.sensory_overload_level in {"medium", "heavy"})
        anxious_days = 0
        social_pressure_days = 0
        language_task_days = 0
        physical_discomfort_days = 0
        env_change_days = sum(1 for item in checkins if item.env_changes)
        latest_details = checkins[0].details_json if checkins else {}

        for checkin in checkins:
            details = checkin.details_json or {}
            mood = str(details.get("child_mood_state", "stable"))
            negative = [str(item) for item in details.get("negative_emotions", []) if isinstance(item, str)]
            activities = [str(item) for item in details.get("today_activities", []) if isinstance(item, str)]
            tasks = [str(item) for item in details.get("today_learning_tasks", []) if isinstance(item, str)]
            discomforts = [str(item) for item in details.get("physical_discomforts", []) if isinstance(item, str)]

            if mood in {"anxious", "irritable", "sensitive"} or negative:
                anxious_days += 1
            if any(keyword in " ".join(activities + negative) for keyword in ["社交", "学校", "同伴", "外出"]):
                social_pressure_days += 1
            if any(keyword in " ".join(tasks) for keyword in ["语言", "表达", "沟通", "理解"]):
                language_task_days += 1
            if discomforts:
                physical_discomfort_days += 1

        if avg_meltdown >= 2:
            bump("emotion_regulation", 24, f"近 7 天平均崩溃/冲突 {avg_meltdown:g} 次，情绪调节应先补齐。", "recent")
        elif avg_meltdown >= 1:
            bump("emotion_regulation", 14, f"近 7 天仍有持续情绪升级，平均 {avg_meltdown:g} 次。", "recent")

        if anxious_days >= 3:
            bump("emotion_regulation", 10, f"近 7 天有 {anxious_days} 天出现焦虑/烦躁信号。", "recent")
        if avg_transition >= 7:
            bump("transition_flexibility", 22, f"过渡难度均值 {avg_transition:g}/10，切换是当前核心难点。", "recent")
        elif avg_transition >= 5:
            bump("transition_flexibility", 12, f"过渡难度均值 {avg_transition:g}/10，仍需要专门练习。", "recent")

        if heavy_sensory_days >= 3:
            bump("sensory_regulation", 18, f"近 7 天有 {heavy_sensory_days} 天感官负荷达到中高水平。", "recent")
        elif heavy_sensory_days >= 1:
            bump("sensory_regulation", 10, f"近期已出现 {heavy_sensory_days} 天感官过载信号。", "recent")

        if physical_discomfort_days >= 2:
            bump("sensory_regulation", 8, "身体不适与感官压力叠加，任务要更短更稳。", "recent")
        if social_pressure_days >= 2:
            bump("social_interaction", 12, "近期在学校/外出相关情境下更容易出现压力反应。", "recent")
        if language_task_days >= 2:
            bump("communication", 10, "近期签到中持续出现语言训练任务，说明沟通目标正在反复影响日常。", "recent")
        if env_change_days >= 2:
            bump("transition_flexibility", 8, "环境变化频繁时，孩子更需要清晰预告与切换支持。", "recent")

        recent_feedback_window = feedbacks[:7]
        feedback_by_area: dict[str, list[TrainingTaskFeedback]] = defaultdict(list)
        for item in feedbacks:
            feedback_by_area[item.area_key].append(item)

        done_total = sum(1 for item in recent_feedback_window if item.completion_status == "done")
        partial_total = sum(1 for item in recent_feedback_window if item.completion_status == "partial")
        missed_total = sum(1 for item in recent_feedback_window if item.completion_status == "missed")
        overloaded_total = sum(1 for item in recent_feedback_window if item.child_response == "overloaded")
        avg_effect = _average([item.effect_score for item in recent_feedback_window])
        avg_confidence = _average([item.parent_confidence for item in recent_feedback_window])

        for area_key, items in feedback_by_area.items():
            done = sum(1 for item in items if item.completion_status == "done")
            missed = sum(1 for item in items if item.completion_status == "missed")
            too_hard = sum(1 for item in items if item.difficulty_rating == "too_hard")
            area_effect = _average([item.effect_score for item in items[:5]])
            if missed >= max(1, done):
                bump(area_key, 10, "最近这类任务完成度偏低，需要把目标再拆小。", "recent")
            if too_hard >= 1:
                bump(area_key, 8, "最近反馈显示当前难度偏高，需要先做更容易开始的版本。", "recent")
            if done >= 2 and area_effect >= 8:
                scores[area_key] = max(0, scores[area_key] - 4)
                signal = "最近这一块已有正向反馈，可以开始考虑从固定练习转向场景泛化。"
                if signal not in recent_signals[area_key]:
                    recent_signals[area_key].append(signal)

        ranked = sorted(
            AREA_DEFS.keys(),
            key=lambda key: (scores[key], -list(AREA_DEFS).index(key)),
            reverse=True,
        )
        top_keys = ranked[:3]

        for area in top_keys:
            if not reasons[area]:
                bump(area, 8, "当前资料较少，先用低负担练习建立观察基线。", "recent")

        load_level = "standard"
        if caregiver_stress >= 7.5 or overloaded_total >= 2 or missed_total > done_total:
            load_level = "light"
        elif feedbacks:
            load_level = "adaptive"

        latest_tasks = [str(item) for item in latest_details.get("today_learning_tasks", []) if isinstance(item, str)]
        latest_activities = [str(item) for item in latest_details.get("today_activities", []) if isinstance(item, str)]

        focus_areas: list[TrainingFocusArea] = []
        for area in top_keys:
            urgency = "watch"
            if scores[area] >= 70:
                urgency = "urgent"
            elif scores[area] >= 48:
                urgency = "high"

            why_now = _unique_trim(
                reasons[area]
                + [f"当前先补 {AREA_DEFS[area]['title']}，更容易带动其它训练一起稳定。"],
                4,
            )
            if len(why_now) < 2:
                why_now.append("先做这一块，是为了把训练重新放回孩子可以进入的状态。")

            focus_areas.append(
                TrainingFocusArea(
                    area_key=cast(Any, area),
                    title=AREA_DEFS[area]["title"],
                    priority_score=scores[area],
                    urgency=cast(Any, urgency),
                    why_now=why_now[:4],
                    profile_signals=_unique_trim(profile_signals[area], 3),
                    recent_signals=_unique_trim(recent_signals[area], 3),
                    long_term_value=AREA_DEFS[area]["long_term_value"],
                )
            )

        def difficulty_for(area: str) -> str:
            items = feedback_by_area.get(area, [])
            done = sum(1 for item in items if item.completion_status == "done")
            too_hard = sum(1 for item in items if item.difficulty_rating == "too_hard")
            area_effect = _average([item.effect_score for item in items[:5]])
            if done >= 2 and area_effect >= 8 and too_hard == 0:
                return "advance"
            if done + sum(1 for item in items if item.completion_status == "partial") >= 2 and area_effect >= 6:
                return "build"
            return "starter"

        def duration_for(area: str) -> int:
            base = {"starter": 10, "build": 12, "advance": 15}[difficulty_for(area)]
            if load_level == "light":
                base -= 2
            if area == "social_interaction" and difficulty_for(area) == "advance":
                base += 2
            return max(8, min(18, base))

        def schedule_for(area: str) -> str:
            latest_activity = _first(latest_activities, scenario_text)
            return {
                "emotion_regulation": "情绪刚起波动的前 3 分钟内",
                "communication": "孩子想要东西或需要帮助时",
                "social_interaction": f"{latest_activity} 前后各 1 个短回合",
                "sensory_regulation": "放学后/环境开始变吵之前",
                "transition_flexibility": f"{scenario_text} 前 5-10 分钟",
                "daily_living": "晚间固定流程或坐下任务开始前",
            }[area]

        def build_task(area: str, slot_idx: int) -> TrainingTask:
            task_key = f"{area}_{slot_idx + 1}"
            difficulty = cast(Any, difficulty_for(area))
            duration = duration_for(area)
            schedule_hint = schedule_for(area)

            if area == "emotion_regulation":
                return TrainingTask(
                    task_key=task_key,
                    title=f"{preferred_item}情绪温度计",
                    area_key=cast(Any, area),
                    duration_minutes=duration,
                    schedule_hint=schedule_hint,
                    objective="先让孩子能指出自己处在什么状态，再从两个冷静动作里做选择。",
                    materials=[preferred_item, "表情卡/温度计", soothing_primary],
                    steps=[
                        f"用 {preferred_item} 或孩子喜欢的图片，把状态分成“平静/紧张/快爆发”三个档。",
                        f"家长先帮 {child_name} 命名当下感受，再给两个可选动作：{soothing_primary} 或 {soothing_secondary}。",
                        "结束后只记录是否更快回到可继续活动的状态，不追求说完整原因。",
                    ],
                    parent_script=f"{child_name}，我看到你现在有点不舒服，我们先选一个让身体慢下来的办法。",
                    coaching_tip="先命名感受，再给选择，不连续追问原因。",
                    success_signals=["能指出当前状态", "愿意从两个动作里选一个", "恢复时间比之前更短"],
                    fallback_plan="如果一开始就抗拒，只保留“家长命名情绪 + 带到安静点”这一步。",
                    difficulty=difficulty,
                )

            if area == "communication":
                return TrainingTask(
                    task_key=task_key,
                    title="需求表达二选一",
                    area_key=cast(Any, area),
                    duration_minutes=duration,
                    schedule_hint=schedule_hint,
                    objective="把拉扯、哭闹或僵住，转成指物、二选一或一句请求。",
                    materials=[preferred_item, "二选一卡", "图片/手势提示"],
                    steps=[
                        f"拿出 {preferred_item} 或孩子当前最想要的东西，先制造一个自然请求机会。",
                        "只给两个固定表达入口：指一指 / 说一个词或短句，不追加开放式提问。",
                        "孩子一旦有任何主动表达，立刻回应并示范更完整一点的版本。",
                    ],
                    parent_script="你可以指给我看，或者告诉我“要这个/不要这个”，我会马上帮你。",
                    coaching_tip="等待 3-5 秒再补第二提示，避免家长替孩子说完。",
                    success_signals=["能主动发起请求", "提示次数减少", "哭闹前能出现替代表达"],
                    fallback_plan="如果今天状态差，就只做指物或点卡，不要求开口。",
                    difficulty=difficulty,
                )

            if area == "social_interaction":
                return TrainingTask(
                    task_key=task_key,
                    title=f"{supporter}轮流互动 3 回合",
                    area_key=cast(Any, area),
                    duration_minutes=duration,
                    schedule_hint=schedule_hint,
                    objective="在可控场景里练回应、轮流和共同注意，不直接上高难社交。",
                    materials=[preferred_item, supporter, "轮流提示卡"],
                    steps=[
                        f"由 {supporter} 和孩子围绕 {preferred_item} 做一个极短轮流游戏，每次只轮 3 回合。",
                        "每轮开始前只说一句提示，例如“轮到你/轮到我”，不临时加规则。",
                        "结束时让孩子和家长一起回看“刚才我们做到了哪一步”，哪怕只完成 1 回合也算成功。",
                    ],
                    parent_script="现在轮到你一下，我做完就轮到你，我们只玩三个回合。",
                    coaching_tip="把社交目标压缩到回应和轮流，不在一次练习里塞进分享、对话、规则三件事。",
                    success_signals=["能接受轮流开始", "至少完成 1-3 个回合", "抗拒低于之前的互动练习"],
                    fallback_plan="如果对人反应压力大，先改成家长和孩子共同看同一件物品，不要求轮流。",
                    difficulty=difficulty,
                )

            if area == "sensory_regulation":
                return TrainingTask(
                    task_key=task_key,
                    title="感官前兆识别 + 快速降载",
                    area_key=cast(Any, area),
                    duration_minutes=duration,
                    schedule_hint=schedule_hint,
                    objective="让孩子和家长更早发现过载前兆，并有一个固定降载动作。",
                    materials=["身体部位图", soothing_primary, "安静角落/耳罩"],
                    steps=[
                        "回顾今天或最近一次不舒服时身体的样子，比如捂耳、躲开、发硬、走来走去。",
                        f"把前兆和一个固定动作绑在一起：一出现信号，就先做 {soothing_primary}。",
                        "练完后记录哪一个前兆最早出现，下次优先在那一步介入。",
                    ],
                    parent_script="一觉得太吵/太挤，我们先做固定的安静动作，不急着继续任务。",
                    coaching_tip="感官练习重点是提前识别，不是要求孩子在高刺激里硬扛。",
                    success_signals=["能指出至少一个前兆", "愿意接受固定降载动作", "升级前能提前暂停"],
                    fallback_plan="如果孩子不愿回顾身体感觉，就直接练“看到信号立刻去安静点”这一条。",
                    difficulty=difficulty,
                )

            if area == "transition_flexibility":
                return TrainingTask(
                    task_key=task_key,
                    title="视觉倒计时过渡练习",
                    area_key=cast(Any, area),
                    duration_minutes=duration,
                    schedule_hint=schedule_hint,
                    objective="把切换前的不可预期，变成看得见、数得清、做得到的三步。",
                    materials=["视觉倒计时", "先后卡", preferred_item],
                    steps=[
                        f"在 {scenario_text} 前 5 分钟出示“先做什么、再做什么”的两步卡片。",
                        "让孩子自己按一次计时器或翻一次卡，家长只保留一句提醒，不重复催促。",
                        f"一完成切换，立刻给一个短回报，例如碰一下喜欢的 {preferred_item} 或口头确认。",
                    ],
                    parent_script="还有一点时间就要切换了，我会先告诉你，再陪你做最后一步。",
                    coaching_tip="切换前不要再追加新要求，也不要临时改变下一步。",
                    success_signals=["接受倒计时出现", "切换延迟时间缩短", "升级频率下降"],
                    fallback_plan="如果一看到倒计时就反感，先只保留“口头预告 + 一起收 1 件物品”。",
                    difficulty=difficulty,
                )

            return TrainingTask(
                task_key=task_key,
                title="分步任务启动练习",
                area_key=cast(Any, area),
                duration_minutes=duration,
                schedule_hint=schedule_hint,
                objective="把需要做但难以开始的任务，压缩到第一步就能进入。",
                materials=["步骤卡", preferred_item, "计时器"],
                steps=[
                    "先把目标任务只拆成 2-3 个最小步骤，并明确告诉孩子今天只做第一段。",
                    "每做完一步就立即打钩或翻卡，不在过程中补新的口头要求。",
                    "结束时一起看“今天做成了哪一步”，比完整完成更重要的是成功起步。",
                ],
                parent_script="今天我们只先做第一小步，做完就停，不一次做完也没关系。",
                coaching_tip="把“开始任务”本身当训练目标，而不是把完成整件事当目标。",
                success_signals=["能更快坐下来开始", "中途需要的提示减少", "对任务的抗拒下降"],
                fallback_plan="如果一开始就卡住，先改成家长带着做 10 秒，再立即结束。",
                difficulty=difficulty,
            )

        tasks = [build_task(area, idx) for idx, area in enumerate(top_keys)]

        short_term_goals = [
            TrainingGoal(
                title=f"本周先补 {focus_areas[0].title}",
                target=f"每天至少完成 1 次 {focus_areas[0].title} 主任务，先追求可开始，不追求做满。",
                success_marker="连续 4 天出现完成或部分完成即可视为稳定进入阶段。",
            ),
            TrainingGoal(
                title="把练习嵌入真实场景",
                target=f"优先放进 {scenario_text} 或签到里最常出现的困难时段，而不是另起整块训练时间。",
                success_marker="本周至少有 2 次在真实场景中提前用上训练动作。",
            ),
            TrainingGoal(
                title="同步记录有效提示",
                target="每次训练结束只记一条最有效的提示语或动作，为下次减负做依据。",
                success_marker="本周能留下 3 条以上有效/无效线索。",
            ),
        ]

        second_title = focus_areas[1].title if len(focus_areas) > 1 else focus_areas[0].title
        long_term_goals = [
            TrainingGoal(
                title="1-2 个月内建立稳定套路",
                target=f"让 {focus_areas[0].title} 从单次任务，变成孩子在固定场景里更容易接受的日常流程。",
                success_marker="同类高摩擦场景的升级频率较当前基线明显下降。",
            ),
            TrainingGoal(
                title="逐步泛化到第二能力面",
                target=f"在 {focus_areas[0].title} 稳住后，带动 {second_title} 的自然场景练习，而不是一直停留在桌面训练。",
                success_marker="家长能报告至少 2 个家庭/外出场景出现迁移效果。",
            ),
        ]

        guidance = _unique_trim(
            [
                f"训练前先确认孩子是否能接受 {soothing_primary}，状态差时先调节再训练。",
                "每次任务只保留一个主要目标和一句核心提示词，避免边做边加码。",
                f"如果家里多人参与，请让 {supporter} 也使用同样的话术和同样的步骤顺序。",
                "孩子出现抗拒时先回到更小的一步，不把当天完成量当成唯一标准。",
                "训练后只记录最有效的一条做法，为下一次调整提供依据。",
            ],
            5,
        )

        adjustments: list[TrainingAdjustment] = []
        if load_level == "light":
            adjustments.append(
                TrainingAdjustment(
                    title="先减负",
                    suggestion="本周单次训练控制在 8-10 分钟，每天只抓 1 个主任务，其余只做观察和泛化。",
                    reason="最近孩子或家长负荷偏高，先保住可执行性比追求任务数量更重要。",
                )
            )
        if overloaded_total >= 1 or any(item.difficulty == "starter" for item in tasks):
            adjustments.append(
                TrainingAdjustment(
                    title="先降难度再稳定",
                    suggestion="优先做“家长示范 1 次 + 孩子尝试 1 次”的版本，不要求完整完成全部步骤。",
                    reason="最近反馈里已经出现过载或难度过高的信号。",
                )
            )
        if done_total >= 2 and avg_effect >= 8:
            adjustments.append(
                TrainingAdjustment(
                    title="开始做泛化",
                    suggestion=f"把最稳定的任务从固定练习转到 {scenario_text} 这个真实场景里再跑一次。",
                    reason="已有连续正向反馈，继续只做桌面练习的边际收益会下降。",
                )
            )
        adjustments.append(
            TrainingAdjustment(
                title="固定开始条件",
                suggestion=f"尽量把主任务放在 {schedule_for(top_keys[0])}，连续几天用同一个开场句和同一个结束动作。",
                reason="可预期的开始条件有助于降低抗拒，提高进入速度。",
            )
        )
        if supporters:
            adjustments.append(
                TrainingAdjustment(
                    title="共享执行方式",
                    suggestion=f"让 {supporter} 也参与至少 1 次同样的练习，减少只有一个照护者能带动的情况。",
                    reason="同一能力如果只在一个人、一种语气下成立，后续泛化会很慢。",
                )
            )
        if len(adjustments) < 2:
            adjustments.append(
                TrainingAdjustment(
                    title="先保住主任务",
                    suggestion="每天先只盯住 1 个最关键任务，另外两项只作为可选泛化，不因为没做全就推翻整天训练。",
                    reason="当数据还少时，先保证可持续执行，比一次塞太多内容更重要。",
                )
            )
        adjustments = adjustments[:4]

        total_feedback = len(recent_feedback_window)
        positive_total = sum(1 for item in recent_feedback_window if item.child_response in {"engaged", "accepted"})
        completion_rate = int(round(((done_total + partial_total * 0.5) / max(total_feedback, 1)) * 100)) if total_feedback else 0
        positive_rate = int(round((positive_total / max(total_feedback, 1)) * 100)) if total_feedback else 0
        confidence_rate = int(round(avg_confidence * 10)) if total_feedback else 0

        progress = [
            TrainingProgressItem(
                label="近 7 天完成率",
                value=completion_rate,
                target=100,
                summary=f"{total_feedback} 次反馈里，完成 {done_total} 次，部分完成 {partial_total} 次。",
            ),
            TrainingProgressItem(
                label="孩子接受度",
                value=positive_rate,
                target=100,
                summary="统计 engaged/accepted 的占比，关注能否在不过载前进入任务。",
            ),
            TrainingProgressItem(
                label="家长执行信心",
                value=confidence_rate,
                target=100,
                summary="根据家长每次打卡的执行信心换算，信心下降时优先减负。",
            ),
        ]

        if total_feedback:
            recent_feedback_summary = (
                f"近 7 天共记录 {total_feedback} 次训练打卡，完成 {done_total} 次，平均有效度 {avg_effect:g}/10。"
                f" 当前更需要关注的是{'难度过高' if missed_total >= done_total or overloaded_total else '把稳定做法继续重复'}。"
            )
        else:
            recent_feedback_summary = "还没有训练打卡数据，建议先完成今天第 1 个任务，再根据孩子反应决定是否减负或进阶。"

        child_summary = (
            f"{child_name}，{age_text}，当前以 {profile.language_level} 沟通为主；"
            f"档案里高频触发器包括 {'、'.join(profile.triggers[:2]) if profile.triggers else '过渡和环境变化'}，"
            f"最近 7 天平均崩溃 {avg_meltdown:g} 次、过渡难度 {avg_transition:g}/10。"
        )

        extra_summary = f" 家长补充：{extra_context.strip()}。" if extra_context.strip() else ""
        latest_task_hint = f" 最近签到里还出现过 {'、'.join(latest_tasks[:2])} 等任务。" if latest_tasks else ""
        load_text = {
            "light": "低负荷节奏",
            "standard": "标准节奏",
            "adaptive": "动态调节节奏",
        }[load_level]
        plan_summary = (
            f"这轮计划优先补 {focus_areas[0].title}，再带动 {focus_areas[1].title} 和 {focus_areas[2].title}。"
            f" 本周先采用{load_text}，把训练嵌进 {scenario_text} 这样的真实场景。"
            f"{latest_task_hint}{extra_summary}"
        ).strip()

        return TrainingPlanResponse(
            family_id=family.family_id,
            child_summary=child_summary,
            plan_summary=plan_summary,
            primary_need=focus_areas[0].title,
            load_level=cast(Any, load_level),
            focus_areas=focus_areas,
            short_term_goals=short_term_goals,
            long_term_goals=long_term_goals,
            daily_tasks=tasks,
            guidance=guidance[:5],
            adjustments=adjustments[:4],
            progress=progress,
            recent_feedback_summary=recent_feedback_summary,
            recent_feedbacks=[_serialize_feedback(item) for item in feedbacks[:6]],
        )

    def _attempt_llm_plan(
        self,
        family: Family,
        profile: ChildProfile,
        checkins: list[DailyCheckin],
        feedbacks: list[TrainingTaskFeedback],
        extra_context: str,
        candidate: TrainingPlanResponse,
    ) -> TrainingPlanResponse:
        context = profile.school_context or {}
        payload = {
            "task": "基于家庭档案、近7天签到和训练反馈，输出ASD个性化能力筛选与训练计划。",
            "family_id": family.family_id,
            "profile": {
                "age_band": profile.age_band,
                "language_level": profile.language_level,
                "sensory_flags": profile.sensory_flags,
                "triggers": profile.triggers,
                "soothing_methods": profile.soothing_methods,
                "high_friction_scenarios": profile.high_friction_scenarios,
                "school_context": context,
            },
            "recent_checkins": [
                {
                    "date": item.date.isoformat(),
                    "meltdown_count": item.meltdown_count,
                    "transition_difficulty": item.transition_difficulty,
                    "sensory_overload_level": item.sensory_overload_level,
                    "caregiver_stress": item.caregiver_stress,
                    "details": item.details_json,
                }
                for item in checkins[:7]
            ],
            "recent_feedbacks": [
                {
                    "date": item.date.isoformat(),
                    "task_key": item.task_key,
                    "task_title": item.task_title,
                    "area_key": item.area_key,
                    "completion_status": item.completion_status,
                    "child_response": item.child_response,
                    "difficulty_rating": item.difficulty_rating,
                    "effect_score": item.effect_score,
                    "parent_confidence": item.parent_confidence,
                    "notes": item.notes,
                }
                for item in feedbacks[:8]
            ],
            "extra_context": extra_context,
            "candidate_plan": candidate.model_dump(),
            "constraints": {
                "focus_areas_max": 3,
                "daily_tasks_exact": 3,
                "short_term_goals_max": 3,
                "long_term_goals_max": 3,
                "guidance_max": 5,
                "adjustments_max": 4,
                "recent_feedbacks_max": 6,
            },
        }
        raw = self.llm.generate_json(
            system_prompt="你是 ASD 家庭能力训练规划助手。只输出合法 JSON，不要解释。",
            user_prompt=json.dumps(payload, ensure_ascii=False),
        )
        return TrainingPlanResponse.model_validate(raw)

    def generate_plan(self, db: Session, family: Family, extra_context: str = "") -> TrainingPlanResponse:
        profile = family.child_profile
        if profile is None:
            raise ValueError("Family profile not found")

        checkins = self._recent_checkins(db=db, family_id=family.family_id)
        feedbacks = self._recent_feedbacks(db=db, family_id=family.family_id)
        candidate = self._fallback_plan(
            family=family,
            profile=profile,
            checkins=checkins,
            feedbacks=feedbacks,
            extra_context=extra_context,
        )

        try:
            return self._attempt_llm_plan(
                family=family,
                profile=profile,
                checkins=checkins,
                feedbacks=feedbacks,
                extra_context=extra_context,
                candidate=candidate,
            )
        except (LLMUnavailableError, ValueError, TypeError, json.JSONDecodeError):
            return candidate

    def next_adjustment(
        self,
        completion_status: str,
        child_response: str,
        difficulty_rating: str,
        effect_score: float,
    ) -> str:
        if child_response == "overloaded" or difficulty_rating == "too_hard":
            return "下次先把时长压到 8 分钟，并把任务拆成“示范 1 次 + 尝试 1 次”。"
        if completion_status == "missed":
            return "下次先换到更容易开始的时段，用偏好物做开场，不强行补做。"
        if completion_status == "done" and effect_score >= 8:
            return "下次先在同一场景稳定一次，再把同样能力迁移到另一个真实场景。"
        return "下次保持同一目标，但减少一句提示或增加一个更明显的视觉线索。"
