import { useEffect, useMemo, useRef, useState } from 'react';

import { TagSelector } from './TagSelector';
import {
  ageBandOptions,
  allergyOptions,
  coexistingConditionOptions,
  coreDifficultyOptions,
  familyMemberOptions,
  familyNamePreview,
  foodPreferenceOptions,
  frictionScenarioOptions,
  interestOptions,
  likeOptions,
  dislikeOptions,
  medicalNeedOptions,
  parentEmotionalSupportOptions,
  parentScheduleOptions,
  parentStressorOptions,
  parentSupportActionOptions,
  schoolTypeOptions,
  sensoryOptions,
  sleepChallengeOptions,
  socialTrainingOptions,
  soothingOptions,
  splitDelimitedText,
  supporterAvailabilityOptions,
  supporterIndependentCareOptions,
  supporterOptions,
  tabooBehaviorOptions,
  triggerOptions
} from '../lib/profileForm';
import type { OnboardingSetupPayload } from '../lib/types';

interface Props {
  form: OnboardingSetupPayload;
  onChange: (patch: Partial<OnboardingSetupPayload>) => void;
}

type StepTone = 'required' | 'recommended' | 'optional';

interface StepConfig {
  id: string;
  eyebrow: string;
  title: string;
  calloutTitle?: string;
  tone: StepTone;
  description: string;
}

const steps: StepConfig[] = [
  {
    id: 'required',
    eyebrow: '必填资料',
    title: '第一次建档先填这些',
    tone: 'required',
    description: '这部分会直接影响建议话术、优先场景和安全底线。首次建档先完成这里即可。'
  },
  {
    id: 'recommended',
    eyebrow: '继续补充',
    title: '这些信息可以接着填写',
    calloutTitle: '以下为选填信息',
    tone: 'recommended',
    description: '如果现在还有时间，可以继续补；不填也不会影响先完成这次建档。'
  },
  {
    id: 'optional',
    eyebrow: '稍后补充',
    title: '这些资料可以之后再完善',
    calloutTitle: '以下为选填信息',
    tone: 'optional',
    description: '学校、诊断、治疗、过敏和危机联系人等都放这里，不会挡住首次建档。'
  }
];

function StepBadge({ tone }: { tone: StepTone }) {
  const label = tone === 'required' ? '必填' : tone === 'recommended' ? '建议填写' : '稍后补充';
  return <span className={`step-badge ${tone}`}>{label}</span>;
}

function FieldLabel({ text, tone }: { text: string; tone: StepTone }) {
  return (
    <span className="field-label">
      <span className="label">{text}</span>
      <StepBadge tone={tone} />
    </span>
  );
}

function tabooValues(value: string | undefined) {
  return splitDelimitedText(value);
}

function joinTabooValues(values: string[]) {
  return values.join('；');
}

function toneLabel(tone: StepTone) {
  if (tone === 'required') return '先完成必要信息';
  if (tone === 'recommended') return '还有时间就继续补充';
  return '都可留到后面再补';
}

