from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models import ChildProfile, Family, User
from app.schemas.domain import (
    ChildProfileRead,
    FamilyRead,
    OnboardingSetupRequest,
    OnboardingSetupResponse,
    OnboardingSnapshot,
    OnboardingSupportCard,
)
from app.services.profile_builder import build_profile_fields, normalize_list

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

SAMPLE_ONBOARDING: dict[str, object] = {
    "family_name": "示例家庭",
    "timezone": "Asia/Shanghai",
    "child_name": "乐乐",
    "child_age": 7,
    "child_gender": "female",
    "primary_caregiver": "parents",
    "diagnosis_status": "asd",
    "diagnosis_notes": "医生提示伴随焦虑反应，近期重点处理过渡和外出。",
    "communication_level": "short_sentence",
    "coexisting_conditions": ["焦虑倾向"],
    "family_members": ["妈妈", "爸爸", "外婆"],
    "interests": ["积木", "地铁", "水彩"],
    "likes": ["固定路线", "提前知道流程", "安静空间"],
    "dislikes": ["突然催促", "陌生人靠近", "太吵的环境"],
    "triggers": ["过渡", "噪音", "陌生环境"],
    "sensory_flags": ["声音敏感", "触感敏感"],
    "soothing_methods": ["提前预告", "安静角落", "视觉倒计时"],
    "taboo_behaviors": "不要突然拉走；不要连续追问；不要在很多人面前催促",
    "sleep_challenges": ["夜醒", "入睡慢"],
    "food_preferences": ["偏爱软糯食物", "不喜欢混合口感"],
    "allergies": ["花生过敏"],
    "medical_needs": ["外出随身带过敏药"],
    "medications": ["舍曲林 12.5mg / 晚"],
    "health_conditions": ["轻度便秘"],
    "behavior_patterns": ["遇到变动会反复确认", "压力大时会躲进角落"],
    "behavior_risks": ["哭闹", "攻击他人"],
    "emotion_patterns": ["焦虑", "易怒"],
    "learning_needs": ["需要视觉提示", "两步以内指令"],
    "school_type": "mainstream",
    "social_training": ["社交小组", "言语训练"],
    "school_notes": "普通小学融合班，和 1 位固定同学关系较好。",
    "high_friction_scenarios": ["transition", "outing"],
    "parent_schedule": ["工作日白天上班", "晚上主要陪伴"],
    "parent_stressors": ["照护任务", "睡眠不足", "缺乏社交支持"],
    "parent_support_actions": ["每周参加一次家长支持群", "周末配偶接手半天"],
    "parent_emotional_supports": ["伴侣倾听", "朋友聊天"],
    "available_supporters": ["配偶", "外婆", "朋友"],
}

GENDER_LABELS = {"male": "男", "female": "女", "other": "其他"}
CAREGIVER_LABELS = {
    "parents": "父母",
    "grandparents": "祖父母",
    "relative": "亲戚",
    "other": "其他照护者",
}
DIAGNOSIS_LABELS = {
    "asd": "自闭症谱系障碍（ASD）",
    "none": "没有诊断",
    "under_assessment": "评估中",
    "other": "其他情况",
}
COMMUNICATION_LABELS = {
    "none": "无语言",
    "single_word": "少量词汇",
    "short_sentence": "短句流利",
    "fluent": "流利语言",
}
SCENARIO_LABELS = {
    "transition": "过渡期",
    "bedtime": "睡前流程",
    "homework": "学习任务",
    "outing": "外出与社交",
}
SCHOOL_TYPE_LABELS = {
    "mainstream": "普通学校/融合环境",
    "special": "特教学校/资源班",
    "home": "居家教育/灵活学习",
    "other": "其他",
}


def _merge_payload(payload: OnboardingSetupRequest) -> dict[str, object]:
    source = dict(SAMPLE_ONBOARDING) if payload.use_sample else {}
    for key, value in payload.model_dump().items():
        if key == "use_sample":
            continue
        if payload.use_sample and value in (None, "", []):
            continue
        source[key] = value
    return source


def _ctx_list(context: dict[str, object], key: str, fallback: str) -> list[str]:
    values = normalize_list(context.get(key) or [], limit=8)
    return values or [fallback]


def _primary_focus(profile: ChildProfile) -> tuple[str, str]:
    scenario_key = profile.high_friction_scenarios[0] if profile.high_friction_scenarios else "transition"
    trigger = profile.triggers[0] if profile.triggers else "过渡"
    return scenario_key, trigger


