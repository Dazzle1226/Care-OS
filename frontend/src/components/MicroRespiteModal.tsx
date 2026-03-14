import { useEffect, useMemo, useRef, useState } from 'react';

import { generateMicroRespite, submitMicroRespiteFeedback } from '../lib/api';
import { sanitizeDisplayText } from '../lib/displayText';
import type {
  CheckinRecord,
  ChildEmotionState,
  MicroRespiteFeedbackResponse,
  MicroRespiteGenerateResponse,
  MicroRespiteOption,
  SignalOutput
} from '../lib/types';
import { SafetyBlockCard } from './SafetyBlockCard';

type SensoryLevel = 'none' | 'light' | 'medium' | 'heavy';
type SupportLevel = 'none' | 'one' | 'two_plus';
type Effectiveness = 'helpful' | 'somewhat' | 'not_helpful';

interface FormValues {
  caregiver_stress: number;
  caregiver_sleep_quality: number;
  support_available: SupportLevel;
  child_emotional_state: ChildEmotionState;
  sensory_overload_level: SensoryLevel;
  transition_difficulty: number;
  meltdown_count: number;
  notes: string;
}

interface Props {
  open: boolean;
  token: string;
  familyId: number | null;
  initialCheckin?: CheckinRecord;
  risk?: SignalOutput;
  onClose: () => void;
}

function inferChildEmotion(checkin?: CheckinRecord): ChildEmotionState {
  if (!checkin) return 'fragile';
  const transitionDifficulty = checkin.transition_difficulty ?? 5;
  if (
    checkin.meltdown_count >= 3 ||
    transitionDifficulty >= 8 ||
    checkin.sensory_overload_level === 'heavy'
  ) {
    return 'meltdown_risk';
  }
  if (
    checkin.meltdown_count >= 2 ||
    transitionDifficulty >= 7 ||
    checkin.sensory_overload_level === 'medium'
  ) {
    return 'escalating';
  }
  if (checkin.meltdown_count === 0 && ['none', 'light'].includes(checkin.sensory_overload_level)) {
    return 'calm';
  }
  return 'fragile';
}

function buildInitialForm(checkin?: CheckinRecord): FormValues {
  return {
    caregiver_stress: checkin?.caregiver_stress ?? 5,
    caregiver_sleep_quality: checkin?.caregiver_sleep_quality ?? 5,
    support_available: checkin?.support_available ?? 'one',
    child_emotional_state: inferChildEmotion(checkin),
    sensory_overload_level: checkin?.sensory_overload_level ?? 'light',
    transition_difficulty: checkin?.transition_difficulty ?? 5,
    meltdown_count: checkin?.meltdown_count ?? 0,
    notes: ''
  };
}