export function ProfileForm({ form, onChange }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const stepTopRef = useRef<HTMLDivElement | null>(null);

  const update = <K extends keyof OnboardingSetupPayload>(key: K, value: OnboardingSetupPayload[K]) => {
    onChange({ [key]: value });
  };

  const current = steps[currentStep];
  const previous = currentStep > 0 ? steps[currentStep - 1] : null;
  const next = currentStep < steps.length - 1 ? steps[currentStep + 1] : null;
  const headingTitle = current.tone === 'required' ? current.title : null;
  const calloutTitle = current.calloutTitle ?? current.title;

  const selectedAgeBand = useMemo(() => {
    const age = form.child_age ?? 6;
    if (age <= 3) return 2;
    if (age <= 6) return 5;
    if (age <= 9) return 8;
    return 11;
  }, [form.child_age]);

  const tabooSelected = useMemo(() => tabooValues(form.taboo_behaviors), [form.taboo_behaviors]);

  useEffect(() => {
    const topNode = stepTopRef.current;
    if (!topNode) return;
    const modalCard = topNode.closest('.modal-card');
    if (modalCard instanceof HTMLElement) {
      modalCard.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    topNode.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [currentStep]);

  return (
    <div className="profile-form-stack">
      <section className="onboarding-section form-stage">
        <div ref={stepTopRef} />
        <div className="step-progress">
          <span className="step-progress-count">
            步骤 {currentStep + 1} / {steps.length}
          </span>
          <span className="step-progress-copy">{toneLabel(current.tone)}</span>
        </div>

        <div className="step-heading">
          <div>
            <p className="eyebrow">{current.eyebrow}</p>
            {headingTitle ? <h3>{headingTitle}</h3> : null}
          </div>
          <StepBadge tone={current.tone} />
        </div>

        <div className={`step-callout ${current.tone}`}>
          <strong>{calloutTitle}</strong>
          <span>{current.description}</span>
        </div>

        {current.id === 'required' ? (
          <>
            <div className="grid two">
              <label>
                <FieldLabel text="孩子称呼 / 昵称" tone="required" />
                <input
                  className="input"
                  value={form.child_name ?? ''}
                  onChange={(e) => update('child_name', e.target.value)}
                  placeholder="例如：小雨"
                />
              </label>
              <div className="option-group">
                <FieldLabel text="年龄段" tone="required" />
                <div className="pill-grid">
                  {ageBandOptions.map((option) => (
                    <button
                      key={option.label}
                      type="button"
                      className={`pill-toggle ${selectedAgeBand === option.value ? 'active' : ''}`}
                      onClick={() => update('child_age', option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <label>
                <FieldLabel text="主要沟通方式" tone="required" />
                <select
                  className="input"
                  value={form.communication_level ?? 'short_sentence'}
                  onChange={(e) =>
                    update('communication_level', e.target.value as OnboardingSetupPayload['communication_level'])
                  }
                >
                  <option value="none">无语言</option>
                  <option value="single_word">单词 / 短语</option>
                  <option value="short_sentence">简单句子</option>
                  <option value="fluent">流利表达</option>
                </select>
              </label>
              <label>
                <FieldLabel text="主要照护者" tone="required" />
                <select
                  className="input"
                  value={form.primary_caregiver ?? ''}
                  onChange={(e) =>
                    update('primary_caregiver', (e.target.value || undefined) as OnboardingSetupPayload['primary_caregiver'])
                  }
                >
                  <option value="">请选择</option>
                  <option value="parents">妈妈 / 爸爸</option>
                  <option value="grandparents">祖父母</option>
                  <option value="relative">其他亲属</option>
                  <option value="other">其他</option>
                </select>
              </label>
            </div>

            <TagSelector
              label="孩子的核心困难（必填）"
              helper="请选择最影响日常生活的几项，系统会据此决定首页优先支持什么。"
              values={form.core_difficulties ?? []}
              options={coreDifficultyOptions}
              onChange={(nextValues) => update('core_difficulties', nextValues)}
              customPlaceholder="补充核心困难"
              variant="pill"
            />

            <TagSelector
              label="常见触发器（必填）"
              helper="高摩擦时刻最核心的数据之一，拿不准就先勾最常见的。"
              values={form.triggers ?? []}
              options={triggerOptions}
              onChange={(nextValues) => update('triggers', nextValues)}
              customPlaceholder="补充触发器"
            />

            <TagSelector
              label="有效安抚方式（必填）"
              helper="系统在高摩擦页面最先参考这组数据。"
              values={form.soothing_methods ?? []}
              options={soothingOptions}
              onChange={(nextValues) => update('soothing_methods', nextValues)}
              customPlaceholder="补充安抚方式"
            />

            <TagSelector
              label="明确禁忌（必填）"
              helper="这是安全底线。建议先勾现阶段最确定不能做的事。"
              values={tabooSelected}
              options={tabooBehaviorOptions}
              onChange={(nextValues) => update('taboo_behaviors', joinTabooValues(nextValues))}
              customPlaceholder="补充明确禁忌"
              variant="pill"
            />

            <div className="grid two">
              <TagSelector
                label="可用支持者（必填）"
                helper="至少填能临时接手的人。"
                values={form.available_supporters ?? []}
                options={supporterOptions}
                onChange={(nextValues) => update('available_supporters', nextValues)}
                customPlaceholder="补充支持者"
                variant="pill"
              />
              <TagSelector
                label="一般什么时候能帮忙（必填）"
                values={form.supporter_availability ?? []}
                options={supporterAvailabilityOptions}
                onChange={(nextValues) => update('supporter_availability', nextValues)}
                customPlaceholder="补充可用时间"
                variant="pill"
              />
            </div>

            <label>
              <FieldLabel text="是否能单独带孩子一会儿" tone="required" />
              <select
                className="input"
                value={form.supporter_independent_care ?? 'unknown'}
                onChange={(e) =>
                  update(
                    'supporter_independent_care',
                    e.target.value as OnboardingSetupPayload['supporter_independent_care']
                  )
                }
              >
                {supporterIndependentCareOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        ) : null}

        {current.id === 'recommended' ? (
          <>
            <TagSelector
              label="感官画像（建议填写）"
              helper="会明显影响外出、睡前、排队、吃饭等建议。"
              values={form.sensory_flags ?? []}
              options={sensoryOptions}
              onChange={(nextValues) => update('sensory_flags', nextValues)}
              customPlaceholder="补充感官特点"
            />

            <TagSelector
              label="高频高摩擦场景（建议填写）"
              helper="建议勾最想先解决的 3 个场景。"
              values={form.high_friction_scenarios ?? []}
              options={frictionScenarioOptions.map((item) => ({ value: item.value, label: item.label }))}
              onChange={(nextValues) => update('high_friction_scenarios', nextValues)}
              customPlaceholder="补充场景键，如 transition"
              variant="pill"
            />

            <TagSelector
              label="家长当前最大压力源（建议填写）"
              values={form.parent_stressors ?? []}
              options={[
                ...parentStressorOptions,
                '孩子情绪波动大',
                '家校沟通困难',
                '缺少帮手',
                '工作和照护冲突',
                '不知道怎么做才对',
                '家人意见不一致'
              ]}
              onChange={(nextValues) => update('parent_stressors', nextValues)}
              customPlaceholder="补充压力源"
              variant="pill"
            />

            <div className="grid two">
              <TagSelector
                label="孩子喜欢什么活动 / 物品（建议填写）"
                values={form.interests ?? []}
                options={interestOptions}
                onChange={(nextValues) => update('interests', nextValues)}
                customPlaceholder="补充兴趣或活动"
                variant="pill"
              />
              <TagSelector
                label="哪些东西最能转移注意力 / 作为奖励（建议填写）"
                values={form.likes ?? []}
                options={likeOptions}
                onChange={(nextValues) => update('likes', nextValues)}
                customPlaceholder="补充偏好或奖励"
                variant="pill"
              />
            </div>
          </>
        ) : null}

        {current.id === 'optional' ? (
          <>
            <div className="grid two">
              <label>
                <FieldLabel text="家庭名称" tone="optional" />
                <input
                  className="input"
                  value={form.family_name ?? familyNamePreview(form.child_name)}
                  onChange={(e) => update('family_name', e.target.value)}
                  placeholder={familyNamePreview(form.child_name)}
                />
              </label>
              <label>
                <FieldLabel text="孩子性别" tone="optional" />
                <select
                  className="input"
                  value={form.child_gender ?? ''}
                  onChange={(e) => update('child_gender', (e.target.value || undefined) as OnboardingSetupPayload['child_gender'])}
                >
                  <option value="">暂不填写</option>
                  <option value="male">男</option>
                  <option value="female">女</option>
                  <option value="other">其他</option>
                </select>
              </label>
              <label>
                <FieldLabel text="诊断情况" tone="optional" />
                <select
                  className="input"
                  value={form.diagnosis_status ?? ''}
                  onChange={(e) =>
                    update('diagnosis_status', (e.target.value || undefined) as OnboardingSetupPayload['diagnosis_status'])
                  }
                >
                  <option value="">暂不填写</option>
                  <option value="asd">自闭症谱系障碍（ASD）</option>
                  <option value="none">没有诊断</option>
                  <option value="under_assessment">评估中</option>
                  <option value="other">其他</option>
                </select>
              </label>
              <label>
                <FieldLabel text="教育环境" tone="optional" />
                <select
                  className="input"
                  value={form.school_type ?? ''}
                  onChange={(e) => update('school_type', (e.target.value || undefined) as OnboardingSetupPayload['school_type'])}
                >
                  <option value="">暂不填写</option>
                  {schoolTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="full-span">
                <FieldLabel text="诊断补充 / 诊断时间" tone="optional" />
                <textarea
                  className="input"
                  rows={3}
                  value={form.diagnosis_notes ?? ''}
                  onChange={(e) => update('diagnosis_notes', e.target.value)}
                  placeholder="例如：2024 年评估；目前伴焦虑，近期重点处理睡前困难。"
                />
              </label>
              <label className="full-span">
                <FieldLabel text="历史上最严重的高摩擦事件" tone="optional" />
                <textarea
                  className="input"
                  rows={3}
                  value={form.major_incident_notes ?? ''}
                  onChange={(e) => update('major_incident_notes', e.target.value)}
                  placeholder="例如：在商场排队时升级到躺地哭闹，最后由爸爸抱离。"
                />
              </label>
              <label className="full-span">
                <FieldLabel text="学校 / 幼儿园情况" tone="optional" />
                <textarea
                  className="input"
                  rows={4}
                  value={form.school_notes ?? ''}
                  onChange={(e) => update('school_notes', e.target.value)}
                  placeholder="例如：普通小学融合班；起床出门和午休后回班最容易卡住。"
                />
              </label>
            </div>

            <div className="grid two">
              <TagSelector
                label="伴随问题（选填）"
                values={form.coexisting_conditions ?? []}
                options={coexistingConditionOptions}
                onChange={(nextValues) => update('coexisting_conditions', nextValues)}
                customPlaceholder="补充伴随问题"
                variant="pill"
              />
              <TagSelector
                label="家庭成员（选填）"
                values={form.family_members ?? []}
                options={familyMemberOptions}
                onChange={(nextValues) => update('family_members', nextValues)}
                customPlaceholder="补充家庭成员"
                variant="pill"
              />
              <TagSelector
                label="饮食 / 挑食情况（选填）"
                values={form.food_preferences ?? []}
                options={foodPreferenceOptions}
                onChange={(nextValues) => update('food_preferences', nextValues)}
                customPlaceholder="补充饮食情况"
              />
              <TagSelector
                label="过敏情况（选填）"
                values={form.allergies ?? []}
                options={allergyOptions}
                onChange={(nextValues) => update('allergies', nextValues)}
                customPlaceholder="补充过敏信息"
                variant="pill"
              />
              <TagSelector
                label="治疗 / 机构参与情况（选填）"
                values={form.social_training ?? []}
                options={socialTrainingOptions}
                onChange={(nextValues) => update('social_training', nextValues)}
                customPlaceholder="补充治疗或机构支持"
                variant="pill"
              />
              <TagSelector
                label="医疗需求（选填）"
                values={form.medical_needs ?? []}
                options={medicalNeedOptions}
                onChange={(nextValues) => update('medical_needs', nextValues)}
                customPlaceholder="补充医疗需求"
                variant="pill"
              />
              <TagSelector
                label="睡眠情况（选填）"
                values={form.sleep_challenges ?? []}
                options={sleepChallengeOptions}
                onChange={(nextValues) => update('sleep_challenges', nextValues)}
                customPlaceholder="补充睡眠情况"
              />
              <TagSelector
                label="危机联系人（选填）"
                values={form.emergency_contacts ?? []}
                options={[]}
                onChange={(nextValues) => update('emergency_contacts', nextValues)}
                customPlaceholder="例如：外婆 138xxxx / 王老师"
                variant="pill"
              />
            </div>

            <div className="grid two">
              <TagSelector
                label="不喜欢 / 尽量避免（选填）"
                values={form.dislikes ?? []}
                options={dislikeOptions}
                onChange={(nextValues) => update('dislikes', nextValues)}
                customPlaceholder="补充不喜欢的内容"
                variant="pill"
              />
              <TagSelector
                label="家长时间安排（选填）"
                values={form.parent_schedule ?? []}
                options={parentScheduleOptions}
                onChange={(nextValues) => update('parent_schedule', nextValues)}
                customPlaceholder="补充家长时间安排"
                variant="pill"
              />
              <TagSelector
                label="已参与的支持性活动（选填）"
                values={form.parent_support_actions ?? []}
                options={parentSupportActionOptions}
                onChange={(nextValues) => update('parent_support_actions', nextValues)}
                customPlaceholder="补充支持性活动"
                variant="pill"
              />
              <TagSelector
                label="家长情感支持来源（选填）"
                values={form.parent_emotional_supports ?? []}
                options={parentEmotionalSupportOptions}
                onChange={(nextValues) => update('parent_emotional_supports', nextValues)}
                customPlaceholder="补充情感支持来源"
                variant="pill"
              />
            </div>
          </>
        ) : null}

        <div className="step-actions">
          {previous ? (
            <button className="btn secondary" type="button" onClick={() => setCurrentStep((value) => value - 1)}>
              上一步
            </button>
          ) : (
            <span className="step-actions-spacer" />
          )}
          {next ? (
            <button className="btn" type="button" onClick={() => setCurrentStep((value) => value + 1)}>
              继续
            </button>
          ) : (
            <span className="muted step-finish-hint">已经到“稍后补充”，可直接保存当前建档内容。</span>
          )}
        </div>
      </section>
    </div>
  );
}
