import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import {
  buildCheckinPayload,
  defaultCheckinFormValues,
  type CheckinFormPayload,
  type CheckinFormValues,
  type MoodState,
  type SensoryLevel,
  type SupportLevel
} from '../lib/checkinPayload';
import { getInitialCheckinStep } from '../lib/checkinFlow';
import { TagSelector } from './TagSelector';

interface Props {
  open: boolean;
  date: string;
  submitting: boolean;
  initialValues?: Partial<CheckinFormValues>;
  onClose: () => void;
  onSubmit: (payload: CheckinFormPayload) => Promise<void>;
}

type StepTone = 'required' | 'optional';
type CheckinStep = 'intro' | 'required-info' | 'child-details' | 'caregiver-details';

const sleepIssueOptions = ['做噩梦', '夜醒', '入睡慢', '早醒', '起床困难'];
const physicalDiscomfortOptions = ['无明显不适', '肠胃不适', '头痛 / 感冒', '过敏不适', '食欲差'];
const aggressiveBehaviorOptions = ['无明显过激行为', '哭闹', '情绪失控', '攻击他人', '摔东西', '自伤'];
const negativeEmotionOptions = ['无明显负面情绪', '焦虑', '恐惧', '愤怒', '社交回避', '低落'];
const activityOptions = ['学校活动', '医生预约', '社交活动', '外出安排', '家庭聚会', '需要长途通勤'];
const learningTaskOptions = ['学校作业', '行为训练', '社交练习', '语言练习', 'OT / 感统', '家庭规则训练'];

const moodOptions = [
  { value: 'stable', label: '稳定', hint: '整体平稳，能正常进入日常流程。' },
  { value: 'sensitive', label: '敏感', hint: '容易被声音、变化或提醒影响。' },
  { value: 'anxious', label: '焦虑', hint: '表现出明显紧张、担心或回避。' },
  { value: 'low_energy', label: '低能量', hint: '疲倦、慢热、容易拖住。' },
  { value: 'irritable', label: '烦躁', hint: '容易顶嘴、拒绝或被小事点燃。' }
] as const;

interface StepConfig {
  id: Exclude<CheckinStep, 'intro'>;
  eyebrow: string;
  title: string;
  tone: StepTone;
  description: string;
}

const stepConfigs: StepConfig[] = [
  {
    id: 'required-info',
    eyebrow: '必要信息',
    title: '必要信息填写',
    tone: 'required',
    description: ''
  },
  {
    id: 'child-details',
    eyebrow: '详细情况',
    title: '需要的话再补充孩子细节',
    tone: 'optional',
    description: '睡眠、身体不适、精神状态和情绪表现都改成选填，不会挡住继续。'
  },
  {
    id: 'caregiver-details',
    eyebrow: '家长状态',
    title: '最后按需补充家长负荷',
    tone: 'optional',
    description: '如果时间紧，这一步可以直接跳过；有空再补能帮助系统评估家长承载量。'
  }
];

function StepBadge({ tone }: { tone: StepTone }) {
  return <span className={`step-badge ${tone}`}>{tone === 'required' ? '必填' : '选填'}</span>;
}

function FieldLabel({ text, tone }: { text: string; tone: StepTone }) {
  return (
    <span className="field-label">
      <span className="label">{text}</span>
      <StepBadge tone={tone} />
    </span>
  );
}