def _build_snapshot(profile: ChildProfile) -> OnboardingSnapshot:
    context = profile.school_context or {}
    child_name = str(context.get("child_name") or "孩子")
    child_age = context.get("child_age")
    gender_text = GENDER_LABELS.get(str(context.get("child_gender")), "未说明")
    caregiver_text = CAREGIVER_LABELS.get(str(context.get("primary_caregiver")), "未说明")
    diagnosis_text = DIAGNOSIS_LABELS.get(str(context.get("diagnosis_status")), "未填写")
    communication_text = COMMUNICATION_LABELS.get(profile.language_level, profile.language_level)
    school_type = SCHOOL_TYPE_LABELS.get(str(context.get("school_type")), "未填写")
    age_text = f"{child_age} 岁" if isinstance(child_age, int) else f"{profile.age_band} 岁段"
    coexisting = _ctx_list(context, "coexisting_conditions", "暂未记录共病/伴随问题")
    family_members = _ctx_list(context, "family_members", "暂未填写家庭成员")
    interests = _ctx_list(context, "interests", "暂未记录明显兴趣")
    likes = _ctx_list(context, "likes", "暂未记录稳定偏好")
    dislikes = _ctx_list(context, "dislikes", "暂未记录明显不喜欢")
    sleep_challenges = _ctx_list(context, "sleep_challenges", "暂未记录明显睡眠困扰")
    food_preferences = _ctx_list(context, "food_preferences", "暂未记录明显饮食偏好")
    allergies = _ctx_list(context, "allergies", "暂未记录过敏")
    medical_needs = _ctx_list(context, "medical_needs", "暂未记录特殊医疗需求")
    medications = _ctx_list(context, "medications", "暂未记录用药")
    health_conditions = _ctx_list(context, "health_conditions", "暂未记录其他健康问题")
    behavior_patterns = _ctx_list(context, "behavior_patterns", "暂未记录固定行为模式")
    behavior_risks = _ctx_list(context, "behavior_risks", "暂未记录高风险行为")
    emotion_patterns = _ctx_list(context, "emotion_patterns", "暂未记录主要情绪波动")
    learning_needs = _ctx_list(context, "learning_needs", "暂未记录学习支持需求")
    social_training = _ctx_list(context, "social_training", "暂未记录社交/康复训练")
    school_notes = str(context.get("school_notes") or "暂未补充学校与社交圈信息").strip()
    parent_schedule = _ctx_list(context, "parent_schedule", "暂未记录家长时间安排")
    parent_stressors = _ctx_list(context, "parent_stressors", "暂未填写压力源")
    parent_support_actions = _ctx_list(context, "parent_support_actions", "暂未记录支持性活动")
    parent_emotional_supports = _ctx_list(context, "parent_emotional_supports", "暂未记录情感支持来源")
    supporters = _ctx_list(context, "available_supporters", "暂未标记可用支持者")
    scenario_key, trigger = _primary_focus(profile)
    focus_label = SCENARIO_LABELS.get(scenario_key, "当前高摩擦场景")

    resource_summary = [
        f"低成本工具优先：{'、'.join(profile.soothing_methods[:2]) if profile.soothing_methods else '提前预告、安静角落'}",
        f"共享禁忌提醒：{'、'.join(profile.donts[:2]) if profile.donts else '先提醒后接触、避免多人围观催促'}",
        f"协作切入口：{focus_label} 先由最稳定的照护者接手。",
        f"当前支持者：{'、'.join(supporters[:3])}",
    ]

    diagnosis_notes = str(context.get("diagnosis_notes") or "").strip()
    child_overview = [
        f"{child_name}，{age_text}，性别：{gender_text}",
        f"诊断情况：{diagnosis_text}",
        f"共病 / 伴随问题：{'、'.join(coexisting[:3])}",
        f"主要照护者：{caregiver_text}，家庭成员：{'、'.join(family_members[:4])}",
        f"沟通能力：{communication_text}",
    ]
    if diagnosis_notes:
        child_overview.append(f"诊断补充：{diagnosis_notes}")

    return OnboardingSnapshot(
        child_overview=child_overview[:6],
        preference_summary=[
            f"兴趣：{'、'.join(interests[:4])}",
            f"喜欢：{'、'.join(likes[:4])}",
            f"不喜欢：{'、'.join(dislikes[:4])}",
        ],
        health_summary=[
            f"睡眠：{'、'.join(sleep_challenges[:3])}",
            f"饮食：{'、'.join(food_preferences[:3])}",
            f"过敏 / 医疗需求：{'、'.join((allergies + medical_needs)[:4])}",
            f"药物 / 健康问题：{'、'.join((medications + health_conditions)[:4])}",
        ],
        behavior_summary=[
            f"固定行为模式：{'、'.join(behavior_patterns[:4])}",
            f"高风险行为：{'、'.join(behavior_risks[:4])}",
            f"情绪波动：{'、'.join(emotion_patterns[:4])}",
        ],
        learning_summary=[
            f"学习支持：{'、'.join(learning_needs[:4])}",
            f"高摩擦场景：{'、'.join(profile.high_friction_scenarios[:3] or ['transition'])}",
        ],
        social_summary=[
            f"教育环境：{school_type}",
            f"训练 / 支持：{'、'.join(social_training[:4])}",
            f"学校与社交：{school_notes}",
        ],
        trigger_summary=profile.triggers[:4] or ["暂未记录明确触发器"],
        sensory_summary=profile.sensory_flags[:4] or ["暂未记录明显感官敏感"],
        soothing_summary=profile.soothing_methods[:4] or ["建议先建立一个固定安静角落"],
        caregiver_pressure=parent_stressors[:4],
        supporter_summary=supporters[:4],
        parent_support_summary=[
            f"家长日程：{'、'.join(parent_schedule[:4])}",
            f"支持性活动：{'、'.join(parent_support_actions[:4])}",
            f"情感支持：{'、'.join(parent_emotional_supports[:4])}",
        ],
        resource_summary=resource_summary[:4],
        recommended_focus=f"先稳定 {focus_label}，尤其留意“{trigger}”相关触发，并把今日任务降到最小可执行步骤。",
    )


