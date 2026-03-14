import { useEffect, useState } from 'react';

import { ReviewCard } from '../components/ReviewCard';
import { TagSelector } from '../components/TagSelector';
import {
  getMonthlyReport,
  getWeeklyReport,
  submitReportFeedback,
  submitReview
} from '../lib/api';
import { sanitizeDisplayText } from '../lib/displayText';
import {
  getActionSourceLabel,
  getScenarioLabel,
  type ActionFlowContext,
  type CareTab
} from '../lib/flow';
import {
  buildReviewScenarioDraft,
  CUSTOM_REVIEW_SCENARIO_VALUE,
  resolveReviewScenarioValue,
  reviewScenarioOptions,
  type ReviewScenarioDraft
} from '../lib/reviewForm';
import type { FeedbackValue, MonthlyReport, ReportTargetKind, WeeklyReport } from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
  actionContext: ActionFlowContext | null;
  onNavigate: (tab: CareTab) => void;
  onActionContextChange: (context: ActionFlowContext | null) => void;
}

interface ReviewFormState extends ReviewScenarioDraft {
  intensity: 'light' | 'medium' | 'heavy';
  triggers: string[];
  responseAction: string;
  outcome: number;
  notes: string;
  followupAction: string;
}

function currentWeekStartISO() {
  const now = new Date();
  const day = now.getDay() || 7;
  const monday = new Date(now);
  monday.setDate(now.getDate() - day + 1);
  return monday.toISOString().slice(0, 10);
}

