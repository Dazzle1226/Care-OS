import type { ReactNode } from 'react';

import type {
  ActionSuggestion,
  FeedbackValue,
  MonthlyHistoryPoint,
  MonthlyReport,
  MonthlyTrendItem,
  ReplayItem,
  ReportMetricPoint,
  ReportFeedbackState,
  ReportTargetKind,
  StrategyInsight,
  TrendDeltaItem,
  WeeklyReport
} from '../lib/types';
import { getScenarioLabel } from '../lib/flow';

interface Props {
  activePeriod: 'weekly' | 'monthly';
  weeklyReport: WeeklyReport | null;
  monthlyReport: MonthlyReport | null;
  loading: boolean;
  feedbackSavingKey: string;
  onFeedback: (payload: {
    periodType: 'weekly' | 'monthly';
    periodStart: string;
    targetKind: ReportTargetKind;
    targetKey: string;
    targetLabel: string;
    feedback: FeedbackValue;
  }) => void;
}

function formatDateRange(start: string, end: string) {
  const formatter = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' });
  return `${formatter.format(new Date(`${start}T00:00:00`))} - ${formatter.format(new Date(`${end}T00:00:00`))}`;
}

function findFeedback(
  states: ReportFeedbackState[],
  targetKind: ReportTargetKind,
  targetKey: string
): FeedbackValue | undefined {
  return states.find((item) => item.target_kind === targetKind && item.target_key === targetKey)?.feedback;
}

const recommendationLabel: Record<'continue' | 'pause' | 'replace', string> = {
  continue: '继续',
  pause: '暂停',
  replace: '替换'
};

const applicabilityLabel: Record<'high' | 'medium' | 'low', string> = {
  high: '高适配',
  medium: '中适配',
  low: '低适配'
};

const directionLabel: Record<'up' | 'down' | 'flat', string> = {
  up: '上升',
  down: '下降',
  flat: '持平'
};

function ScoreRing({
  value,
  max = 100,
  tone = 'warm'
}: {
  value: number;
  max?: number;
  tone?: 'warm' | 'calm';
}) {
  const safeValue = Math.max(0, Math.min(Math.round(value), max));
  const size = 104;
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safeValue / max) * circumference;

  return (
    <div className={`score-ring ${tone === 'calm' ? 'calm' : ''}`}>
      <svg viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="score-ring-track" cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} />
        <circle
          className="score-ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="score-ring-value">
        <strong>{safeValue}</strong>
        <span>/ {max}</span>
      </div>
    </div>
  );
}

