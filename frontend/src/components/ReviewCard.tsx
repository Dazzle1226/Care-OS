import type {
  ActionSuggestion,
  FeedbackValue,
  MonthlyHistoryPoint,
  MonthlyReport,
  MonthlyTrendItem,
  ReportFeedbackState,
  ReportTargetKind,
  StrategyInsight,
  TaskEffectItem,
  WeeklyReport
} from '../lib/types';

interface Props {
  weeklyReport: WeeklyReport | null;
  monthlyReport: MonthlyReport | null;
  loading: boolean;
  exportingWeekly: boolean;
  feedbackSavingKey: string;
  onExportWeekly: () => void;
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

function MetricBars({ points, maxValue }: { points: { label: string; value: number }[]; maxValue?: number }) {
  const ceiling = maxValue ?? Math.max(...points.map((item) => item.value), 1);

  return (
    <div className="metric-bars">
      {points.map((point) => {
        const height = ceiling === 0 ? 8 : Math.max((point.value / ceiling) * 100, point.value > 0 ? 18 : 8);
        return (
          <div className="metric-bar-col" key={point.label}>
            <span className="metric-bar-value">{point.value}</span>
            <div className="metric-bar-track">
              <div className="metric-bar-fill" style={{ height: `${height}%` }} />
            </div>
            <span className="metric-bar-label">{point.label}</span>
          </div>
        );
      })}
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

function TaskGroup({ title, items }: { title: string; items: TaskEffectItem[] }) {
  return (
    <div className="task-group">
      <div className="task-group-head">
        <h4>{title}</h4>
        <span className="muted">{items.length} 条</span>
      </div>
      {items.length ? (
        items.map((item) => (
          <div className="task-item" key={`${title}-${item.title}`}>
            <strong>{item.title}</strong>
            <p>{item.summary}</p>
          </div>
        ))
      ) : (
        <div className="muted">本周期暂无相关记录。</div>
      )}
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
  return (
    <div className="insight-stack">
      {items.map((item) => {
        const saving = feedbackSavingKey === `${periodType}:strategy:${item.target_key}`;
        return (
          <div className="insight-card" key={item.target_key}>
            <div className="insight-card-top">
              <div>
                <h4>{item.title}</h4>
                <p>{item.summary}</p>
              </div>
              <span className="status-pill">{item.evidence_count} 次记录</span>
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
  return (
    <div className="insight-stack">
      {items.map((item) => {
        const saving = feedbackSavingKey === `${periodType}:action:${item.target_key}`;
        return (
          <div className="insight-card" key={item.target_key}>
            <div className="insight-card-top">
              <div>
                <h4>{item.title}</h4>
                <p>{item.summary}</p>
              </div>
            </div>
            <p className="muted">{item.rationale}</p>
            <FeedbackButtons
              activeValue={findFeedback(states, 'action', item.target_key)}
              saving={saving}
              positiveLabel="继续执行"
              negativeLabel="调整计划"
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
            <span className={`status-pill ${item.direction === 'up' ? 'warning' : ''}`}>
              {item.current_value}
              {item.unit}
            </span>
          </div>
          <p>{item.summary}</p>
          <div className="muted">
            上期：{item.previous_value}
            {item.unit}
          </div>
        </div>
      ))}
    </div>
  );
}

function HistoryCards({ items }: { items: MonthlyHistoryPoint[] }) {
  return (
    <div className="history-grid">
      {items.map((item) => (
        <div className="history-card" key={item.label}>
          <div className="history-card-top">
            <h4>{item.label}</h4>
            <span className="status-pill">{item.task_completion_rate}/100</span>
          </div>
          <div className="history-stat">
            <span className="label">压力均值</span>
            <strong>{item.avg_stress}/10</strong>
          </div>
          <div className="history-stat">
            <span className="label">冲突次数</span>
            <strong>{item.conflict_count}</strong>
          </div>
          <div className="history-progress">
            <div className="history-progress-label">
              <span>任务完成度</span>
              <span>{item.task_completion_rate}%</span>
            </div>
            <div className="history-progress-track">
              <div className="history-progress-fill" style={{ width: `${item.task_completion_rate}%` }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ReviewCard({
  weeklyReport,
  monthlyReport,
  loading,
  exportingWeekly,
  feedbackSavingKey,
  onExportWeekly,
  onFeedback
}: Props) {
  if (loading && !weeklyReport && !monthlyReport) {
    return <div className="panel muted">正在生成周报与月报...</div>;
  }

  if (!weeklyReport && !monthlyReport) {
    return <div className="panel muted">先补一条复盘，再查看周期报告。</div>;
  }

  return (
    <div className="review-report-grid">
      {weeklyReport ? (
        <div className="panel report-card">
          <div className="report-card-header">
            <div>
              <p className="eyebrow">Weekly Review</p>
              <h3>每周总结</h3>
              <p className="muted">{formatDateRange(weeklyReport.week_start, weeklyReport.week_end)}</p>
            </div>
            <div className="report-header-actions">
              <span className="status-pill">导出 {weeklyReport.export_count} 次</span>
              <button className="btn secondary" onClick={onExportWeekly} disabled={exportingWeekly}>
                {exportingWeekly ? '导出中...' : '再次导出'}
              </button>
            </div>
          </div>

          <div className="report-kpi-grid">
            <div className="metric-card">
              <span className="label">本周完成度</span>
              <strong>{weeklyReport.task_completion_score}/100</strong>
              <p>{weeklyReport.task_summary}</p>
            </div>
            <div className="metric-card">
              <span className="label">最高风险场景</span>
              <strong>{weeklyReport.highest_risk_scenario}</strong>
              <p>{weeklyReport.one_thing_next_week}</p>
            </div>
            <div className="metric-card">
              <span className="label">家长压力均值</span>
              <strong>{weeklyReport.caregiver_stress_avg}/10</strong>
              <p>峰值 {weeklyReport.caregiver_stress_peak}/10，恢复 {weeklyReport.caregiver_sleep_avg}/10</p>
            </div>
          </div>

          <div className="report-section">
            <div className="report-section-head">
              <h4>触发器与情绪模式</h4>
              <div className="chip-row">
                {weeklyReport.trigger_top3.map((trigger) => (
                  <span className="info-chip" key={trigger}>
                    {trigger}
                  </span>
                ))}
              </div>
            </div>
            <p>{weeklyReport.trigger_summary}</p>
            <p>{weeklyReport.child_emotion_summary}</p>
            <div className="trend-grid">
              <div className="trend-box">
                <div className="trend-box-head">
                  <h4>家长压力趋势</h4>
                  <span className="muted">过去 7 天</span>
                </div>
                <MetricBars points={weeklyReport.stress_trend} maxValue={10} />
              </div>
              <div className="trend-box">
                <div className="trend-box-head">
                  <h4>情绪升级次数</h4>
                  <span className="muted">过去 7 天</span>
                </div>
                <MetricBars points={weeklyReport.meltdown_trend} maxValue={3} />
              </div>
            </div>
          </div>

          <div className="report-section">
            <h4>任务完成情况与效果</h4>
            <div className="task-grid">
              <TaskGroup title="执行稳定" items={weeklyReport.completed_tasks} />
              <TaskGroup title="部分完成" items={weeklyReport.partial_tasks} />
              <TaskGroup title="需要重试" items={weeklyReport.retry_tasks} />
            </div>
          </div>

          <div className="report-section">
            <h4>家长自评摘要</h4>
            <div className="quote-box">{weeklyReport.caregiver_summary}</div>
          </div>

          <div className="report-section">
            <div className="report-section-head">
              <h4>本周有效策略 TOP3</h4>
              <div className="feedback-summary">
                <span className="status-pill">有效 {weeklyReport.feedback_summary.effective_count}</span>
                <span className="status-pill warning">未按预期 {weeklyReport.feedback_summary.not_effective_count}</span>
              </div>
            </div>
            <StrategyList
              items={weeklyReport.strategy_top3}
              states={weeklyReport.feedback_states}
              periodType="weekly"
              periodStart={weeklyReport.week_start}
              feedbackSavingKey={feedbackSavingKey}
              onFeedback={onFeedback}
              positiveLabel="此策略对我有效"
              negativeLabel="未按预期执行"
              positiveValue="effective"
              negativeValue="not_effective"
            />
          </div>

          <div className="report-section">
            <div className="report-section-head">
              <h4>家长下一步行动建议</h4>
              <div className="feedback-summary">
                <span className="status-pill">继续执行 {weeklyReport.feedback_summary.continue_count}</span>
                <span className="status-pill warning">调整计划 {weeklyReport.feedback_summary.adjust_count}</span>
              </div>
            </div>
            <ActionList
              items={weeklyReport.next_actions}
              states={weeklyReport.feedback_states}
              periodType="weekly"
              periodStart={weeklyReport.week_start}
              feedbackSavingKey={feedbackSavingKey}
              onFeedback={onFeedback}
            />
          </div>
        </div>
      ) : null}

      {monthlyReport ? (
        <div className="panel report-card">
          <div className="report-card-header">
            <div>
              <p className="eyebrow">Monthly Review</p>
              <h3>长期跟踪与调整</h3>
              <p className="muted">{formatDateRange(monthlyReport.month_start, monthlyReport.month_end)}</p>
            </div>
            <span className="status-pill">{monthlyReport.history.length} 个月历史</span>
          </div>

          <div className="report-section">
            <h4>本月概览</h4>
            <div className="quote-box">{monthlyReport.overview_summary}</div>
            <div className="report-copy-grid">
              <div className="metric-card">
                <span className="label">压力变化</span>
                <p>{monthlyReport.stress_change_summary}</p>
              </div>
              <div className="metric-card">
                <span className="label">冲突变化</span>
                <p>{monthlyReport.conflict_change_summary}</p>
              </div>
              <div className="metric-card">
                <span className="label">任务完成趋势</span>
                <p>{monthlyReport.task_completion_summary}</p>
              </div>
            </div>
          </div>

          <div className="report-section">
            <h4>长期趋势</h4>
            <TrendCards items={monthlyReport.long_term_trends} />
          </div>

          <div className="report-section">
            <div className="report-section-head">
              <h4>成功案例与高效方法</h4>
              <div className="feedback-summary">
                <span className="status-pill">有效 {monthlyReport.feedback_summary.effective_count}</span>
                <span className="status-pill warning">需调整 {monthlyReport.feedback_summary.not_effective_count}</span>
              </div>
            </div>
            <StrategyList
              items={monthlyReport.successful_methods}
              states={monthlyReport.feedback_states}
              periodType="monthly"
              periodStart={monthlyReport.month_start}
              feedbackSavingKey={feedbackSavingKey}
              onFeedback={onFeedback}
              positiveLabel="继续保留"
              negativeLabel="方法失效了"
              positiveValue="effective"
              negativeValue="not_effective"
            />
          </div>

          <div className="report-section">
            <div className="report-section-head">
              <h4>下一步行动计划</h4>
              <div className="feedback-summary">
                <span className="status-pill">继续执行 {monthlyReport.feedback_summary.continue_count}</span>
                <span className="status-pill warning">调整计划 {monthlyReport.feedback_summary.adjust_count}</span>
              </div>
            </div>
            <ActionList
              items={monthlyReport.next_month_plan}
              states={monthlyReport.feedback_states}
              periodType="monthly"
              periodStart={monthlyReport.month_start}
              feedbackSavingKey={feedbackSavingKey}
              onFeedback={onFeedback}
            />
          </div>

          <div className="report-section">
            <h4>个性化历史趋势</h4>
            <HistoryCards items={monthlyReport.history} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
