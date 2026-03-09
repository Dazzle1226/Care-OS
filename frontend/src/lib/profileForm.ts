import type { OnboardingSetupPayload, OnboardingSummary } from './types';

export const familyMemberOptions = ['妈妈', '爸爸', '奶奶', '爷爷', '外婆', '外公', '兄弟姐妹', '阿姨'];
export const coexistingConditionOptions = ['ADHD', '焦虑', '睡眠问题', '感统失调', '语言发育迟缓', '情绪障碍'];
export const interestOptions = ['积木', '数字', '交通工具', '动物', '音乐', '画画', '拼图', '水'];
export const likeOptions = ['提前预告', '固定流程', '安静角落', '视觉提示', '一对一陪伴', '独处时间'];
export const dislikeOptions = ['突然催促', '陌生人靠近', '排队等待', '大声说话', '拥挤环境', '身体接触'];
export const triggerOptions = ['过渡', '等待', '噪音', '陌生环境', '行程变动', '多人围观', '作业', '外出'];
export const sensoryOptions = ['声音敏感', '光敏', '触感敏感', '气味敏感', '拥挤敏感', '温度敏感'];
export const soothingOptions = ['提前预告', '视觉倒计时', '安静角落', '给两个选择', '耳罩', '深压抱枕'];
export const sleepChallengeOptions = ['入睡慢', '夜醒', '做噩梦', '早醒', '拒绝睡觉', '起床困难'];
export const foodPreferenceOptions = ['偏爱软糯食物', '拒绝混合口感', '挑食', '偏爱固定品牌', '需要分开摆放'];
export const allergyOptions = ['花生过敏', '牛奶过敏', '鸡蛋过敏', '粉尘敏感', '季节性过敏'];
export const medicalNeedOptions = ['需随身带药', '需记录排便', '需观察皮肤过敏', '需规律喝水', '外出备急救卡'];
export const behaviorPatternOptions = ['反复确认', '遇到变化会僵住', '喜欢重复某个动作', '会躲到角落', '需要反复安抚'];
export const behaviorRiskOptions = ['哭闹', '情绪失控', '攻击他人', '摔东西', '自伤', '逃跑'];
export const emotionPatternOptions = ['焦虑', '愤怒', '恐惧', '社交回避', '低落', '烦躁'];
export const learningNeedOptions = ['视觉提示', '两步以内指令', '口语示范', '社交故事', '更多等待时间', '分段任务'];
export const schoolTypeOptions = [
  { value: 'mainstream', label: '普通学校 / 融合环境' },
  { value: 'special', label: '特教学校 / 资源班' },
  { value: 'home', label: '居家教育 / 灵活学习' },
  { value: 'other', label: '其他' }
] as const;
export const socialTrainingOptions = ['社交小组', '言语训练', 'OT / 感统', 'ABA / 行为训练', '心理支持', '同伴陪练'];
export const frictionScenarioOptions = [
  { value: 'transition', label: '过渡' },
  { value: 'bedtime', label: '睡前' },
  { value: 'homework', label: '学习任务' },
  { value: 'outing', label: '外出 / 社交' }
] as const;
export const parentScheduleOptions = ['工作日白天上班', '晚上主要陪伴', '周末全天陪伴', '需要频繁接送', '轮班'];
export const parentStressorOptions = ['工作压力', '照护任务', '睡眠不足', '缺乏社交支持', '经济压力', '夫妻分工不均'];
export const parentSupportActionOptions = ['家长支持群', '行为治疗陪训', '周末有人接手', '固定喘息时间', '咨询 / 心理支持'];
export const parentEmotionalSupportOptions = ['伴侣倾听', '朋友聊天', '家庭支持', '治疗师支持', '线上社群'];
export const supporterOptions = ['配偶', '父母', '祖父母', '亲戚', '朋友', '老师', '治疗师', '家政服务'];

function contextList(summary: OnboardingSummary | null | undefined, key: string) {
  const raw = summary?.profile.school_context?.[key];
  return Array.isArray(raw) ? raw.filter((item): item is string => typeof item === 'string') : [];
}

function contextString(summary: OnboardingSummary | null | undefined, key: string) {
  const raw = summary?.profile.school_context?.[key];
  return typeof raw === 'string' ? raw : '';
}

export function dedupeOptions(values: string[]) {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
}

export function mergeOptions(base: string[], current: string[] | undefined) {
  return dedupeOptions([...(base ?? []), ...(current ?? [])]);
}

export function familyNamePreview(childName?: string, familyName?: string) {
  if (familyName?.trim()) return familyName.trim();
  return childName?.trim() ? `${childName.trim()}的家庭` : '我的家庭';
}

export function createEmptyProfileForm(): OnboardingSetupPayload {
  return {
    timezone: 'Asia/Shanghai',
    child_age: 6,
    communication_level: 'short_sentence',
    child_name: '',
    diagnosis_notes: '',
    taboo_behaviors: '',
    school_notes: ''
  };
}

export function buildProfileFormFromSummary(summary: OnboardingSummary | null): OnboardingSetupPayload {
  if (!summary) return createEmptyProfileForm();
  const context = summary.profile.school_context;

  return {
    family_name: summary.family.name,
    timezone: summary.family.timezone,
    child_name: typeof context.child_name === 'string' ? context.child_name : '',
    child_age: typeof context.child_age === 'number' ? context.child_age : 6,
    child_gender: (context.child_gender as OnboardingSetupPayload['child_gender']) ?? undefined,
    primary_caregiver: (context.primary_caregiver as OnboardingSetupPayload['primary_caregiver']) ?? undefined,
    diagnosis_status: (context.diagnosis_status as OnboardingSetupPayload['diagnosis_status']) ?? undefined,
    diagnosis_notes: contextString(summary, 'diagnosis_notes'),
    communication_level: (summary.profile.language_level as OnboardingSetupPayload['communication_level']) ?? 'short_sentence',
    coexisting_conditions: contextList(summary, 'coexisting_conditions'),
    family_members: contextList(summary, 'family_members'),
    interests: contextList(summary, 'interests'),
    likes: contextList(summary, 'likes'),
    dislikes: contextList(summary, 'dislikes'),
    triggers: summary.profile.triggers,
    sensory_flags: summary.profile.sensory_flags,
    soothing_methods: summary.profile.soothing_methods,
    taboo_behaviors: contextString(summary, 'taboo_behaviors'),
    sleep_challenges: contextList(summary, 'sleep_challenges'),
    food_preferences: contextList(summary, 'food_preferences'),
    allergies: contextList(summary, 'allergies'),
    medical_needs: contextList(summary, 'medical_needs'),
    medications: contextList(summary, 'medications'),
    health_conditions: contextList(summary, 'health_conditions'),
    behavior_patterns: contextList(summary, 'behavior_patterns'),
    behavior_risks: contextList(summary, 'behavior_risks'),
    emotion_patterns: contextList(summary, 'emotion_patterns'),
    learning_needs: contextList(summary, 'learning_needs'),
    school_type: (context.school_type as OnboardingSetupPayload['school_type']) ?? undefined,
    social_training: contextList(summary, 'social_training'),
    school_notes: contextString(summary, 'school_notes'),
    high_friction_scenarios: summary.profile.high_friction_scenarios,
    parent_schedule: contextList(summary, 'parent_schedule'),
    parent_stressors: contextList(summary, 'parent_stressors'),
    parent_support_actions: contextList(summary, 'parent_support_actions'),
    parent_emotional_supports: contextList(summary, 'parent_emotional_supports'),
    available_supporters: contextList(summary, 'available_supporters')
  };
}