function currentMonthValue() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${now.getFullYear()}-${month}`;
}

function monthValueToISO(value: string) {
  return `${value}-01`;
}

function buildInitialForm(context: ActionFlowContext | null): ReviewFormState {
  return {
    ...buildReviewScenarioDraft(context),
    intensity: 'medium',
    triggers: context?.suggestedTriggers.length ? context.suggestedTriggers : ['等待'],
    responseAction: '',
    outcome: 1,
    notes: '',
    followupAction: context?.suggestedFollowup || ''
  };
}

const triggerOptions = [
  '等待',
  '噪音',
  '临时变化',
  '作业要求',
  '睡前切换',
  '出门',
  '饥饿',
  '社交压力'
];

const outcomeOptions = [
  { value: 2, label: '明显更稳了', hint: '这次做法值得保留' },
  { value: 1, label: '有帮助', hint: '方向对，但还可微调' },
  { value: 0, label: '一般', hint: '没有明显变好变坏' },
  { value: -1, label: '更难了', hint: '做法需要调整' },
  { value: -2, label: '直接失效', hint: '下次别再硬撑这套' }
] as const;

export function ReviewPage({ token, familyId, actionContext, onNavigate, onActionContextChange }: Props) {
  const [form, setForm] = useState<ReviewFormState>(() => buildInitialForm(actionContext));
  const [weekStart, setWeekStart] = useState(currentWeekStartISO);
  const [monthValue, setMonthValue] = useState(currentMonthValue);
  const [activePeriod, setActivePeriod] = useState<'weekly' | 'monthly'>('weekly');
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null);
  const [monthlyReport, setMonthlyReport] = useState<MonthlyReport | null>(null);
  const [loadingReports, setLoadingReports] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [feedbackSavingKey, setFeedbackSavingKey] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const monthStart = monthValueToISO(monthValue);

  useEffect(() => {
    setForm(buildInitialForm(actionContext));
  }, [actionContext]);

  useEffect(() => {
    if (!familyId) {
      setWeeklyReport(null);
      setMonthlyReport(null);
      return;
    }

    let cancelled = false;

    const loadReports = async () => {
      setLoadingReports(true);
      setError('');
      try {
        const [weekly, monthly] = await Promise.all([
          getWeeklyReport(token, familyId, weekStart),
          getMonthlyReport(token, familyId, monthStart)
        ]);
        if (!cancelled) {
          setWeeklyReport(weekly);
          setMonthlyReport(monthly);
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message);
        }
      } finally {
        if (!cancelled) {
          setLoadingReports(false);
        }
      }
    };

    void loadReports();

    return () => {
      cancelled = true;
    };
  }, [token, familyId, weekStart, monthStart]);

  useEffect(() => {
    if (activePeriod === 'weekly' && !weeklyReport && monthlyReport) {
      setActivePeriod('monthly');
      return;
    }
    if (activePeriod === 'monthly' && !monthlyReport && weeklyReport) {
      setActivePeriod('weekly');
    }
  }, [activePeriod, weeklyReport, monthlyReport]);

  const refreshWeekly = async () => {
    if (!familyId) return;
    const weekly = await getWeeklyReport(token, familyId, weekStart);
    setWeeklyReport(weekly);
  };

  const refreshMonthly = async () => {
    if (!familyId) return;
    const monthly = await getMonthlyReport(token, familyId, monthStart);
    setMonthlyReport(monthly);
  };

  const submit = async () => {
    if (!familyId) {
      setError('请先创建家庭。');
      return;
    }

    const submittedScenario = resolveReviewScenarioValue(form);
    if (!submittedScenario) {
      setError('请先填写场景名称。');
      return;
    }
    if (!form.responseAction.trim()) {
      setError('请先填写应对方式。');
      return;
    }

    setSubmittingReview(true);
    setError('');
    setNotice('');
    try {
      await submitReview(token, {
        family_id: familyId,
        scenario: submittedScenario,
        intensity: form.intensity,
        triggers: form.triggers,
        card_ids: actionContext?.cardIds.length ? actionContext.cardIds : [],
        outcome_score: form.outcome,
        response_action: form.responseAction.trim(),
        notes: form.notes.trim(),
        followup_action: form.followupAction.trim()
      });
      await Promise.all([refreshWeekly(), refreshMonthly()]);
      onActionContextChange(null);
      setNotice('复盘已提交，报告已刷新。');
      setForm(buildInitialForm(null));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleFeedback = async (payload: {
    periodType: 'weekly' | 'monthly';
    periodStart: string;
    targetKind: ReportTargetKind;
    targetKey: string;
    targetLabel: string;
    feedback: FeedbackValue;
  }) => {
    if (!familyId) return;
    const savingKey = `${payload.periodType}:${payload.targetKind}:${payload.targetKey}`;
    setFeedbackSavingKey(savingKey);
    setError('');
    try {
      await submitReportFeedback(token, {
        family_id: familyId,
        period_type: payload.periodType,
        period_start: payload.periodStart,
        target_kind: payload.targetKind,
        target_key: payload.targetKey,
        target_label: payload.targetLabel,
        feedback: payload.feedback
      });
      if (payload.periodType === 'weekly') {
        await refreshWeekly();
      } else {
        await refreshMonthly();
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setFeedbackSavingKey('');
    }
  };

  if (!familyId) {
    return <div className="panel muted">请先创建家庭，再开始轻复盘和周报/月报查看。</div>;
  }

  return (
    <div className="content-page-shell review-page-shell">
      <div className="review-page">
      <section className="panel review-quick-panel">
        <div className="review-form-header">
          <div>
            <p className="eyebrow">轻复盘</p>
            <h3>只记结果、触发器、保留项</h3>
          </div>
          <button className="btn secondary" type="button" onClick={() => onNavigate('today')}>
            回到今天页
          </button>
        </div>

        {actionContext ? (
          <div className="review-context-card">
            <div className="focus-header">
              <div>
                <p className="eyebrow">当前行动</p>
                <h4>{sanitizeDisplayText(actionContext.title)}</h4>
              </div>
              <span className="status-chip active">
                {getActionSourceLabel(actionContext.source)} · {getScenarioLabel(actionContext.sourceScenario ?? actionContext.scenario)}
              </span>
            </div>
            <p>{sanitizeDisplayText(actionContext.summary)}</p>
          </div>
        ) : (
          <div className="review-context-card">
            <p className="eyebrow">无待复盘行动</p>
            <p className="muted">也可以手动补一条。</p>
          </div>
        )}

        <label>
          <span className="label">场景</span>
          <select
            className="input"
            value={form.scenarioSelection}
            onChange={(e) => {
              const value = e.target.value as ReviewFormState['scenarioSelection'];
              setForm((prev) =>
                value === CUSTOM_REVIEW_SCENARIO_VALUE
                  ? { ...prev, scenarioSelection: value }
                  : { ...prev, scenario: value, scenarioSelection: value, customScenarioName: '' }
              );
            }}
          >
            {reviewScenarioOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
            <option value={CUSTOM_REVIEW_SCENARIO_VALUE}>自己填写</option>
          </select>
        </label>

        {form.scenarioSelection === CUSTOM_REVIEW_SCENARIO_VALUE ? (
          <label>
            <span className="label">自定义场景</span>
            <input
              className="input"
              value={form.customScenarioName}
              onChange={(e) => setForm((prev) => ({ ...prev, customScenarioName: e.target.value }))}
              placeholder="例如：理发店、吃饭、上兴趣班。"
            />
          </label>
        ) : null}

        <div className="option-group">
          <span className="label">结果怎么样</span>
          <div className="review-outcome-grid">
            {outcomeOptions.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`option-card ${form.outcome === item.value ? 'active' : ''}`}
                onClick={() => setForm((prev) => ({ ...prev, outcome: item.value }))}
              >
                <strong>{item.label}</strong>
                <span>{item.hint}</span>
              </button>
            ))}
          </div>
        </div>

        <TagSelector
          label="主要触发器"
          values={form.triggers}
          options={triggerOptions}
          onChange={(next) => setForm((prev) => ({ ...prev, triggers: next }))}
          helper="选 1-3 个。"
          customPlaceholder="补充触发器"
          variant="pill"
        />

        <label>
          <span className="label">应对方式</span>
          <input
            className="input"
            value={form.responseAction}
            onChange={(e) => setForm((prev) => ({ ...prev, responseAction: e.target.value }))}
            placeholder="例如：先预告两分钟，再只给一个选择。"
          />
        </label>

        <label>
          <span className="label">下次继续保留</span>
          <input
            className="input"
            value={form.followupAction}
            onChange={(e) => setForm((prev) => ({ ...prev, followupAction: e.target.value }))}
            placeholder="例如：先预告，再带离现场。"
          />
        </label>

        <details className="review-optional-panel">
          <summary>补充信息（可选）</summary>
          <div className="review-optional-body">
            <div className="grid two">
              <label>
                <span className="label">强度</span>
                <select
                  className="input"
                  value={form.intensity}
                  onChange={(e) => setForm((prev) => ({ ...prev, intensity: e.target.value as ReviewFormState['intensity'] }))}
                >
                  <option value="light">轻度</option>
                  <option value="medium">中度</option>
                  <option value="heavy">重度</option>
                </select>
              </label>
            </div>

            <label>
              <span className="label">备注</span>
              <textarea
                className="input textarea"
                value={form.notes}
                onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
                placeholder="只记关键观察。"
              />
            </label>
          </div>
        </details>

        <div className="review-actions">
          <button className="btn" type="button" onClick={submit} disabled={submittingReview}>
            {submittingReview ? '提交中...' : '提交复盘'}
          </button>
          <span className="muted">先交最小记录。</span>
        </div>
      </section>

      {notice ? <div className="panel review-notice">{notice}</div> : null}
      {error ? <div className="panel error">{error}</div> : null}

      <section className="panel review-toolbar">
        <div className="review-period-switch" role="tablist" aria-label="复盘周期切换">
          <button
            type="button"
            className={`plan-mode-btn ${activePeriod === 'weekly' ? 'active' : ''}`}
            onClick={() => setActivePeriod('weekly')}
            aria-pressed={activePeriod === 'weekly'}
          >
            本周
          </button>
          <button
            type="button"
            className={`plan-mode-btn ${activePeriod === 'monthly' ? 'active' : ''}`}
            onClick={() => setActivePeriod('monthly')}
            aria-pressed={activePeriod === 'monthly'}
          >
            本月
          </button>
        </div>

        {activePeriod === 'weekly' ? (
          <label>
            <span className="label">查看周</span>
            <input className="input" type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} />
          </label>
        ) : (
          <label>
            <span className="label">查看月份</span>
            <input className="input" type="month" value={monthValue} onChange={(e) => setMonthValue(e.target.value)} />
          </label>
        )}

        <div className="review-toolbar-meta">
          {loadingReports ? <span className="status-pill">同步中</span> : null}
        </div>
      </section>

        <ReviewCard
          activePeriod={activePeriod}
          weeklyReport={weeklyReport}
          monthlyReport={monthlyReport}
          loading={loadingReports}
          feedbackSavingKey={feedbackSavingKey}
          onFeedback={handleFeedback}
        />
      </div>
    </div>
  );
}