export function MicroRespiteModal({ open, token, familyId, initialCheckin, risk, onClose }: Props) {
  const [form, setForm] = useState<FormValues>(buildInitialForm(initialCheckin));
  const [result, setResult] = useState<MicroRespiteGenerateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeOptionId, setActiveOptionId] = useState<string | null>(null);
  const [pausedOptionId, setPausedOptionId] = useState<string | null>(null);
  const [feedbackTargetId, setFeedbackTargetId] = useState<string | null>(null);
  const [feedbackEffectiveness, setFeedbackEffectiveness] = useState<Effectiveness>('helpful');
  const [feedbackMatched, setFeedbackMatched] = useState(true);
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [declinedIds, setDeclinedIds] = useState<string[]>([]);
  const [feedbackByOption, setFeedbackByOption] = useState<Record<string, MicroRespiteFeedbackResponse>>({});
  const outcomeAnchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setForm(buildInitialForm(initialCheckin));
    setResult(null);
    setLoading(false);
    setFeedbackLoading(false);
    setError('');
    setActiveOptionId(null);
    setPausedOptionId(null);
    setFeedbackTargetId(null);
    setFeedbackEffectiveness('helpful');
    setFeedbackMatched(true);
    setFeedbackNotes('');
    setDeclinedIds([]);
    setFeedbackByOption({});
  }, [open, initialCheckin]);

  useEffect(() => {
    if (!open || (!result && !error)) return;

    const anchor = outcomeAnchorRef.current;
    if (!anchor) return;

    const frameId = window.requestAnimationFrame(() => {
      anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
      anchor.focus({ preventScroll: true });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [error, open, result]);

  const riskLabel = useMemo(() => {
    if (!risk) return '';
    return {
      green: '低风险',
      yellow: '谨慎模式',
      red: '高压模式'
    }[risk.risk_level];
  }, [risk]);

  if (!open) return null;

  const generate = async () => {
    if (!familyId) {
      setError('请先创建家庭档案。');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await generateMicroRespite(token, {
        family_id: familyId,
        ...form,
        high_risk_selected: false
      });
      setResult(data);
      setActiveOptionId(null);
      setPausedOptionId(null);
      setFeedbackTargetId(null);
      setDeclinedIds([]);
      setFeedbackByOption({});
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const markDeclined = (optionId: string) => {
    setDeclinedIds((prev) => (prev.includes(optionId) ? prev : [...prev, optionId]));
    if (activeOptionId === optionId) setActiveOptionId(null);
    if (pausedOptionId === optionId) setPausedOptionId(null);
    if (feedbackTargetId === optionId) setFeedbackTargetId(null);
  };

  const openFeedback = (optionId: string) => {
    setFeedbackTargetId(optionId);
    setFeedbackEffectiveness('helpful');
    setFeedbackMatched(true);
    setFeedbackNotes('');
  };

  const submitFeedback = async (option: MicroRespiteOption) => {
    if (!familyId) {
      setError('请先创建家庭档案。');
      return;
    }

    setFeedbackLoading(true);
    setError('');
    try {
      const data = await submitMicroRespiteFeedback(token, {
        family_id: familyId,
        option_id: option.option_id,
        source_card_ids: option.source_card_ids,
        effectiveness: feedbackEffectiveness,
        matched_expectation: feedbackMatched,
        notes: feedbackNotes
      });
      setFeedbackByOption((prev) => ({ ...prev, [option.option_id]: data }));
      setFeedbackTargetId(null);
      setActiveOptionId(null);
      setPausedOptionId(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setFeedbackLoading(false);
    }
  };

  return (
    <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="micro-respite-title">
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-card modal-card-wide micro-respite-modal-card">
        <button className="icon-btn micro-respite-close" type="button" onClick={onClose} aria-label="关闭微喘息弹窗">
          ×
        </button>

        <div className="micro-respite-scroll">
          <div className="micro-respite-shell">
            <div className="micro-respite-header">
              <div>
                <p className="eyebrow">微喘息支持</p>
                <h3 id="micro-respite-title">开始微喘息</h3>
                <p className="muted">先补充此刻状态，再生成 3 条可执行的个性化建议。</p>
              </div>
              <div className="micro-meta">
                {riskLabel ? <span className="date-pill">{riskLabel}</span> : null}
                {risk?.reasons?.[0] ? <span className="date-pill">{risk.reasons[0]}</span> : null}
              </div>
            </div>

            <div className="question-group">
              <h4>实时状态</h4>
              <div className="grid two">
                <label className="range-field">
                  <div className="field-head">
                    <span>家长当前压力</span>
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
                    <span>家长当前睡眠质量</span>
                    <strong>{form.caregiver_sleep_quality} / 10</strong>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    step="1"
                    value={form.caregiver_sleep_quality}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, caregiver_sleep_quality: Number(e.target.value) }))
                    }
                  />
                </label>
              </div>

              <fieldset className="segmented">
                <legend className="label">孩子此刻情绪</legend>
                {[
                  { label: '平稳', value: 'calm' },
                  { label: '脆弱', value: 'fragile' },
                  { label: '升级中', value: 'escalating' },
                  { label: '接近失控', value: 'meltdown_risk' }
                ].map((item) => (
                  <label
                    key={item.value}
                    className={`option-chip ${form.child_emotional_state === item.value ? 'active' : ''}`}
                  >
                    <input
                      type="radio"
                      name="child_emotional_state"
                      checked={form.child_emotional_state === item.value}
                      onChange={() =>
                        setForm((prev) => ({ ...prev, child_emotional_state: item.value as ChildEmotionState }))
                      }
                    />
                    <span>{item.label}</span>
                  </label>
                ))}
              </fieldset>

              <div className="grid two">
                <label>
                  <span className="label">感官过载</span>
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
                  <legend className="label">可用支持</legend>
                  {[
                    { label: '无人接手', value: 'none' },
                    { label: '有 1 人', value: 'one' },
                    { label: '有 2 人+', value: 'two_plus' }
                  ].map((item) => (
                    <label
                      key={item.value}
                      className={`option-chip ${form.support_available === item.value ? 'active' : ''}`}
                    >
                      <input
                        type="radio"
                        name="support_available_micro"
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

              <div className="grid two">
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
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, transition_difficulty: Number(e.target.value) }))
                    }
                  />
                </label>

                <fieldset className="segmented">
                  <legend className="label">今日冲突 / 崩溃次数</legend>
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
                        name="micro_meltdown_count"
                        checked={form.meltdown_count === item.value}
                        onChange={() => setForm((prev) => ({ ...prev, meltdown_count: item.value }))}
                      />
                      <span>{item.label}</span>
                    </label>
                  ))}
                </fieldset>
              </div>

              <label>
                <span className="label">补充说明</span>
                <textarea
                  className="input textarea"
                  rows={3}
                  value={form.notes}
                  placeholder="例如：刚从学校回来、家里很吵、支持者 20 分钟后能接手。"
                  onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
                />
              </label>

              <div className="micro-actions">
                <button className="btn secondary" type="button" onClick={onClose}>
                  取消
                </button>
                <button className="btn" type="button" disabled={loading} onClick={generate}>
                  {loading ? '生成中...' : '生成 3 条建议'}
                </button>
              </div>
            </div>

            <div ref={outcomeAnchorRef} tabIndex={-1} aria-hidden="true" />

            {result?.blocked && result.safety_block ? <SafetyBlockCard block={result.safety_block} /> : null}

            {!result?.blocked && result?.plan ? (
              <div className="micro-results">
                <div className="panel micro-plan-summary">
                  <div>
                    <p className="eyebrow">个性化建议</p>
                    <h4>{sanitizeDisplayText(result.plan.headline)}</h4>
                  </div>
                  <p>{result.plan.context_summary}</p>
                  <div className="chip-row">
                    {result.plan.safety_notes.map((note) => (
                      <span key={note} className="info-chip">
                        {note}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="micro-option-grid balanced-card-grid cols-2">
                  {result.plan.options.map((option) => {
                    const declined = declinedIds.includes(option.option_id);
                    const feedback = feedbackByOption[option.option_id];
                    const active = activeOptionId === option.option_id;
                    const paused = pausedOptionId === option.option_id;
                    const collectingFeedback = feedbackTargetId === option.option_id;

                    return (
                      <div
                        key={option.option_id}
                        className={`panel micro-option-card ${declined ? 'micro-option-muted' : ''}`}
                      >
                        <div className="micro-option-top">
                          <div>
                            <p className="eyebrow">方案 {option.duration_minutes} 分钟</p>
                            <h4>{option.title}</h4>
                          </div>
                          {option.requires_manual_review ? (
                            <span className="status-pill warning">需人工复核</span>
                          ) : option.low_stimulation_only ? (
                            <span className="status-pill">低刺激</span>
                          ) : null}
                        </div>

                        <p>{option.summary}</p>
                        <p className="muted">{option.fit_reason}</p>

                        <div className="micro-focus-grid">
                          <div className="micro-focus-box">
                            <p className="label">孩子这段时间做什么</p>
                            <p>{option.child_focus}</p>
                          </div>
                          <div className="micro-focus-box">
                            <p className="label">家长这段时间做什么</p>
                            <p>{option.parent_focus}</p>
                          </div>
                        </div>

                        <div className="micro-list-block">
                          <p className="label">开始前</p>
                          <ul className="list">
                            {option.setup_steps.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="micro-list-block">
                          <p className="label">执行方式</p>
                          <ol className="list">
                            {option.instructions.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ol>
                        </div>

                        <div className="micro-list-block">
                          <p className="label">安全提醒</p>
                          <ul className="list">
                            {option.safety_notes.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>

                        <p className="muted">{option.support_plan}</p>

                        {feedback ? (
                          <div className="micro-state-box success">
                            <strong>已记录反馈</strong>
                            <p>{feedback.next_hint}</p>
                          </div>
                        ) : collectingFeedback ? (
                          <div className="micro-feedback-box">
                            <p className="label">效果如何</p>
                            <div className="chip-row">
                              {[
                                { label: '有效', value: 'helpful' },
                                { label: '一般', value: 'somewhat' },
                                { label: '无效', value: 'not_helpful' }
                              ].map((item) => (
                                <button
                                  key={item.value}
                                  type="button"
                                  className={`chip-btn ${feedbackEffectiveness === item.value ? 'active' : ''}`}
                                  onClick={() => setFeedbackEffectiveness(item.value as Effectiveness)}
                                >
                                  {item.label}
                                </button>
                              ))}
                            </div>
                            <p className="label">是否符合预期</p>
                            <div className="chip-row">
                              <button
                                type="button"
                                className={`chip-btn ${feedbackMatched ? 'active' : ''}`}
                                onClick={() => setFeedbackMatched(true)}
                              >
                                符合
                              </button>
                              <button
                                type="button"
                                className={`chip-btn ${!feedbackMatched ? 'active' : ''}`}
                                onClick={() => setFeedbackMatched(false)}
                              >
                                不符合
                              </button>
                            </div>
                            <label>
                              <span className="label">补充说明</span>
                              <textarea
                                className="input textarea"
                                rows={3}
                                value={feedbackNotes}
                                placeholder="例如：孩子今天无法等待，或支持者交接非常顺利。"
                                onChange={(e) => setFeedbackNotes(e.target.value)}
                              />
                            </label>
                            <div className="micro-actions">
                              <button className="btn secondary" type="button" onClick={() => setFeedbackTargetId(null)}>
                                稍后再说
                              </button>
                              <button
                                className="btn"
                                type="button"
                                disabled={feedbackLoading}
                                onClick={() => submitFeedback(option)}
                              >
                                {feedbackLoading ? '提交中...' : '提交反馈'}
                              </button>
                            </div>
                          </div>
                        ) : active ? (
                          <div className="micro-state-box">
                            <strong>进行中</strong>
                            <p>{result.plan?.feedback_prompt}</p>
                            <div className="micro-actions">
                              <button
                                className="btn secondary"
                                type="button"
                                onClick={() => {
                                  setActiveOptionId(null);
                                  setPausedOptionId(option.option_id);
                                }}
                              >
                                暂停一下
                              </button>
                              <button className="btn" type="button" onClick={() => openFeedback(option.option_id)}>
                                完成后反馈
                              </button>
                            </div>
                          </div>
                        ) : paused ? (
                          <div className="micro-state-box paused">
                            <strong>已暂停</strong>
                            <p>这条建议先挂起，等你准备好再回来继续。</p>
                            <div className="micro-actions">
                              <button className="btn secondary" type="button" onClick={() => markDeclined(option.option_id)}>
                                直接跳过
                              </button>
                              <button
                                className="btn"
                                type="button"
                                onClick={() => {
                                  setPausedOptionId(null);
                                  setActiveOptionId(option.option_id);
                                }}
                              >
                                恢复开始
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="micro-actions">
                            <button
                              className="btn secondary"
                              type="button"
                              onClick={() => {
                                setActiveOptionId(null);
                                setPausedOptionId(option.option_id);
                              }}
                              disabled={option.requires_manual_review}
                            >
                              稍后开始
                            </button>
                            <button
                              className="btn secondary"
                              type="button"
                              onClick={() => markDeclined(option.option_id)}
                            >
                              跳过
                            </button>
                            <button
                              className="btn"
                              type="button"
                              disabled={declined || option.requires_manual_review}
                              onClick={() => {
                                setDeclinedIds((prev) => prev.filter((id) => id !== option.option_id));
                                setPausedOptionId(null);
                                setActiveOptionId(option.option_id);
                              }}
                            >
                              {declined ? '已跳过' : '确认开始'}
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {error ? <div className="panel error">{error}</div> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
