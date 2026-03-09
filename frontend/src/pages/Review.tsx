import { useEffect, useState } from 'react';

import { ReviewCard } from '../components/ReviewCard';
import {
  exportWeeklyReport,
  getMonthlyReport,
  getWeeklyReport,
  submitReportFeedback,
  submitReview
} from '../lib/api';
import type { FeedbackValue, MonthlyReport, ReportTargetKind, WeeklyReport } from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
}

interface ReviewFormState {
  scenario: 'transition' | 'bedtime' | 'homework' | 'outing';
  intensity: 'light' | 'medium' | 'heavy';
  triggers: string;
  cardIds: string;
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

function parseCommaSeparated(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

const initialForm: ReviewFormState = {
  scenario: 'transition',
  intensity: 'medium',
  triggers: '等待, 噪音',
  cardIds: 'CARD-0001',
  outcome: 1,
  notes: '',
  followupAction: ''
};

export function ReviewPage({ token, familyId }: Props) {
  const [form, setForm] = useState<ReviewFormState>(initialForm);
  const [weekStart, setWeekStart] = useState(currentWeekStartISO);
  const [monthValue, setMonthValue] = useState(currentMonthValue);
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null);
  const [monthlyReport, setMonthlyReport] = useState<MonthlyReport | null>(null);
  const [loadingReports, setLoadingReports] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [exportingWeekly, setExportingWeekly] = useState(false);
  const [feedbackSavingKey, setFeedbackSavingKey] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const monthStart = monthValueToISO(monthValue);

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

    setSubmittingReview(true);
    setError('');
    setNotice('');
    try {
      await submitReview(token, {
        family_id: familyId,
        scenario: form.scenario,
        intensity: form.intensity,
        triggers: parseCommaSeparated(form.triggers),
        card_ids: parseCommaSeparated(form.cardIds),
        outcome_score: form.outcome,
        notes: form.notes.trim(),
        followup_action: form.followupAction.trim()
      });
      await Promise.all([refreshWeekly(), refreshMonthly()]);
      setNotice('复盘已提交，周报和月报已刷新。');
      setForm((prev) => ({ ...prev, notes: '', followupAction: '' }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleExport = async () => {
    if (!familyId) return;
    setExportingWeekly(true);
    setError('');
    setNotice('');
    try {
      await exportWeeklyReport(token, familyId, weekStart);
      await refreshWeekly();
      setNotice('周报导出计数已更新。');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setExportingWeekly(false);
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
    return <div className="panel muted">请先创建家庭，再开始周报和月报复盘。</div>;
  }

  return (
    <div className="review-page">
      <div className="panel review-form-shell">
        <div className="review-form-header">
          <div>
            <p className="eyebrow">Quick Review</p>
            <h3>1 分钟补一条复盘</h3>
          </div>
          <p className="muted">复盘越完整，周报和月报的触发器、策略和趋势判断越可靠。</p>
        </div>

        <div className="grid two">
          <label>
            <span className="label">场景</span>
            <select
              className="input"
              value={form.scenario}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, scenario: e.target.value as ReviewFormState['scenario'] }))
              }
            >
              <option value="transition">过渡</option>
              <option value="bedtime">睡前</option>
              <option value="homework">作业</option>
              <option value="outing">外出</option>
            </select>
          </label>

          <label>
            <span className="label">强度</span>
            <select
              className="input"
              value={form.intensity}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, intensity: e.target.value as ReviewFormState['intensity'] }))
              }
            >
              <option value="light">轻度</option>
              <option value="medium">中度</option>
              <option value="heavy">重度</option>
            </select>
          </label>

          <label>
            <span className="label">触发器（逗号分隔）</span>
            <input
              className="input"
              value={form.triggers}
              onChange={(e) => setForm((prev) => ({ ...prev, triggers: e.target.value }))}
            />
          </label>

          <label>
            <span className="label">策略卡 IDs（逗号分隔）</span>
            <input
              className="input"
              value={form.cardIds}
              onChange={(e) => setForm((prev) => ({ ...prev, cardIds: e.target.value }))}
            />
          </label>

          <label>
            <span className="label">效果评分（-2 到 2）</span>
            <input
              className="input"
              type="number"
              min={-2}
              max={2}
              value={form.outcome}
              onChange={(e) => setForm((prev) => ({ ...prev, outcome: Number(e.target.value) }))}
            />
          </label>

          <label>
            <span className="label">下次改进动作</span>
            <input
              className="input"
              value={form.followupAction}
              onChange={(e) => setForm((prev) => ({ ...prev, followupAction: e.target.value }))}
              placeholder="例如：保留睡前过渡预告"
            />
          </label>
        </div>

        <label>
          <span className="label">复盘备注</span>
          <textarea
            className="input textarea"
            value={form.notes}
            onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
            placeholder="记录这次执行的情况、孩子反应、家长感受。"
          />
        </label>

        <div className="review-actions">
          <button className="btn" onClick={submit} disabled={submittingReview}>
            {submittingReview ? '提交中...' : '提交复盘'}
          </button>
          <span className="muted">建议每周至少补 1 次高摩擦场景复盘。</span>
        </div>
      </div>

      <div className="panel review-toolbar">
        <label>
          <span className="label">查看周</span>
          <input className="input" type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} />
        </label>

        <label>
          <span className="label">查看月份</span>
          <input className="input" type="month" value={monthValue} onChange={(e) => setMonthValue(e.target.value)} />
        </label>

        <div className="review-toolbar-meta">
          <span className="status-pill">{loadingReports ? '报告刷新中' : '报告已同步'}</span>
          <button className="btn secondary" onClick={handleExport} disabled={exportingWeekly}>
            {exportingWeekly ? '导出中...' : '导出本周报告'}
          </button>
        </div>
      </div>

      {notice ? <div className="panel review-notice">{notice}</div> : null}
      {error ? <div className="panel error">{error}</div> : null}

      <ReviewCard
        weeklyReport={weeklyReport}
        monthlyReport={monthlyReport}
        loading={loadingReports}
        exportingWeekly={exportingWeekly}
        feedbackSavingKey={feedbackSavingKey}
        onExportWeekly={handleExport}
        onFeedback={handleFeedback}
      />
    </div>
  );
}
