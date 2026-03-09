import { useEffect, useState } from 'react';

import { TagSelector } from './TagSelector';

type SensoryLevel = 'none' | 'light' | 'medium' | 'heavy';
type SupportLevel = 'none' | 'one' | 'two_plus';
type MoodState = 'stable' | 'sensitive' | 'anxious' | 'low_energy' | 'irritable';
type CheckinFormValues = Omit<CheckinFormPayload, 'date'>;

export interface CheckinFormPayload {
  date: string;
  child_sleep_hours: number;
  child_sleep_quality: number;
  sleep_issues: string[];
  sensory_overload_level: SensoryLevel;
  meltdown_count: number;
  child_mood_state: MoodState;
  physical_discomforts: string[];
  aggressive_behaviors: string[];
  negative_emotions: string[];
  transition_difficulty: number;
  caregiver_stress: number;
  support_available: SupportLevel;
  caregiver_sleep_quality: number;
  today_activities: string[];
  today_learning_tasks: string[];
}

interface Props {
  open: boolean;
  date: string;
  submitting: boolean;
  initialValues?: Partial<CheckinFormValues>;
  onClose: () => void;
  onSubmit: (payload: CheckinFormPayload) => Promise<void>;
}

const sleepIssueOptions = ['做噩梦', '夜醒', '入睡慢', '早醒', '起床困难'];
const physicalDiscomfortOptions = ['无明显不适', '肠胃不适', '头痛 / 感冒', '过敏不适', '食欲差'];
const aggressiveBehaviorOptions = ['无明显过激行为', '哭闹', '情绪失控', '攻击他人', '摔东西', '自伤'];
const negativeEmotionOptions = ['无明显负面情绪', '焦虑', '恐惧', '愤怒', '社交回避', '低落'];
const activityOptions = ['学校活动', '医生预约', '社交活动', '外出安排', '家庭聚会', '需要长途通勤'];
const learningTaskOptions = ['学校作业', '行为训练', '社交练习', '语言练习', 'OT / 感统', '家庭规则训练'];

const defaultForm: CheckinFormValues = {
  child_sleep_hours: 8,
  child_sleep_quality: 6,
  sleep_issues: [],
  sensory_overload_level: 'light',
  meltdown_count: 0,
  child_mood_state: 'stable',
  physical_discomforts: [],
  aggressive_behaviors: [],
  negative_emotions: [],
  transition_difficulty: 4,
  caregiver_stress: 4,
  support_available: 'one',
  caregiver_sleep_quality: 6,
  today_activities: [],
  today_learning_tasks: []
};

const moodOptions = [
  { value: 'stable', label: '稳定', hint: '整体平稳，能正常进入日常流程。' },
  { value: 'sensitive', label: '敏感', hint: '容易被声音、变化或提醒影响。' },
  { value: 'anxious', label: '焦虑', hint: '表现出明显紧张、担心或回避。' },
  { value: 'low_energy', label: '低能量', hint: '疲倦、慢热、容易拖住。' },
  { value: 'irritable', label: '烦躁', hint: '容易顶嘴、拒绝或被小事点燃。' }
] as const;