export function CheckinCard({ open, date, submitting, initialValues, onClose, onSubmit }: Props) {
  const [step, setStep] = useState<CheckinStep>('intro');
  const [form, setForm] = useState<CheckinFormValues>(defaultCheckinFormValues);
  const modalScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setStep(getInitialCheckinStep(initialValues));
    setForm({
      ...defaultCheckinFormValues,
      ...initialValues
    });
  }, [open, date, initialValues]);

  useEffect(() => {
    if (!open || typeof document === 'undefined') return;

    const { body } = document;
    const previousOverflow = body.style.overflow;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleEscape);

    return () => {
      body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleEscape);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    modalScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [open, step]);

  if (!open) return null;
  if (typeof document === 'undefined') return null;

  const currentIndex = stepConfigs.findIndex((item) => item.id === step);
  const currentStep = currentIndex >= 0 ? stepConfigs[currentIndex] : null;
  const previousStep = currentIndex > 0 ? stepConfigs[currentIndex - 1] : null;
  const nextStep = currentIndex >= 0 && currentIndex < stepConfigs.length - 1 ? stepConfigs[currentIndex + 1] : null;

  return createPortal(
    <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="daily-checkin-title">
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-card modal-card-fixed-close checkin-modal-card">
        <button
          className="icon-btn modal-close-fixed"
          type="button"
          onClick={onClose}
          aria-label="关闭签到弹窗"
        >
          ×
        </button>
        <div ref={modalScrollRef} className="modal-scroll-area">
          {step === 'intro' ? (
            <div className="checkin-intro">
              <p className="eyebrow">每日签到</p>
              <h3 id="daily-checkin-title">你好，今天如何？</h3>
              <div className="intro-pills">
                <span>先填必填，再决定是否补充</span>
                <span>每一步都能继续</span>
                <span>完成后即时生成今日对策</span>
              </div>
              <button className="btn" type="button" onClick={() => setStep('required-info')}>
                开始签到
              </button>
            </div>
          ) : (
            <div className="checkin-form">
              <div className="checkin-header">
                <div>
                  <p className="eyebrow">今日签到</p>
                  <h3 id="daily-checkin-title">按步骤填写今天最必要的信息</h3>
                </div>
                <span className="date-pill">{date}</span>
              </div>

              {currentStep ? (
                <>
                  <div className="step-progress">
                    <span className="step-progress-count">
                      步骤 {currentIndex + 1} / {stepConfigs.length}
                    </span>
                    <span className="step-progress-copy">
                      {currentStep.tone === 'required' ? '先完成必要信息' : '这一步可直接继续'}
                    </span>
                  </div>

                  <div className="step-heading">
                    <div>
                      <p className="eyebrow">{currentStep.eyebrow}</p>
                      <h3>{currentStep.title}</h3>
                    </div>
                    <StepBadge tone={currentStep.tone} />
                  </div>

                  {currentStep.description ? <p className="muted step-description">{currentStep.description}</p> : null}

                  {step === 'required-info' ? (
                    <div className="required-info-layout">
                      <div className="question-group required-info-panel">
                        <h4>核心状态</h4>
                        <label>
                          <FieldLabel text="今天感官过载" tone="required" />
                          <select
                            className="input"
                            value={form.sensory_overload_level}
                            onChange={(e) =>
                              setForm((prev) => ({
                                ...prev,
                                sensory_overload_level: e.target.value as SensoryLevel
                              }))
                            }
                          >
                            <option value="none">无</option>
                            <option value="light">轻微</option>
                            <option value="medium">中等</option>
                            <option value="heavy">严重</option>
                          </select>
                        </label>
                        <fieldset className="segmented">
                          <legend className="field-label">
                            <span className="label">冲突 / 崩溃次数</span>
                            <StepBadge tone="required" />
                          </legend>
                          {[
                            { label: '0', value: 0 },
                            { label: '1', value: 1 },
                            { label: '2', value: 2 },
                            { label: '3+', value: 3 }
                          ].map((item) => (
                            <label
                              key={item.label}
                              className={`option-chip ${form.meltdown_count === item.value ? 'active' : ''}`}
                            >
                              <input
                                type="radio"
                                name="meltdown_count"
                                checked={form.meltdown_count === item.value}
                                onChange={() => setForm((prev) => ({ ...prev, meltdown_count: item.value }))}
                              />
                              <span>{item.label}</span>
                            </label>
                          ))}
                        </fieldset>
                        <label className="range-field">
                          <div className="field-head">
                            <FieldLabel text="过渡难度" tone="required" />
                            <strong>{form.transition_difficulty ?? 4} / 10</strong>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="10"
                            step="1"
                            value={form.transition_difficulty ?? 4}
                            onChange={(e) =>
                              setForm((prev) => ({ ...prev, transition_difficulty: Number(e.target.value) }))
                            }
                          />
                        </label>
                        <fieldset className="segmented">
                          <legend className="field-label">
                            <span className="label">今日可用支持</span>
                            <StepBadge tone="required" />
                          </legend>
                          {[
                            { label: '无', value: 'none' },
                            { label: '有 1 人', value: 'one' },
                            { label: '有 2 人+', value: 'two_plus' }
                          ].map((item) => (
                            <label
                              key={item.value}
                              className={`option-chip ${form.support_available === item.value ? 'active' : ''}`}
                            >
                              <input
                                type="radio"
                                name="support_available"
                                checked={form.support_available === item.value}
                                onChange={() =>
                                  setForm((prev) => ({ ...prev, support_available: item.value as SupportLevel }))
                                }
                              />
                              <span>{item.label}</span>
                            </label>
                          ))}
                        </fieldset>
                      </div>

                      <div className="question-group required-info-panel">
                        <h4>今日安排</h4>
                        <TagSelector
                          label="今天的特别安排（必填）"
                          values={form.today_activities}
                          options={activityOptions}
                          onChange={(next) => setForm((prev) => ({ ...prev, today_activities: next }))}
                          customPlaceholder="补充今日安排"
                          variant="pill"
                        />
                        <TagSelector
                          label="今天的学习 / 训练任务（必填）"
                          values={form.today_learning_tasks}
                          options={learningTaskOptions}
                          onChange={(next) => setForm((prev) => ({ ...prev, today_learning_tasks: next }))}
                          customPlaceholder="补充训练任务"
                          variant="pill"
                        />
                      </div>
                    </div>
                  ) : null}

                {step === 'child-details' ? (
                  <>
                    <div className="question-group">
                      <h4>睡眠与身体状态</h4>
                      <div className="grid two">
                        <label className="range-field">
                          <div className="field-head">
                            <FieldLabel text="昨晚睡眠时长" tone="optional" />
                            <strong>{form.child_sleep_hours} 小时</strong>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="12"
                            step="1"
                            value={form.child_sleep_hours}
                            onChange={(e) => setForm((prev) => ({ ...prev, child_sleep_hours: Number(e.target.value) }))}
                          />
                        </label>
                        <label className="range-field">
                          <div className="field-head">
                            <FieldLabel text="昨晚睡眠质量" tone="optional" />
                            <strong>{form.child_sleep_quality ?? '未填'}</strong>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="10"
                            step="1"
                            value={form.child_sleep_quality ?? 6}
                            onChange={(e) => setForm((prev) => ({ ...prev, child_sleep_quality: Number(e.target.value) }))}
                          />
                        </label>
                      </div>
                      <TagSelector
                        label="昨晚有无困扰（选填）"
                        values={form.sleep_issues}
                        options={sleepIssueOptions}
                        onChange={(next) => setForm((prev) => ({ ...prev, sleep_issues: next }))}
                        customPlaceholder="补充睡眠困扰"
                        variant="pill"
                      />
                      <TagSelector
                        label="是否有身体不适（选填）"
                        values={form.physical_discomforts}
                        options={physicalDiscomfortOptions}
                        onChange={(next) => setForm((prev) => ({ ...prev, physical_discomforts: next }))}
                        customPlaceholder="补充身体不适"
                        variant="pill"
                      />
                    </div>

                    <div className="question-group">
                      <h4>精神状态与情绪表现</h4>
                      <div className="option-group">
                        <span className="field-label">
                          <span className="label">孩子今天的精神状态</span>
                          <StepBadge tone="optional" />
                        </span>
                        <div className="option-grid mood-grid">
                          {moodOptions.map((option) => (
                            <button
                              key={option.value}
                              type="button"
                              className={`option-card ${form.child_mood_state === option.value ? 'active' : ''}`}
                              onClick={() => setForm((prev) => ({ ...prev, child_mood_state: option.value as MoodState }))}
                            >
                              <strong>{option.label}</strong>
                              <span>{option.hint}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                      <TagSelector
                        label="昨天是否出现过激行为（选填）"
                        values={form.aggressive_behaviors}
                        options={aggressiveBehaviorOptions}
                        onChange={(next) => setForm((prev) => ({ ...prev, aggressive_behaviors: next }))}
                        customPlaceholder="补充行为表现"
                        variant="pill"
                      />
                      <TagSelector
                        label="今天是否有强烈负面情绪（选填）"
                        values={form.negative_emotions}
                        options={negativeEmotionOptions}
                        onChange={(next) => setForm((prev) => ({ ...prev, negative_emotions: next }))}
                        customPlaceholder="补充情绪表现"
                        variant="pill"
                      />
                    </div>
                  </>
                ) : null}

                {step === 'caregiver-details' ? (
                  <div className="question-group">
                    <div className="grid two">
                      <label className="range-field">
                        <div className="field-head">
                          <FieldLabel text="今日压力" tone="optional" />
                          <strong>{form.caregiver_stress} / 10</strong>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="10"
                          step="1"
                          value={form.caregiver_stress}
                          onChange={(e) => setForm((prev) => ({ ...prev, caregiver_stress: Number(e.target.value) }))}
                        />
                      </label>
                      <label className="range-field">
                        <div className="field-head">
                          <FieldLabel text="家长睡眠质量" tone="optional" />
                          <strong>{form.caregiver_sleep_quality} / 10</strong>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="10"
                          step="1"
                          value={form.caregiver_sleep_quality}
                          onChange={(e) => setForm((prev) => ({ ...prev, caregiver_sleep_quality: Number(e.target.value) }))}
                        />
                      </label>
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}

              <div className="checkin-actions">
                {previousStep ? (
                  <button className="btn secondary" type="button" onClick={() => setStep(previousStep.id)}>
                    上一步
                  </button>
                ) : (
                  <button className="btn secondary" type="button" onClick={() => setStep('intro')}>
                    返回
                  </button>
                )}

                {step === 'required-info' ? (
                  <>
                    <button className="btn secondary" type="button" onClick={() => setStep('child-details')}>
                      继续补充可选信息
                    </button>
                    <button
                      className="btn"
                      type="button"
                      disabled={submitting}
                      onClick={() => onSubmit(buildCheckinPayload({ date, ...form }))}
                    >
                      {submitting ? '生成中...' : '完成签到'}
                    </button>
                  </>
                ) : nextStep ? (
                  <button className="btn" type="button" onClick={() => setStep(nextStep.id)}>
                    继续
                  </button>
                ) : (
                  <button
                    className="btn"
                    type="button"
                    disabled={submitting}
                    onClick={() => onSubmit(buildCheckinPayload({ date, ...form }))}
                  >
                    {submitting ? '生成中...' : '完成签到'}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