def _build_support_cards(profile: ChildProfile) -> list[OnboardingSupportCard]:
    context = profile.school_context or {}
    child_name = str(context.get("child_name") or "孩子")
    parent_stressors = _ctx_list(context, "parent_stressors", "照护任务")
    supporters = _ctx_list(context, "available_supporters", "一位固定支持者")
    support_actions = _ctx_list(context, "parent_support_actions", "留出 15 分钟微喘息")
    scenario_key, trigger = _primary_focus(profile)
    focus_label = SCENARIO_LABELS.get(scenario_key, "高摩擦场景")

    return [
        OnboardingSupportCard(
            card_id="ONB-CHILD",
            icon="child",
            title=f"{focus_label}应对卡",
            summary=f"围绕“{trigger}”先降刺激，再给 {child_name} 一个可预测的下一步。",
            bullets=[
                f"先说观察：我看到 {child_name} 现在被“{trigger}”卡住了。",
                f"优先使用：{profile.soothing_methods[0] if profile.soothing_methods else '提前预告 + 安静角落'}。",
                f"避免：{profile.donts[0] if profile.donts else '临时强拉或连续追问'}。",
            ],
        ),
        OnboardingSupportCard(
            card_id="ONB-PARENT",
            icon="parent",
            title="家长减压卡",
            summary=f"当前优先缓解“{parent_stressors[0]}”带来的持续透支，先保留可执行空间。",
            bullets=[
                "把今天目标缩成一件事，其余改为可延期任务。",
                f"优先尝试：{support_actions[0]}。",
                "当指令开始变多时，先停 10 秒，再只说下一步。",
            ],
        ),
        OnboardingSupportCard(
            card_id="ONB-TEAM",
            icon="team",
            title="家庭协作卡",
            summary=f"把 {focus_label} 的分工先交给 {supporters[0]} 或最稳定的支持者，降低单人硬扛。",
            bullets=[
                f"把触发器、安抚方式和禁忌各挑 1 条发给 {supporters[0]}。",
                "约定谁负责接手、谁负责环境整理，避免现场再协商。",
                "每周只复盘一个高摩擦场景，持续微调而不是一次改完。",
            ],
        ),
    ]


def _build_response(family: Family, profile: ChildProfile) -> OnboardingSetupResponse:
    return OnboardingSetupResponse(
        family=FamilyRead.model_validate(family, from_attributes=True),
        profile=ChildProfileRead.model_validate(profile, from_attributes=True),
        snapshot=_build_snapshot(profile),
        support_cards=_build_support_cards(profile),
    )


@router.post("/setup", response_model=OnboardingSetupResponse)
def complete_onboarding(
    payload: OnboardingSetupRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OnboardingSetupResponse:
    source = _merge_payload(payload)
    child_name = str(source.get("child_name") or "").strip()
    family_name = str(source.get("family_name") or "").strip() or (f"{child_name}的家庭" if child_name else "我的家庭")

    family = Family(
        name=family_name,
        timezone=str(source.get("timezone") or "Asia/Shanghai"),
        owner_user_id=user.user_id,
    )
    db.add(family)
    db.flush()

    profile_fields = build_profile_fields(
        source=source,
        onboarding_source="sample" if payload.use_sample else "manual",
    )
    profile = ChildProfile(family_id=family.family_id, **profile_fields)
    db.add(profile)
    db.commit()
    db.refresh(family)
    db.refresh(profile)

    return _build_response(family, profile)


@router.get("/family/{family_id}", response_model=OnboardingSetupResponse)
def get_onboarding_family(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OnboardingSetupResponse:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    profile = db.scalar(select(ChildProfile).where(ChildProfile.family_id == family_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    return _build_response(family, profile)