export function CheckinCard({ open, date, submitting, initialValues, onClose, onSubmit }: Props) {
  const [step, setStep] = useState<'intro' | 'form'>('intro');
  const [form, setForm] = useState<CheckinFormValues>(defaultForm);

  useEffect(() => {
    if (!open) return;
    setStep('intro');
    setForm({
      ...defaultForm,
      ...initialValues
    });
  }, [open, date, initialValues]);

  if (!open) return null;

  return (
    <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="daily-checkin-title">
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-card">
        <button className="icon-btn" type="button" onClick={onClose} aria-label="关闭签到弹窗">
          ×
        </button>

        {step === 'intro' ? (
          <div className="checkin-intro">
            <p className="eyebrow">每日签到</p>
            <h3 id="daily-checkin-title">你好，今天如何？</h3>
            <p className="intro-copy">补一下孩子和家长今天的状态，系统会根据历史记录和今天的安排生成更贴近现实的行动卡片。</p>
            <div className="intro-pills">
              <span>滑条 + 单选 + 多选</span>
              <span>可补充自定义选项</span>
              <span>完成后即时生成今日对策</span>
            </div>
            <button className="btn" type="button" onClick={() => setStep('form')}>
              开始签到
            </button>
          </div>
        ) : (
          <div className="checkin-form">
            <div className="checkin-header">
              <div>
                <p className="eyebrow">今日状态</p>
                <h3 id="daily-checkin-title">把今天的风险点先标出来</h3>
              </div>
              <span className="date-pill">{date}</span>
            </div>

            <div className="question-group">
              <h4>孩子健康状态</h4>
              <div className="grid two">
                <label className="range-field">
                  <div className="field-head">
                    <span>昨晚睡眠时长</span>
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
                    <span>昨晚睡眠质量</span>
                    <strong>{form.child_sleep_quality} / 10</strong>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    step="1"
                    value={form.child_sleep_quality}
                    onChange={(e) => setForm((prev) => ({ ...prev, child_sleep_quality: Number(e.target.value) }))}
                  />
                </label>
              </div>
              <TagSelector
                label="昨晚有无困扰"
                values={form.sleep_issues}
                options={sleepIssueOptions}
                onChange={(next) => setForm((prev) => ({ ...prev, sleep_issues: next }))}
                customPlaceholder="补充睡眠困扰"
                variant="pill"
              />
              <div className="option-group">
                <span className="label">孩子今天的精神状态</span>
                <div className="option-grid mood-grid">
                  {moodOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`option-card ${form.child_mood_state === option.value ? 'active' : ''}`}
                      onClick={() => setForm((prev) => ({ ...prev, child_mood_state: option.value }))}
                    >
                      <strong>{option.label}</strong>
                      <span>{option.hint}</span>
                    </button>
                  ))}
                </div>
              </div>
              <TagSelector
                label="是否有身体不适"
                values={form.physical_discomforts}
                options={physicalDiscomfortOptions}
                onChange={(next) => setForm((prev) => ({ ...prev, physical_discomforts: next }))}
                customPlaceholder="补充身体不适"
                variant="pill"
              />
            </div>

            <div className="question-group">
              <h4>孩子行为表现</h4>
              <label>
                <span className="label">今天感官过载</span>
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
                <legend className="label">冲突 / 崩溃次数</legend>
                {[
                  { label: '0', value: 0 },
                  { label: '1', value: 1 },
                  { label: '2', value: 2 },
                  { label: '3+', value: 3 }
                ].map((item) => (
                  <label key={item.label} className={`option-chip ${form.meltdown_count === item.value ? 'active' : ''}`}>
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
                  <span>过渡难度</span>
                  <strong>{form.transition_difficulty} / 10</strong>
                </div>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="1"
                  value={form.transition_difficulty}
                  onChange={(e) => setForm((prev) => ({ ...prev, transition_difficulty: Number(e.target.value) }))}
                />
              </label>
              <TagSelector
                label="昨天是否出现过激行为"
                values={form.aggressive_behaviors}
                options={aggressiveBehaviorOptions}
                onChange={(next) => setForm((prev) => ({ ...prev, aggressive_behaviors: next }))}
                customPlaceholder="补充行为表现"
                variant="pill"
              />
              <TagSelector
                label="今天是否有强烈负面情绪"
                values={form.negative_emotions}
                options={negativeEmotionOptions}
                onChange={(next) => setForm((prev) => ({ ...prev, negative_emotions: next }))}
                customPlaceholder="补充情绪表现"
                variant="pill"
              />
            </div>

            <div className="question-group">
              <h4>家长状态与今日计划</h4>
              <div className="grid two">
                <label className="range-field">
                  <div className="field-head">
                    <span>今日压力</span>
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
                    <span>家长睡眠质量</span>
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
              <fieldset className="segmented">
                <legend className="label">今日可用支持</legend>
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
              <TagSelector
                label="今天有哪些特别安排"
                values={form.today_activities}
                options={activityOptions}
                onChange={(next) => setForm((prev) => ({ ...prev, today_activities: next }))}
                customPlaceholder="补充今日活动安排"
                variant="pill"
              />
              <TagSelector
                label="今天是否有学习 / 训练任务"
                values={form.today_learning_tasks}
                options={learningTaskOptions}
                onChange={(next) => setForm((prev) => ({ ...prev, today_learning_tasks: next }))}
                customPlaceholder="补充学习或训练任务"
                variant="pill"
              />
            </div>

            <div className="checkin-actions">
              <button className="btn secondary" type="button" onClick={() => setStep('intro')}>
                返回
              </button>
              <button
                className="btn"
                type="button"
                disabled={submitting}
                onClick={() => onSubmit({ date, ...form })}
              >
                {submitting ? '生成中...' : '完成签到'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
