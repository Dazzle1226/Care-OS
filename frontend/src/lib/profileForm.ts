import type { OnboardingSetupPayload, OnboardingSummary } from './types';

export const ageBandOptions = [
  { label: '0-3 岁', value: 2 },
  { label: '4-6 岁', value: 5 },
  { label: '7-9 岁', value: 8 },
  { label: '10-12 岁', value: 11 }
] as const;
export const coreDifficultyOptions = [
  '过渡困难',
  '情绪崩溃/哭闹',
  '感官敏感',
  '作业/任务启动困难',
  '睡前困难',
  '吃饭/挑食',
  '外出困难',
  '社交冲突',
  '攻击/打人/扔东西'
];
export const familyMemberOptions = ['妈妈', '爸爸', '奶奶', '爷爷', '外婆', '外公', '兄弟姐妹', '阿姨'];
export const coexistingConditionOptions = ['ADHD', '焦虑', '睡眠问题', '感统失调', '语言发育迟缓', '情绪障碍'];
export const interestOptions = ['积木', '数字', '交通工具', '动物', '音乐', '画画', '拼图', '水'];
export const likeOptions = ['喜欢的物品', '喜欢的活动', '固定流程', '安静角落', '提前预告', '一对一陪伴', '奖励贴纸', '独处时间'];
export const dislikeOptions = ['突然催促', '陌生人靠近', '排队等待', '大声说话', '拥挤环境', '身体接触'];
export const triggerOptions = [
  '突然变化',
  '被打断喜欢的活动',
  '噪音',
  '人多',
  '等待',
  '不会表达需求',
  '身体不舒服/饿/困',
  '被催促',
  '陌生环境',
  '过渡',
  '行程变动',
  '多人围观',
  '作业',
  '外出'
];
export const sensoryOptions = ['对声音敏感', '对强光敏感', '对衣服标签/触感敏感', '对气味敏感', '对拥挤空间敏感', '对食物口感敏感'];
export const soothingOptions = [
  '安静独处',
  '拥抱/深压（适用时）',
  '喜欢的物品',
  '音乐',
  '视觉提示',
  '倒计时/计时器',
  '选择题而不是命令',
  '喝水/吃点东西',
  '身体活动',
  '提前预告',
  '安静角落'
];
export const tabooBehaviorOptions = ['不要强拉', '不要大声训斥', '不要多人围着说话', '不要突然碰触', '不要连续追问', '不要直接抢走物品'];
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
export const supporterAvailabilityOptions = ['工作日白天', '工作日晚上', '周末', '不固定'];
export const supporterIndependentCareOptions = [
  { value: 'can_alone', label: '可以单独带一会儿' },
  { value: 'needs_handoff', label: '需要先交接再接手' },
  { value: 'cannot_alone', label: '暂时不能单独带' },
  { value: 'unknown', label: '还不确定' }
] as const;

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

export function splitDelimitedText(value: string | undefined) {
  if (!value?.trim()) return [];
  return dedupeOptions(value.replace(/；/g, ',').replace(/，/g, ',').split(','));
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
    school_notes: '',
    major_incident_notes: '',
    supporter_independent_care: 'unknown'
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
    core_difficulties: contextList(summary, 'core_difficulties'),
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
    available_supporters: contextList(summary, 'available_supporters'),
    supporter_availability: contextList(summary, 'supporter_availability'),
    supporter_independent_care:
      (context.supporter_independent_care as OnboardingSetupPayload['supporter_independent_care']) ?? 'unknown',
    major_incident_notes: contextString(summary, 'major_incident_notes'),
    emergency_contacts: contextList(summary, 'emergency_contacts')
  };
}