function MiniBars({
  points,
  maxValue
}: {
  points: ReportMetricPoint[];
  maxValue?: number;
}) {
  const ceiling = maxValue ?? Math.max(...points.map((item) => item.value), 1);

  return (
    <div className="mini-bars">
      {points.map((point) => {
        const height = ceiling === 0 ? 10 : Math.max((point.value / ceiling) * 100, point.value > 0 ? 16 : 10);
        return (
          <div className="mini-bar-col" key={point.label}>
            <div className="mini-bar-track">
              <div className="mini-bar-fill" style={{ height: `${height}%` }} />
            </div>
            <span>{point.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function HistoryBars({ items }: { items: MonthlyHistoryPoint[] }) {
  const recent = items.slice(-4);
  const ceiling = Math.max(...recent.map((item) => item.task_completion_rate), 100);

  return (
    <div className="history-bars">
      {recent.map((item) => {
        const height = Math.max((item.task_completion_rate / ceiling) * 100, 18);
        return (
          <div className="history-bar-col" key={item.label}>
            <span className="history-bar-value">{item.task_completion_rate}</span>
            <div className="history-bar-track">
              <div className="history-bar-fill" style={{ height: `${height}%` }} />
            </div>
            <span className="history-bar-label">{item.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function DashboardMetric({
  label,
  value,
  meta,
  accent,
  children
}: {
  label: string;
  value?: string;
  meta?: string;
  accent?: boolean;
  children?: ReactNode;
}) {
  return (
    <div className={`dashboard-metric-card ${accent ? 'accent' : ''}`}>
      <span className="label">{label}</span>
      {value ? <h4>{value}</h4> : null}
      {meta ? <p className="muted">{meta}</p> : null}
      {children}
    </div>
  );
}

function FeedbackButtons({
  activeValue,
  saving,
  positiveLabel,
  negativeLabel,
  positiveValue,
  negativeValue,
  onChoose
}: {
  activeValue?: FeedbackValue;
  saving: boolean;
  positiveLabel: string;
  negativeLabel: string;
  positiveValue: FeedbackValue;
  negativeValue: FeedbackValue;
  onChoose: (value: FeedbackValue) => void;
}) {
  return (
    <div className="feedback-actions">
      <button
        className={`chip-btn ${activeValue === positiveValue ? 'active' : ''}`}
        type="button"
        disabled={saving}
        onClick={() => onChoose(positiveValue)}
      >
        {saving && activeValue !== positiveValue ? '提交中...' : positiveLabel}
      </button>
      <button
        className={`chip-btn ${activeValue === negativeValue ? 'active' : ''}`}
        type="button"
        disabled={saving}
        onClick={() => onChoose(negativeValue)}
      >
        {negativeLabel}
      </button>
    </div>
  );
}

function StrategyList({
  items,
  states,
  periodType,
  periodStart,
  feedbackSavingKey,
  onFeedback,
  positiveLabel,
  negativeLabel,
  positiveValue,
  negativeValue
}: {
  items: StrategyInsight[];
  states: ReportFeedbackState[];
  periodType: 'weekly' | 'monthly';
  periodStart: string;
  feedbackSavingKey: string;
  onFeedback: Props['onFeedback'];
  positiveLabel: string;
  negativeLabel: string;
  positiveValue: FeedbackValue;
  negativeValue: FeedbackValue;
}) {
  if (!items.length) {
    return <div className="muted">当前还没有足够样本。</div>;
  }

  return (
    <div className="insight-stack">
      {items.map((item) => {
        const saving = feedbackSavingKey === `${periodType}:strategy:${item.target_key}`;
        return (
          <div className="insight-card" key={item.target_key}>
            <div className="insight-card-top">
              <h4>{item.title}</h4>
              <span className="status-pill">{recommendationLabel[item.recommendation]}</span>
            </div>
            <div className="chip-row">
              <span className="info-chip">{item.evidence_count} 次</span>
              <span className="info-chip">{item.success_rate}%</span>
              <span className="info-chip">{applicabilityLabel[item.applicability]}</span>
            </div>
            <FeedbackButtons
              activeValue={findFeedback(states, 'strategy', item.target_key)}
              saving={saving}
              positiveLabel={positiveLabel}
              negativeLabel={negativeLabel}
              positiveValue={positiveValue}
              negativeValue={negativeValue}
              onChoose={(feedback) =>
                onFeedback({
                  periodType,
                  periodStart,
                  targetKind: 'strategy',
                  targetKey: item.target_key,
                  targetLabel: item.title,
                  feedback
                })
              }
            />
          </div>
        );
      })}
    </div>
  );
}

function ActionList({
  items,
  states,
  periodType,
  periodStart,
  feedbackSavingKey,
  onFeedback
}: {
  items: ActionSuggestion[];
  states: ReportFeedbackState[];
  periodType: 'weekly' | 'monthly';
  periodStart: string;
  feedbackSavingKey: string;
  onFeedback: Props['onFeedback'];
}) {
  if (!items.length) {
    return <div className="muted">当前没有新的行动建议。</div>;
  }

  return (
    <div className="insight-stack">
      {items.map((item) => {
        const saving = feedbackSavingKey === `${periodType}:action:${item.target_key}`;
        return (
          <div className="insight-card" key={item.target_key}>
            <div className="insight-card-top">
              <h4>{item.title}</h4>
              <span className="status-pill">{recommendationLabel[item.recommendation]}</span>
            </div>
            <div className="chip-row">
              <span className="info-chip soft">{item.summary}</span>
            </div>
            <FeedbackButtons
              activeValue={findFeedback(states, 'action', item.target_key)}
              saving={saving}
              positiveLabel="继续"
              negativeLabel="调整"
              positiveValue="continue"
              negativeValue="adjust"
              onChoose={(feedback) =>
                onFeedback({
                  periodType,
                  periodStart,
                  targetKind: 'action',
                  targetKey: item.target_key,
                  targetLabel: item.title,
                  feedback
                })
              }
            />
          </div>
        );
      })}
    </div>
  );
}

function TrendCards({ items }: { items: MonthlyTrendItem[] }) {
  return (
    <div className="trend-card-grid">
      {items.map((item) => (
        <div className="trend-card" key={item.title}>
          <div className="trend-card-top">
            <h4>{item.title}</h4>
            <span className={`status-pill ${item.direction === 'up' ? 'warning' : ''}`}>{directionLabel[item.direction]}</span>
          </div>
          <div className="trend-card-values">
            <strong>
              {item.current_value}
              {item.unit}
            </strong>
            <span className="muted">
              上期 {item.previous_value}
              {item.unit}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function TrendDeltaCards({ items }: { items: TrendDeltaItem[] }) {
  return (
    <div className="trend-card-grid">
      {items.map((item) => (
        <div className="trend-card" key={item.title}>
          <div className="trend-card-top">
            <h4>{item.title}</h4>
            <span className={`status-pill ${item.direction === 'up' ? 'warning' : ''}`}>{directionLabel[item.direction]}</span>
          </div>
          <div className="trend-card-values">
            <strong>
              {item.current_value}
              {item.unit}
            </strong>
            <span className="muted">
              上周 {item.previous_value}
              {item.unit}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ReplayList({ items }: { items: ReplayItem[] }) {
  return (
    <div className="insight-stack">
      {items.map((item) => (
        <div className="insight-card" key={item.incident_id}>
          <div className="insight-card-top">
            <h4>{item.scenario}回放</h4>
            <span className="status-pill">{recommendationLabel[item.recommendation]}</span>
          </div>
          <div className="training-goal-stack">
            {item.timeline.map((step) => (
              <div key={`${item.incident_id}-${step.label}`} className="training-goal-card">
                <strong>{step.label}</strong>
                <p>{step.value}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function WeeklyReviewView({
  report,
  feedbackSavingKey,
  onFeedback
}: {
  report: WeeklyReport;
  feedbackSavingKey: string;
  onFeedback: Props['onFeedback'];
}) {
  const highestRiskScenarioLabel = getScenarioLabel(report.highest_risk_scenario);

  return (
    <div className="panel report-card">
      <div className="review-summary-hero">
        <div>
          <p className="eyebrow">本周复盘</p>
          <h3>{formatDateRange(report.week_start, report.week_end)}</h3>
        </div>
        <span className="status-pill">{highestRiskScenarioLabel}</span>
      </div>

      <div className="review-dashboard-grid">
        <DashboardMetric label="完成度" accent>
          <ScoreRing value={report.task_completion_score} />
        </DashboardMetric>
        <DashboardMetric label="压力趋势" meta="7天">
          <MiniBars points={report.stress_trend} maxValue={10} />
        </DashboardMetric>
        <DashboardMetric label="升级次数" meta="7天">
          <MiniBars points={report.meltdown_trend} maxValue={3} />
        </DashboardMetric>
        <DashboardMetric label="风险焦点" value={highestRiskScenarioLabel}>
          <div className="chip-row">
            {report.trigger_top3.length ? (
              report.trigger_top3.map((trigger) => (
                <span className="info-chip" key={trigger}>
                  {trigger}
                </span>
              ))
            ) : (
              <span className="muted">样本不足</span>
            )}
          </div>
        </DashboardMetric>
      </div>

      <div className="review-priority-grid compact">
        <div className="review-priority-card accent">
          <span className="label">结论</span>
          <h4>{report.task_summary}</h4>
        </div>
        <div className="review-priority-card accent">
          <span className="label">下周只做一件</span>
          <h4>{report.one_thing_next_week}</h4>
        </div>
      </div>

      <details className="review-secondary-panel">
        <summary>查看次要信息</summary>
        <div className="review-secondary-body">
          <div className="report-section">
            <h4>趋势变化</h4>
            {report.week_over_week.length ? <TrendDeltaCards items={report.week_over_week} /> : <div className="muted">暂无变化数据。</div>}
          </div>
          <div className="report-section">
            <h4>事件回放</h4>
            {report.replay_items.length ? <ReplayList items={report.replay_items} /> : <div className="muted">本周还没有可回放事件。</div>}
          </div>
          <div className="review-secondary-copy">
            <p>{report.caregiver_summary}</p>
            <p>{report.trigger_summary}</p>
            <p>{report.child_emotion_summary}</p>
          </div>
        </div>
      </details>
    </div>
  );
}

function MonthlyReviewView({
  report,
  feedbackSavingKey,
  onFeedback
}: {
  report: MonthlyReport;
  feedbackSavingKey: string;
  onFeedback: Props['onFeedback'];
}) {
  return (
    <div className="panel report-card">
      <div className="review-summary-hero">
        <div>
          <p className="eyebrow">本月回看</p>
          <h3>{formatDateRange(report.month_start, report.month_end)}</h3>
        </div>
        <span className="status-pill">长期观察</span>
      </div>

      <div className="review-dashboard-grid monthly">
        <DashboardMetric
          label="压力变化"
          value={directionLabel[report.long_term_trends[0]?.direction ?? 'flat']}
          meta={report.stress_change_summary}
        />
        <DashboardMetric
          label="冲突变化"
          value={directionLabel[report.long_term_trends[1]?.direction ?? 'flat']}
          meta={report.conflict_change_summary}
        />
        <DashboardMetric
          label="执行趋势"
          value={directionLabel[report.long_term_trends[2]?.direction ?? 'flat']}
          meta={report.task_completion_summary}
        />
        <DashboardMetric label="近月执行率" accent>
          <HistoryBars items={report.history} />
        </DashboardMetric>
      </div>

      <div className="review-priority-grid compact">
        <div className="review-priority-card accent">
          <span className="label">月结论</span>
          <h4>{report.overview_summary}</h4>
        </div>
      </div>

      <details className="review-secondary-panel">
        <summary>查看长期趋势</summary>
        <div className="review-secondary-body">
          {report.long_term_trends.length ? <TrendCards items={report.long_term_trends} /> : <div className="muted">暂无长期趋势数据。</div>}
          <div className="review-secondary-copy">
            <p>{report.stress_change_summary}</p>
            <p>{report.conflict_change_summary}</p>
            <p>{report.task_completion_summary}</p>
          </div>
        </div>
      </details>
    </div>
  );
}

export function ReviewCard({ activePeriod, weeklyReport, monthlyReport, loading, feedbackSavingKey, onFeedback }: Props) {
  if (loading && !weeklyReport && !monthlyReport) {
    return <div className="panel muted">正在生成复盘...</div>;
  }

  if (!weeklyReport && !monthlyReport) {
    return <div className="panel muted">先补一条复盘，再查看周期总结。</div>;
  }

  if (activePeriod === 'monthly' && monthlyReport) {
    return <MonthlyReviewView report={monthlyReport} feedbackSavingKey={feedbackSavingKey} onFeedback={onFeedback} />;
  }

  if (weeklyReport) {
    return <WeeklyReviewView report={weeklyReport} feedbackSavingKey={feedbackSavingKey} onFeedback={onFeedback} />;
  }

  if (monthlyReport) {
    return <MonthlyReviewView report={monthlyReport} feedbackSavingKey={feedbackSavingKey} onFeedback={onFeedback} />;
  }

  return null;
}
