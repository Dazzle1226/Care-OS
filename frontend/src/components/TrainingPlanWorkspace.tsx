import { useEffect, useState } from 'react';

import {
  addTrainingSessionEventV3,
  closeTrainingSessionV3,
  generateTrainingPlan,
  getCurrentTrainingPlan,
  getTrainingDomainDetail,
  scheduleTrainingReminder,
  startTrainingSessionV3,
  submitTrainingFeedback
} from '../lib/api';
import { createActionFlowContext, type ActionFlowContext, type CareTab } from '../lib/flow';
import { scheduleScrollWorkspaceToTop } from '../lib/scroll';
import {
  buildCheckinCircles,
  buildProgressMoments,
  buildTrainingPlanEntries,
  computeDomainProgressPercent,
  summarizeCurrentSituation,
  type TrainingPlanEntry
} from '../lib/trainingTracking';
import type {
  AdaptiveSession,
  CoordinationDecision,
  DecisionGraphStageRun,
  DecisionState,
  TrainingAdjustmentLogItem,
  DailyTrainingTask,
  TrainingChildResponse,
  TrainingCompletionStatus,
  TrainingDashboard,
  TrainingDomainDetail,
  TrainingHelpfulness,
  TrainingObstacleTag
} from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
  onNavigate: (tab: CareTab) => void;
  onActionContextChange: (context: ActionFlowContext | null) => void;
}

interface FeedbackDraft {
  completion_status: TrainingCompletionStatus;
  child_response: TrainingChildResponse;
  helpfulness: TrainingHelpfulness;
  obstacle_tag: TrainingObstacleTag;
  notes: string;
}

const DETAIL_HASH_PREFIX = '#training/';

function createDraft(): FeedbackDraft {
  return {
    completion_status: 'partial',
    child_response: 'accepted',
    helpfulness: 'neutral',
    obstacle_tag: 'none',
    notes: ''
  };
}

function formatDateTime(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(
    date.getMinutes()
  ).padStart(2, '0')}`;
}

function formatShortDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  const weekday = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()];
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日 ${weekday}`;
}

function formatMonthDay(value: string) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function inferReviewScenario(value?: string | null) {
  const text = value?.trim() ?? '';
  if (!text) return 'transition';
  if (text.includes('睡')) return 'bedtime';
  if (text.includes('作业') || text.includes('学习')) return 'homework';
  if (text.includes('外出') || text.includes('排队')) return 'outing';
  return 'transition';
}

function formatAdjustmentState(value: unknown) {
  const text = String(value ?? '').trim();
  if (!text) return '未记录';
  if (text in stageLabel) return stageLabel[text as keyof typeof stageLabel];
  if (text in difficultyLabel) return difficultyLabel[text as keyof typeof difficultyLabel];
  return text;
}

function summarizeAdjustmentDelta(item: TrainingAdjustmentLogItem) {
  return {
    stage: `${formatAdjustmentState(item.before_state['stage'])} -> ${formatAdjustmentState(item.after_state['stage'])}`,
    difficulty: `${formatAdjustmentState(item.before_state['difficulty'])} -> ${formatAdjustmentState(item.after_state['difficulty'])}`
  };
}

function readAreaKeyFromHash() {
  if (typeof window === 'undefined') return null;
  const hash = window.location.hash;
  if (!hash.startsWith(DETAIL_HASH_PREFIX)) return null;
  return decodeURIComponent(hash.slice(DETAIL_HASH_PREFIX.length)) || null;
}

function writeAreaKeyToHash(areaKey: string | null, mode: 'push' | 'replace' = 'replace') {
  if (typeof window === 'undefined') return;

  const url = new URL(window.location.href);
  url.hash = areaKey ? `${DETAIL_HASH_PREFIX}${encodeURIComponent(areaKey)}` : '';

  if (mode === 'push') {
    window.history.pushState(window.history.state, '', url);
    return;
  }

  window.history.replaceState(window.history.state, '', url);
}

const stageLabel = {
  stabilize: '稳定期',
  practice: '练习期',
  generalize: '泛化期',
  maintain: '维持期'
} as const;

const difficultyLabel = {
  starter: '起步版',
  build: '推进版',
  advance: '进阶版'
} as const;

const statusLabel = {
  pending: '待开始',
  scheduled: '已提醒',
  done: '已完成',
  partial: '部分完成',
  missed: '未完成'
} as const;

const cooperationLabel = {
  engaged: '很配合',
  accepted: '一般',
  resistant: '很抗拒',
  overloaded: '已过载'
} as const;

const helpfulnessLabel = {
  helpful: '有帮助',
  neutral: '一般',
  not_helpful: '没帮助'
} as const;

const riskLevelLabel = {
  green: '低风险',
  yellow: '需要留意',
  red: '高风险'
} as const;

const overloadLevelLabel = {
  low: '低',
  medium: '中',
  high: '高'
} as const;

const emotionLabel = {
  calm: '平稳',
  fragile: '脆弱',
  escalating: '正在升级',
  meltdown_risk: '接近失控',
  strained: '吃紧',
  anxious: '焦虑',
  overloaded: '过载'
} as const;

const readinessLabel = {
  ready: '今天适合练',
  lighter: '今天先降载练',
  pause: '今天先不练'
} as const;

const readinessClassName = {
  ready: 'review-notice',
  lighter: 'review-notice',
  pause: 'error'
} as const;

const coordinationModeLabel = {
  ready: '按计划练',
  continue: '按计划练',
  lighter: '低负担版',
  handoff: '准备交接',
  blocked: '暂停正式训练',
  pause: '暂停正式训练'
} as const;

const obstacleLabel = {
  none: '无明显困难',
  too_hard: '太难',
  refused: '孩子抗拒',
  parent_overloaded: '家长太累',
  wrong_timing: '时机不对',
  sensory_overload: '感官过载',
  unclear_steps: '步骤不清楚'
} as const;

function readOutputText(output: Record<string, unknown>, key: string) {
  const value = output[key];
  return typeof value === 'string' ? value : '';
}

const quickFeedbackOptions: Array<{
  key: string;
  label: string;
  draft: FeedbackDraft;
}> = [
  {
    key: 'done',
    label: '顺利完成',
    draft: {
      completion_status: 'done',
      child_response: 'engaged',
      helpfulness: 'helpful',
      obstacle_tag: 'none',
      notes: ''
    }
  },
  {
    key: 'partial',
    label: '部分完成',
    draft: {
      completion_status: 'partial',
      child_response: 'accepted',
      helpfulness: 'neutral',
      obstacle_tag: 'too_hard',
      notes: ''
    }
  },
  {
    key: 'missed',
    label: '今天没做',
    draft: {
      completion_status: 'missed',
      child_response: 'resistant',
      helpfulness: 'not_helpful',
      obstacle_tag: 'wrong_timing',
      notes: ''
    }
  }
];

export function TrainingPlanWorkspace({ token, familyId, onNavigate, onActionContextChange }: Props) {
  const [dashboard, setDashboard] = useState<TrainingDashboard | null>(null);
  const [detailCache, setDetailCache] = useState<Record<string, TrainingDomainDetail>>({});
  const [selectedAreaKey, setSelectedAreaKey] = useState<string | null>(null);
  const [activePlanEntryId, setActivePlanEntryId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, FeedbackDraft>>({});
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [detailLoadingKey, setDetailLoadingKey] = useState<string | null>(null);
  const [submittingTaskId, setSubmittingTaskId] = useState<number | null>(null);
  const [remindingTaskId, setRemindingTaskId] = useState<number | null>(null);
  const [trainingSession, setTrainingSession] = useState<AdaptiveSession | null>(null);
  const [trainingDecisionState, setTrainingDecisionState] = useState<DecisionState | null>(null);
  const [trainingCoordination, setTrainingCoordination] = useState<CoordinationDecision | null>(null);
  const [trainingLearningSummary, setTrainingLearningSummary] = useState<string[]>([]);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const selectedDetail = selectedAreaKey ? detailCache[selectedAreaKey] ?? null : null;
  const selectedTask = selectedAreaKey
    ? dashboard?.today_tasks.find((task) => task.area_key === selectedAreaKey) ?? null
    : null;
  const selectedPlanEntries = selectedDetail ? buildTrainingPlanEntries(selectedDetail, selectedTask) : [];
  const activePlanEntry = selectedPlanEntries.find((item) => item.entry_id === activePlanEntryId) ?? null;
  const recentAdaptations = trainingDecisionState?.adaptation_history.slice(-3).reverse() ?? [];

  useEffect(() => {
    let cancelled = false;

    if (!familyId) {
      setDashboard(null);
      setDetailCache({});
      setSelectedAreaKey(null);
      setTrainingSession(null);
      setTrainingDecisionState(null);
      setTrainingCoordination(null);
      setTrainingLearningSummary([]);
      setError('');
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setError('');
    getCurrentTrainingPlan(token, familyId)
      .then((data) => {
        if (cancelled) return;
        setDashboard(data);
        setDetailCache({});
        setTrainingSession(null);
        setTrainingDecisionState(null);
        setTrainingCoordination(null);
        setTrainingLearningSummary([]);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [familyId, token]);

  useEffect(() => {
    const syncWithHash = () => {
      const nextAreaKey = readAreaKeyFromHash();
      setSelectedAreaKey(nextAreaKey);
      if (!nextAreaKey) {
        setActivePlanEntryId(null);
      }
    };

    syncWithHash();
    window.addEventListener('popstate', syncWithHash);
    return () => window.removeEventListener('popstate', syncWithHash);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    return scheduleScrollWorkspaceToTop(document, window);
  }, [selectedAreaKey]);

  useEffect(() => {
    if (!familyId || !selectedAreaKey) return;
    if (detailCache[selectedAreaKey]) return;

    let cancelled = false;
    setDetailLoadingKey(selectedAreaKey);
    getTrainingDomainDetail(token, familyId, selectedAreaKey)
      .then((data) => {
        if (cancelled) return;
        setDetailCache((current) => ({ ...current, [selectedAreaKey]: data }));
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setDetailLoadingKey((current) => (current === selectedAreaKey ? null : current));
      });

    return () => {
      cancelled = true;
    };
  }, [detailCache, familyId, selectedAreaKey, token]);

  useEffect(() => {
    if (!familyId || !dashboard?.priority_domains.length) return;

    let cancelled = false;
    const keys = [...new Set(dashboard.priority_domains.map((item) => item.area_key))];

    Promise.all(
      keys.map(async (areaKey) => {
        const detail = await getTrainingDomainDetail(token, familyId, areaKey);
        return [areaKey, detail] as const;
      })
    )
      .then((entries) => {
        if (cancelled) return;
        setDetailCache((current) => ({
          ...current,
          ...Object.fromEntries(entries)
        }));
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [dashboard, familyId, token]);

  const refreshDashboard = async () => {
    if (!familyId) return;
    setRefreshing(true);
    setError('');
    setNotice('');
    try {
      const data = await generateTrainingPlan(token, { family_id: familyId, extra_context: '' });
      setDashboard(data);
      setDetailCache({});
      if (selectedAreaKey) {
        setDetailLoadingKey(selectedAreaKey);
        const nextDetail = await getTrainingDomainDetail(token, familyId, selectedAreaKey);
        setDetailCache((current) => ({ ...current, [selectedAreaKey]: nextDetail }));
      }
      setNotice('已根据最近情况更新长期训练跟踪。');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRefreshing(false);
      setDetailLoadingKey(null);
    }
  };

  const openDomainDetail = async (areaKey: string) => {
    if (!familyId) return;
    setSelectedAreaKey(areaKey);
    setActivePlanEntryId(null);
    writeAreaKeyToHash(areaKey, 'push');
    if (detailCache[areaKey]) return;

    setDetailLoadingKey(areaKey);
    setError('');
    try {
      const data = await getTrainingDomainDetail(token, familyId, areaKey);
      setDetailCache((current) => ({ ...current, [areaKey]: data }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDetailLoadingKey(null);
    }
  };

  const closeDomainDetail = () => {
    setSelectedAreaKey(null);
    setActivePlanEntryId(null);
    writeAreaKeyToHash(null, 'replace');
  };

  const updateDraft = (taskId: number, patch: Partial<FeedbackDraft>) => {
    setDrafts((current) => ({
      ...current,
      [taskId]: {
        ...(current[taskId] ?? createDraft()),
        ...patch
      }
    }));
  };

  const syncDetailIfNeeded = async (areaKey: string) => {
    if (!familyId) return;
    const data = await getTrainingDomainDetail(token, familyId, areaKey);
    setDetailCache((current) => ({ ...current, [areaKey]: data }));
  };

  const submitTaskFeedback = async (task: DailyTrainingTask, draftOverride?: FeedbackDraft) => {
    if (!familyId) return;
    const draft = draftOverride ?? drafts[task.task_instance_id] ?? createDraft();
    setSubmittingTaskId(task.task_instance_id);
    setError('');
    setNotice('');
    try {
      const response = await submitTrainingFeedback(token, {
        family_id: familyId,
        task_instance_id: task.task_instance_id,
        completion_status: draft.completion_status,
        child_response: draft.child_response,
        helpfulness: draft.helpfulness,
        obstacle_tag: draft.obstacle_tag,
        notes: draft.notes
      });
      setDashboard(response.dashboard);
      setDrafts((current) => ({ ...current, [task.task_instance_id]: createDraft() }));
      setNotice(response.adjustment_summary);
      await syncDetailIfNeeded(task.area_key);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmittingTaskId(null);
    }
  };

  const remindLater = async (task: DailyTrainingTask) => {
    if (!familyId) return;
    setRemindingTaskId(task.task_instance_id);
    setError('');
    setNotice('');
    try {
      const response = await scheduleTrainingReminder(token, {
        family_id: familyId,
        task_instance_id: task.task_instance_id
      });
      setDashboard(response.dashboard);
      setNotice('已为这项训练安排稍后提醒。');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRemindingTaskId(null);
    }
  };

  const startTrainingSession = async () => {
    if (!familyId) return;
    setSessionBusy(true);
    setError('');
    setNotice('');
    try {
      const response = await startTrainingSessionV3(token, {
        family_id: familyId,
        extra_context: '',
        ingestion_ids: []
      });
      setDashboard(response.dashboard);
      setTrainingSession(response.session);
      setTrainingDecisionState(response.decision_state);
      setTrainingCoordination(response.coordination);
      setTrainingLearningSummary([]);
      setNotice('已启动会话式训练支持，系统会跟着今天状态一起调整。');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSessionBusy(false);
    }
  };

  const pushTrainingSessionEvent = async (
    eventKind: 'status_check' | 'request_lighter' | 'no_improvement' | 'caregiver_overloaded',
    rawText: string
  ) => {
    if (!trainingSession) return;
    setSessionBusy(true);
    setError('');
    try {
      const response = await addTrainingSessionEventV3(token, trainingSession.session_id, {
        source_type: 'user_action',
        event_kind: eventKind,
        raw_text: rawText
      });
      setDashboard(response.dashboard);
      setTrainingSession(response.session);
      setTrainingDecisionState(response.decision_state);
      setTrainingCoordination(response.coordination);
      if (response.replanned) {
        setNotice(`训练支持已调整：${response.changed_fields.join(' / ') || '已切换到更适合当前状态的方案'}`);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSessionBusy(false);
    }
  };

  const closeTrainingSession = async (effectiveness: 'helpful' | 'somewhat' | 'not_helpful') => {
    if (!trainingSession) return;
    setSessionBusy(true);
    setError('');
    try {
      const response = await closeTrainingSessionV3(token, trainingSession.session_id, {
        effectiveness,
        notes: ''
      });
      setDashboard(response.dashboard);
      setTrainingSession(response.session);
      setTrainingDecisionState(response.decision_state);
      setTrainingLearningSummary(response.learning_summary);
      setNotice('训练支持会话已结束，系统已记住这次更有效的减负方式。');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSessionBusy(false);
    }
  };

  const jumpToReview = (task?: DailyTrainingTask | null) => {
    const seedTask = task ?? dashboard?.today_tasks.find((item) => item.highlight) ?? dashboard?.today_tasks[0] ?? null;
    const seedDetail =
      (seedTask ? detailCache[seedTask.area_key] : null) ?? (selectedAreaKey ? detailCache[selectedAreaKey] : null);

    if (seedTask || seedDetail) {
      onActionContextChange(
        createActionFlowContext({
          source: 'plan',
          scenario: inferReviewScenario(seedTask?.training_scene ?? seedDetail?.title),
          sourceScenario: seedTask?.training_scene ?? seedDetail?.title,
          title: seedTask?.title ?? `${seedDetail?.title ?? '长期训练'}复盘`,
          summary: seedTask?.today_goal ?? seedDetail?.short_term_goal.target ?? dashboard?.summary.summary_text ?? '记录本次训练结果',
          suggestedTriggers: seedDetail?.current_risks ?? [],
          suggestedFollowup: seedTask?.coaching_tip ?? seedDetail?.training_principles[0] ?? ''
        })
      );
    } else {
      onActionContextChange(null);
    }

    onNavigate('review');
  };

  const renderFeedbackPanel = (task: DailyTrainingTask) => {
    const draft = drafts[task.task_instance_id] ?? createDraft();
    const isExpanded = activeTaskId === task.task_instance_id;
    const isSubmitting = submittingTaskId === task.task_instance_id;

    if (!isExpanded) return null;

    return (
      <div className="training-feedback-shell">
        <div className="training-quick-actions">
          {quickFeedbackOptions.map((option) => (
            <button
              key={option.key}
              className="btn secondary"
              type="button"
              disabled={isSubmitting}
              onClick={() => submitTaskFeedback(task, option.draft)}
            >
              {isSubmitting ? '提交中...' : option.label}
            </button>
          ))}
        </div>

        <div className="training-feedback-grid">
          <label>
            <span className="label">今天是否完成</span>
            <select
              className="input"
              value={draft.completion_status}
              onChange={(e) =>
                updateDraft(task.task_instance_id, {
                  completion_status: e.target.value as TrainingCompletionStatus
                })
              }
            >
              <option value="done">完成</option>
              <option value="partial">部分完成</option>
              <option value="missed">未完成</option>
            </select>
          </label>

          <label>
            <span className="label">孩子配合程度</span>
            <select
              className="input"
              value={draft.child_response}
              onChange={(e) =>
                updateDraft(task.task_instance_id, {
                  child_response: e.target.value as TrainingChildResponse
                })
              }
            >
              <option value="engaged">很配合</option>
              <option value="accepted">一般</option>
              <option value="resistant">很抗拒</option>
              <option value="overloaded">已过载</option>
            </select>
          </label>

          <label>
            <span className="label">训练效果</span>
            <select
              className="input"
              value={draft.helpfulness}
              onChange={(e) =>
                updateDraft(task.task_instance_id, {
                  helpfulness: e.target.value as TrainingHelpfulness
                })
              }
            >
              <option value="helpful">有帮助</option>
              <option value="neutral">一般</option>
              <option value="not_helpful">没帮助</option>
            </select>
          </label>

          <label>
            <span className="label">最大的困难</span>
            <select
              className="input"
              value={draft.obstacle_tag}
              onChange={(e) =>
                updateDraft(task.task_instance_id, {
                  obstacle_tag: e.target.value as TrainingObstacleTag
                })
              }
            >
              <option value="none">无明显困难</option>
              <option value="too_hard">太难</option>
              <option value="refused">孩子抗拒</option>
              <option value="parent_overloaded">家长太累</option>
              <option value="wrong_timing">时机不对</option>
              <option value="sensory_overload">感官过载</option>
              <option value="unclear_steps">步骤不清楚</option>
            </select>
          </label>

          <label className="full-span">
            <span className="label">备注（可选）</span>
            <textarea
              className="input textarea"
              rows={3}
              value={draft.notes}
              onChange={(e) =>
                updateDraft(task.task_instance_id, {
                  notes: e.target.value
                })
              }
              placeholder="例如：晚饭后更配合，但第二步一加就烦躁。"
            />
          </label>
        </div>

        <div className="training-task-actions">
          <button className="btn" type="button" disabled={isSubmitting} onClick={() => submitTaskFeedback(task)}>
            {isSubmitting ? '提交中...' : '提交反馈'}
          </button>
          <button className="btn secondary" type="button" onClick={() => jumpToReview(task)}>
            去复盘页补完整记录
          </button>
        </div>
      </div>
    );
  };

  if (!familyId) {
    return <div className="panel">请先在【家庭】页完成档案建立，再生成长期训练计划。</div>;
  }

  if (loading) {
    return <div className="panel">正在加载长期训练跟踪...</div>;
  }

  if (selectedAreaKey) {
    const progressMoments = selectedDetail ? buildProgressMoments(selectedDetail) : [];

    return (
      <div className="grid">
        <section className="panel training-detail-shell training-route-shell">
          <div className="focus-header">
            <div>
              <p className="eyebrow">长期训练跟踪 / 能力详情</p>
              <h3>{selectedDetail?.title ?? '正在读取能力详情'}</h3>
              <p className="muted">这是独立详情视图，可以直接返回总览，不会把内容继续堆在当前列表里。</p>
            </div>
            <button className="btn secondary" type="button" onClick={closeDomainDetail}>
              返回长期训练跟踪
            </button>
          </div>

          {detailLoadingKey === selectedAreaKey || !selectedDetail ? (
            <p className="muted">正在读取能力详情...</p>
          ) : (
            <>
              <div className="training-detail-summary-grid">
                <article className="training-detail-summary-card training-detail-hero-card">
                  <p className="eyebrow">能力说明</p>
                  <h4>{selectedDetail.title}</h4>
                  <p>{selectedDetail.importance_summary}</p>
                  <div className="training-pill-row">
                    <span className="training-pill strong">阶段：{stageLabel[selectedDetail.current_stage]}</span>
                    <span className="training-pill">难度：{difficultyLabel[selectedDetail.current_difficulty]}</span>
                    <span className="training-pill">
                      当前进度 {computeDomainProgressPercent(
                        dashboard?.priority_domains.find((item) => item.area_key === selectedAreaKey) ?? {
                          area_key: selectedDetail.area_key,
                          title: selectedDetail.title,
                          priority_label: 'high',
                          priority_score: 0,
                          recommended_reason: '',
                          current_stage: selectedDetail.current_stage,
                          current_difficulty: selectedDetail.current_difficulty,
                          weekly_sessions_count: selectedDetail.progress.weekly_sessions_count,
                          has_today_task: Boolean(selectedTask),
                          current_status: '',
                          improvement_value: '',
                          coordination_hint: ''
                        },
                        selectedDetail
                      )}
                      %
                    </span>
                  </div>
                </article>

                <article className="training-detail-summary-card">
                  <p className="eyebrow">当前情况与训练目标</p>
                  <p>{summarizeCurrentSituation(selectedDetail)}</p>
                  <div className="training-goal-stack">
                    <div className="training-goal-card">
                      <strong>{selectedDetail.short_term_goal.title}</strong>
                      <p>{selectedDetail.short_term_goal.target}</p>
                      <p className="muted">预期效果：{selectedDetail.short_term_goal.success_marker}</p>
                    </div>
                    <div className="training-goal-card">
                      <strong>{selectedDetail.medium_term_goal.title}</strong>
                      <p>{selectedDetail.medium_term_goal.target}</p>
                      <p className="muted">预期效果：{selectedDetail.medium_term_goal.success_marker}</p>
                    </div>
                  </div>
                </article>
              </div>

              <div className="training-detail-grid">
                <section className="panel">
                  <p className="eyebrow">为什么现在优先练</p>
                  <ul className="list compact-list">
                    {selectedDetail.reason_for_priority.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>

                  <p className="label">系统当前重点关注</p>
                  <div className="training-pill-row">
                    {selectedDetail.current_risks.map((item) => (
                      <span key={item} className="training-pill strong">
                        {item}
                      </span>
                    ))}
                  </div>

                  <p className="label">当前家长最常遇到的卡点</p>
                  <div className="training-pill-row">
                    {selectedDetail.related_daily_challenges.map((item) => (
                      <span key={item} className="training-pill">
                        {item}
                      </span>
                    ))}
                  </div>

                  <p className="label">家长执行原则</p>
                  <ol className="list compact-list">
                    {selectedDetail.parent_steps.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ol>
                </section>

                <section className="panel">
                  <p className="eyebrow">进步动态</p>
                  {progressMoments.length ? (
                    <>
                      <div className="training-momentum-row" aria-label="进步动态">
                        {progressMoments.map((item, index) => (
                          <article key={item.point_id} className="training-momentum-card">
                            <div className="training-momentum-top">
                              <span className={`training-history-status ${item.completion_status}`}>
                                {statusLabel[item.completion_status]}
                              </span>
                              <strong>{item.label}</strong>
                            </div>
                            <div className="training-momentum-track">
                              <div className="training-momentum-fill" style={{ width: `${item.effect_score}%` }} />
                            </div>
                            <div className="training-momentum-metrics">
                              <span>效果 {item.effect_score}%</span>
                              <span>家长把握 {item.confidence}%</span>
                            </div>
                            <p className="muted">{item.summary}</p>
                            {index < progressMoments.length - 1 ? <span className="training-momentum-link" aria-hidden="true" /> : null}
                          </article>
                        ))}
                      </div>
                      <p className="muted">每次家长提交训练反馈后，这里会自动刷新，帮助你看到这个能力点是不是在稳定进步。</p>
                    </>
                  ) : (
                    <p className="muted">还没有足够反馈，先完成 1-2 次训练并提供反馈，这里就会开始显示动态趋势。</p>
                  )}

                  <div className="training-detail-progress-board">
                    <div className="training-kpi-card">
                      <div className="training-kpi-top">
                        <span>本周训练次数</span>
                        <strong>{selectedDetail.progress.weekly_sessions_count}</strong>
                      </div>
                    </div>
                    <div className="training-kpi-card">
                      <div className="training-kpi-top">
                        <span>累计完成次数</span>
                        <strong>{selectedDetail.progress.total_completed_count}</strong>
                      </div>
                    </div>
                    <div className="training-kpi-card">
                      <div className="training-kpi-top">
                        <span>最近完成率</span>
                        <strong>{selectedDetail.progress.recent_completion_rate}%</strong>
                      </div>
                    </div>
                    <div className="training-kpi-card">
                      <div className="training-kpi-top">
                        <span>最近有效率</span>
                        <strong>{selectedDetail.progress.recent_effective_rate}%</strong>
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              <div className="training-detail-grid">
                <section className="panel">
                  <div className="training-section-head">
                    <div>
                      <p className="eyebrow">训练计划</p>
                      <h4>未来两周建议安排</h4>
                    </div>
                    <span className="training-pill strong">点日期查看具体训练内容</span>
                  </div>
                  <div className="training-schedule-list">
                    {selectedPlanEntries.map((entry) => (
                      <button
                        key={entry.entry_id}
                        className={`training-schedule-item ${entry.source === 'today_task' ? 'today' : ''}`}
                        type="button"
                        onClick={() => setActivePlanEntryId(entry.entry_id)}
                      >
                        <div className="training-schedule-date">
                          <strong>{formatMonthDay(entry.date)}</strong>
                          <span>{entry.source === 'today_task' ? '今日训练' : '建议训练'}</span>
                        </div>
                        <div className="training-schedule-copy">
                          <strong>{entry.title}</strong>
                          <p>{entry.focus}</p>
                          <p className="muted">预期达到：{entry.expected_effect}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </section>

                <section className="panel">
                  <p className="eyebrow">补充信息</p>
                  <div className="training-detail-stack">
                    <div>
                      <p className="label">建议训练场景</p>
                      <div className="training-pill-row">
                        {selectedDetail.suggested_scenarios.map((item) => (
                          <span key={item} className="training-pill">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="label">家长话术示例</p>
                      <div className="quote-stack">
                        {selectedDetail.script_examples.map((item) => (
                          <blockquote key={item} className="quote-box">
                            “{item}”
                          </blockquote>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="label">孩子状态不对时的降级方式</p>
                      <ul className="list compact-list">
                        {selectedDetail.fallback_options.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="label">注意事项</p>
                      <ul className="list compact-list">
                        {selectedDetail.cautions.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </section>
              </div>

              <div className="training-detail-grid">
                <section className="panel">
                  <p className="eyebrow">系统学到了什么</p>
                  {selectedDetail.adjustment_logs.length ? (
                    <div className="training-history-grid balanced-card-grid cols-3">
                      {selectedDetail.adjustment_logs.slice(0, 3).map((item) => {
                        const delta = summarizeAdjustmentDelta(item);
                        return (
                          <article key={item.adjustment_id} className="training-history-card">
                            <strong>{item.title}</strong>
                            <p>{item.summary}</p>
                            <div className="training-pill-row">
                              <span className="training-pill">阶段：{delta.stage}</span>
                              <span className="training-pill">难度：{delta.difficulty}</span>
                            </div>
                            <p className="muted">
                              触发：{obstacleLabel[item.trigger as keyof typeof obstacleLabel] ?? item.trigger} · {formatDateTime(item.created_at)}
                            </p>
                          </article>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="muted">还没有形成自动调整记录。完成 1-2 次训练反馈后，这里会显示系统如何改变阶段和难度。</p>
                  )}
                </section>

                <section className="panel">
                  <p className="eyebrow">最近训练反馈</p>
                  {selectedDetail.recent_feedbacks.length ? (
                    <div className="training-history-grid balanced-card-grid cols-3">
                      {selectedDetail.recent_feedbacks.slice(0, 3).map((item) => (
                        <article key={item.feedback_id} className="training-history-card">
                          <strong>{item.task_title}</strong>
                          <div className="training-pill-row">
                            <span className={`training-history-status ${item.completion_status}`}>
                              {statusLabel[item.completion_status]}
                            </span>
                            <span className="training-pill">孩子：{cooperationLabel[item.child_response]}</span>
                            <span className="training-pill">效果：{helpfulnessLabel[item.helpfulness]}</span>
                          </div>
                          <p className="muted">
                            障碍：{obstacleLabel[item.obstacle_tag]} · 家长把握 {Math.round(item.parent_confidence * 10)}%
                          </p>
                          {item.notes ? <p>{item.notes}</p> : <p className="muted">这次没有补充备注。</p>}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="muted">还没有训练反馈。提交今天的训练结果后，这里会开始累计家庭自己的学习证据。</p>
                  )}
                </section>
              </div>
            </>
          )}
        </section>

        {activePlanEntry ? (
          <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="training-plan-entry-title">
            <div className="modal-backdrop" onClick={() => setActivePlanEntryId(null)} />
            <div className="modal-card modal-card-fixed-close training-plan-modal">
              <button
                className="icon-btn modal-close-fixed"
                type="button"
                onClick={() => setActivePlanEntryId(null)}
                aria-label="关闭训练计划详情"
              >
                ×
              </button>

              <div className="modal-scroll-area">
                <div className="training-plan-modal-shell">
                  <div className="focus-header">
                    <div>
                      <p className="eyebrow">训练日期详情</p>
                      <h3 id="training-plan-entry-title">{activePlanEntry.title}</h3>
                      <p className="muted">{formatShortDate(activePlanEntry.date)}</p>
                    </div>
                    <span className="training-pill strong">{activePlanEntry.training_scene}</span>
                  </div>

                  <article className="training-goal-card">
                    <strong>今天重点</strong>
                    <p>{activePlanEntry.focus}</p>
                    <p className="muted">预期效果：{activePlanEntry.expected_effect}</p>
                  </article>

                  <div className="training-detail-stack">
                    <div>
                      <p className="label">家长怎么做</p>
                      <ol className="list compact-list">
                        {activePlanEntry.steps.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ol>
                    </div>
                    <div>
                      <p className="label">建议话术</p>
                      <blockquote className="quote-box">“{activePlanEntry.parent_script}”</blockquote>
                    </div>
                    {activePlanEntry.materials.length ? (
                      <div>
                        <p className="label">准备物</p>
                        <div className="training-pill-row">
                          {activePlanEntry.materials.map((item) => (
                            <span key={item} className="training-pill">
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <div>
                      <p className="label">如果抗拒</p>
                      <p>{activePlanEntry.fallback_plan}</p>
                      <p className="muted">执行提醒：{activePlanEntry.coaching_tip}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {error ? <div className="panel error">{error}</div> : null}
      </div>
    );
  }

  const circles = dashboard ? buildCheckinCircles(dashboard.progress_overview.recent_trend) : [];

  return (
    <div className="grid">
      {notice ? <div className="panel review-notice">{notice}</div> : null}
      {dashboard?.safety_alert ? <div className="panel error">{dashboard.safety_alert}</div> : null}
      {dashboard ? (
        <div className={`panel ${readinessClassName[dashboard.summary.readiness_status]}`}>
          <p className="eyebrow">训练协调判断</p>
          <h3>{readinessLabel[dashboard.summary.readiness_status]}</h3>
          <p>{dashboard.summary.readiness_reason}</p>
          <p className="muted">现在建议：{dashboard.summary.recommended_action}</p>
        </div>
      ) : null}
      {dashboard ? (
        <>
          <section className="panel training-summary-panel">
            <div className="training-summary-header">
              <div>
                <p className="eyebrow">当前优先能力</p>
                <h3>最需要提升的 3 项能力</h3>
                <p>{dashboard.summary.summary_text}</p>
              </div>
            </div>

            <div className="training-priority-grid training-priority-grid-spotlight balanced-card-grid cols-3">
              {dashboard.priority_domains.map((item, index) => {
                const detail = detailCache[item.area_key];
                const progressPercent = computeDomainProgressPercent(item, detail);

                return (
                  <article key={item.area_key} className={`training-priority-card training-priority-spotlight rank-${index + 1}`}>
                    <div className="training-card-top">
                      <div>
                        <p className="eyebrow">优先能力 {index + 1}</p>
                        <strong>{item.title}</strong>
                        <p className="muted">{item.priority_label === 'high' ? '高优先级' : '中优先级'}</p>
                      </div>
                      <span className="score-badge">{item.priority_score}</span>
                    </div>

                    <p>{item.recommended_reason}</p>
                    {item.coordination_hint ? <p className="muted">协调提示：{item.coordination_hint}</p> : null}

                    <div className="training-pill-row">
                      <span className="training-pill">阶段：{stageLabel[item.current_stage]}</span>
                      <span className="training-pill">难度：{difficultyLabel[item.current_difficulty]}</span>
                      <span className="training-pill">本周 {item.weekly_sessions_count} 次</span>
                    </div>

                    <div className="training-priority-metric">
                      <div className="training-priority-meter-top">
                        <span>当前进度</span>
                        <strong>{progressPercent}%</strong>
                      </div>
                      <div className="progress-track">
                        <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
                      </div>
                    </div>

                    <p className="muted">{detail ? summarizeCurrentSituation(detail) : item.improvement_value}</p>

                    <button className="btn secondary" type="button" onClick={() => openDomainDetail(item.area_key)}>
                      查看详情
                    </button>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="panel training-dashboard-panel training-progress-dashboard">
            <div className="training-section-head">
              <div>
                <p className="eyebrow">当前进度仪表盘</p>
                <h3>看每项能力目前训练到哪里了</h3>
              </div>
            </div>

            <div className="training-dashboard-grid training-dashboard-grid-extended">
              <div className="training-progress-list">
                {dashboard.priority_domains.map((item) => {
                  const detail = detailCache[item.area_key];
                  const progressPercent = computeDomainProgressPercent(item, detail);
                  return (
                    <article key={`progress-${item.area_key}`} className="progress-card training-progress-row-card">
                      <div className="progress-card-top">
                        <div>
                          <strong>{item.title}</strong>
                          <p className="muted">
                            {detail ? stageLabel[detail.progress.current_stage] : stageLabel[item.current_stage]} ·{' '}
                            {detail ? difficultyLabel[detail.progress.current_difficulty] : difficultyLabel[item.current_difficulty]}
                          </p>
                        </div>
                        <span className="training-pill strong">{progressPercent}%</span>
                      </div>
                      <div className="progress-track">
                        <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
                      </div>
                      <div className="training-progress-meta">
                        <span>本周 {detail?.progress.weekly_sessions_count ?? item.weekly_sessions_count} 次训练</span>
                        <span>最近完成率 {detail?.progress.recent_completion_rate ?? Math.max(progressPercent - 12, 0)}%</span>
                        <span>最近有效率 {detail?.progress.recent_effective_rate ?? Math.max(progressPercent - 8, 0)}%</span>
                      </div>
                    </article>
                  );
                })}
              </div>

              <aside className="training-streak-panel">
                <div className="training-kpi-grid training-kpi-grid-wide">
                  <article className="training-kpi-card training-kpi-card-accent">
                    <div className="training-kpi-top">
                      <span>连续打卡</span>
                      <strong>{dashboard.progress_overview.streak_days} 天</strong>
                    </div>
                  </article>
                  <article className="training-kpi-card">
                    <div className="training-kpi-top">
                      <span>最近 7 天完成率</span>
                      <strong>{dashboard.progress_overview.seven_day_completion_rate}%</strong>
                    </div>
                  </article>
                  <article className="training-kpi-card">
                    <div className="training-kpi-top">
                      <span>本周完成训练</span>
                      <strong>{dashboard.progress_overview.weekly_completion_count} 次</strong>
                    </div>
                  </article>
                </div>

                <div className="training-checkin-calendar">
                  <div className="training-checkin-head">
                    <strong>最近训练打卡</strong>
                    <span className="muted">每有一次完成，就会把当天圆点点亮</span>
                  </div>
                  <div className="training-checkin-circles">
                    {circles.map((item) => (
                      <div key={item.circle_id} className="training-checkin-circle-wrap">
                        <span className={`training-checkin-circle ${item.completed ? 'done' : ''}`} />
                        <strong>{item.label}</strong>
                        <span className="muted">{item.completion_rate}%</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="training-status-note">
                  <strong>系统识别到的当前有效方法</strong>
                  <p>{dashboard.progress_overview.best_method_summary}</p>
                </div>

                {dashboard.method_insights.length ? (
                  <div className="training-detail-stack">
                    <p className="label">最近学到的有效做法</p>
                    <div className="training-history-grid balanced-card-grid cols-3">
                      {dashboard.method_insights.map((item) => (
                        <article key={item.title} className="training-history-card">
                          <strong>{item.title}</strong>
                          <p>{item.summary}</p>
                          <p className="muted">
                            家庭内证据 {item.evidence_count} 次 · 有效率 {item.effectiveness_score}%
                          </p>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}
              </aside>
            </div>
          </section>

          <section className="panel">
            <div className="training-section-head">
              <div>
                <p className="eyebrow">今日训练内容</p>
                <h3>今天直接照着做</h3>
                <p className="muted">这里直接展开每天任务的详细版本，家长不用再进详情页找今天该怎么做。</p>
              </div>
            </div>
            {dashboard.today_tasks.length ? (
              <div className="training-today-stack">
                {dashboard.today_tasks.map((task) => {
                  const isExpanded = activeTaskId === task.task_instance_id;
                  const isReminding = remindingTaskId === task.task_instance_id;

                  return (
                    <article key={task.task_instance_id} className={`training-task-card training-task-card-wide ${task.highlight ? 'highlight' : ''}`}>
                      <div className="training-card-top">
                        <div>
                          <p className="eyebrow">{task.area_title}</p>
                          <strong>{task.title}</strong>
                          <p className="muted">
                            {task.schedule_hint} · {task.duration_minutes} 分钟 · {difficultyLabel[task.difficulty]}
                          </p>
                        </div>
                        <span className={`training-history-status ${task.status}`}>{statusLabel[task.status]}</span>
                      </div>

                      <div className="training-task-main-grid">
                        <div className="training-detail-stack">
                          <article className="training-goal-card">
                            <strong>今天的目标</strong>
                            <p>{task.today_goal}</p>
                            <p className="muted">
                              {coordinationModeLabel[task.coordination_mode]}：{task.why_today || dashboard.summary.readiness_reason}
                            </p>
                          </article>

                          <div className="training-meta-block">
                            <p className="label">训练步骤</p>
                            <ol className="list compact-list">
                              {task.steps.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ol>
                          </div>

                          <div className="training-meta-block">
                            <p className="label">家长怎么说</p>
                            <blockquote className="quote-box">“{task.parent_script}”</blockquote>
                          </div>
                        </div>

                        <div className="training-detail-stack">
                          <div className="training-pill-row">
                            <span className="training-pill">训练场景：{task.training_scene}</span>
                            <span className="training-pill strong">{coordinationModeLabel[task.coordination_mode]}</span>
                            {task.reminder_status !== 'none' ? (
                              <span className="training-pill strong">
                                {task.reminder_status === 'due' ? '提醒已到' : '已提醒'}
                                {task.reminder_at ? ` · ${formatDateTime(task.reminder_at)}` : ''}
                              </span>
                            ) : null}
                          </div>

                          <div className="training-meta-block">
                            <p className="label">准备物</p>
                            <div className="training-pill-row">
                              {task.materials.map((item) => (
                                <span key={item} className="training-pill">
                                  {item}
                                </span>
                              ))}
                            </div>
                          </div>

                          <article className="training-goal-card">
                            <strong>如果孩子抗拒</strong>
                            <p>{task.fallback_plan}</p>
                            <p className="muted">执行提示：{task.coaching_tip}</p>
                          </article>
                        </div>
                      </div>

                      <div className="focus-actions">
                        <button className="btn" type="button" onClick={() => setActiveTaskId(task.task_instance_id)}>
                          开始训练
                        </button>
                        <button className="btn secondary" type="button" onClick={() => openDomainDetail(task.area_key)}>
                          查看所属能力详情
                        </button>
                        <button
                          className="btn secondary"
                          type="button"
                          onClick={() => remindLater(task)}
                          disabled={isReminding}
                        >
                          {isReminding ? '设置中...' : '稍后提醒'}
                        </button>
                        <button
                          className="btn secondary"
                          type="button"
                          onClick={() => setActiveTaskId(isExpanded ? null : task.task_instance_id)}
                        >
                          {isExpanded ? '收起反馈入口' : '提供反馈'}
                        </button>
                      </div>

                      {renderFeedbackPanel(task)}
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="training-goal-card">
                <strong>{readinessLabel[dashboard.summary.readiness_status]}</strong>
                <p>{dashboard.summary.readiness_reason}</p>
                <p className="muted">现在建议：{dashboard.summary.recommended_action}</p>
              </div>
            )}
          </section>

          <section className="panel training-followup-panel training-followup-strip">
            <div className="focus-header">
              <div>
                <p className="eyebrow">下一步</p>
                <h3>训练结束后可以继续这两件事</h3>
              </div>
            </div>
            <div className="training-followup-grid">
              <article className="training-followup-card">
                <p className="eyebrow">去复盘</p>
                <h4>把这次结果记下来</h4>
                <p>补孩子反应、触发点和下次保留的一件事，系统会据此刷新能力评估。</p>
                <button className="btn secondary" type="button" onClick={() => jumpToReview()}>
                  跳转复盘
                </button>
              </article>

              <article className="training-followup-card">
                <p className="eyebrow">重新评估计划</p>
                <h4>根据最新情况刷新长期安排</h4>
                <p>如果这几天状态明显变了，直接补充变化后重新评估，计划会跟着更新。</p>
                <button className="btn secondary" type="button" onClick={refreshDashboard} disabled={refreshing}>
                  {refreshing ? '重新评估中...' : '重新评估'}
                </button>
              </article>
            </div>
          </section>

          <section className="panel">
            <div className="training-section-head">
              <div>
                <p className="eyebrow">会话式训练支持</p>
                <h3>让训练跟着今天的状态一起调整</h3>
                <p className="muted">这不是重新生成一整页计划，而是保留骨架、按你和孩子的状态做差量调整。</p>
              </div>
            </div>

            {trainingSession && trainingDecisionState && trainingCoordination ? (
              <div className="training-detail-stack">
                <article className="training-goal-card">
                  <strong>
                    当前模式：{coordinationModeLabel[trainingCoordination.active_mode === 'blocked' ? 'pause' : trainingCoordination.active_mode]}
                  </strong>
                  <p>{trainingCoordination.summary}</p>
                  <p className="muted">
                    会话版本 {trainingSession.current_state_version} · {trainingSession.next_check_in_hint}
                  </p>
                </article>

                <div className="training-task-main-grid">
                  <article className="training-goal-card">
                    <strong>现在先做这一步</strong>
                    <p>{trainingCoordination.now_step}</p>
                    <p className="muted">为什么这样调：{trainingCoordination.decision_reason}</p>
                  </article>

                  <article className="training-goal-card">
                    <strong>现在怎么说</strong>
                    <blockquote className="quote-box">“{trainingCoordination.now_script}”</blockquote>
                    <p className="muted">如果还不行：{trainingCoordination.next_if_not_working}</p>
                  </article>
                </div>

                {trainingDecisionState.used_memory_signals.length ? (
                  <div className="training-pill-row">
                    {trainingDecisionState.used_memory_signals.map((item) => (
                      <span key={item} className="training-pill">
                        {item}
                      </span>
                    ))}
                  </div>
                ) : null}

                <div className="training-task-main-grid">
                  <article className="training-goal-card">
                    <strong>系统当前判断</strong>
                    <ul className="list compact-list">
                      <li>
                        风险：
                        {trainingDecisionState.risk_assessment
                          ? riskLevelLabel[trainingDecisionState.risk_assessment.risk_level]
                          : '未触发单独风险判断'}
                      </li>
                      <li>
                        孩子状态：
                        {trainingDecisionState.emotion_assessment
                          ? `${emotionLabel[trainingDecisionState.emotion_assessment.child_emotion]} / 过载 ${overloadLevelLabel[trainingDecisionState.emotion_assessment.child_overload_level]}`
                          : '未标注'}
                      </li>
                      <li>
                        家长状态：
                        {trainingDecisionState.emotion_assessment
                          ? `${emotionLabel[trainingDecisionState.emotion_assessment.caregiver_emotion]} / 过载 ${overloadLevelLabel[trainingDecisionState.emotion_assessment.caregiver_overload_level]}`
                          : '未标注'}
                      </li>
                    </ul>
                  </article>

                  <article className="training-goal-card">
                    <strong>为什么今天这样安排</strong>
                    <ul className="list compact-list">
                      {trainingCoordination.weight_summary.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                      {!trainingCoordination.weight_summary.length ? <li>{trainingCoordination.decision_reason}</li> : null}
                    </ul>
                    {trainingCoordination.replan_triggers.length ? (
                      <p className="muted">下次触发重规划：{trainingCoordination.replan_triggers.join('、')}</p>
                    ) : null}
                  </article>
                </div>

                {trainingDecisionState.context_signals.length ? (
                  <article className="training-goal-card">
                    <strong>这次参考了哪些现场信号</strong>
                    <div className="training-pill-row">
                      {trainingDecisionState.context_signals.slice(0, 6).map((item) => (
                        <span key={`${item.signal_key}-${item.signal_value}`} className="training-pill">
                          {item.signal_label}：{item.signal_value}
                        </span>
                      ))}
                    </div>
                  </article>
                ) : null}

                {recentAdaptations.length ? (
                  <article className="training-goal-card">
                    <strong>最近几次为什么会调整</strong>
                    <ul className="list compact-list">
                      {recentAdaptations.map((item, index) => (
                        <li key={`${item}-${index}`}>{item}</li>
                      ))}
                    </ul>
                  </article>
                ) : null}

                <div className="focus-actions">
                  <button className="btn" type="button" disabled={sessionBusy} onClick={() => pushTrainingSessionEvent('status_check', '先按这个方案继续。')}>
                    {sessionBusy ? '处理中...' : '继续这个方案'}
                  </button>
                  <button
                    className="btn secondary"
                    type="button"
                    disabled={sessionBusy}
                    onClick={() => pushTrainingSessionEvent('request_lighter', '今天想再轻一点。')}
                  >
                    换更轻的
                  </button>
                  <button
                    className="btn secondary"
                    type="button"
                    disabled={sessionBusy}
                    onClick={() => pushTrainingSessionEvent('no_improvement', '照着做了，但现在还是没改善。')}
                  >
                    状态没改善
                  </button>
                  <button
                    className="btn secondary"
                    type="button"
                    disabled={sessionBusy}
                    onClick={() => pushTrainingSessionEvent('caregiver_overloaded', '我现在更累了，想减负。')}
                  >
                    我太累了
                  </button>
                </div>

                <div className="training-quick-actions">
                  <button className="btn secondary" type="button" disabled={sessionBusy} onClick={() => closeTrainingSession('helpful')}>
                    这次有帮助
                  </button>
                  <button className="btn secondary" type="button" disabled={sessionBusy} onClick={() => closeTrainingSession('somewhat')}>
                    一般
                  </button>
                  <button className="btn secondary" type="button" disabled={sessionBusy} onClick={() => closeTrainingSession('not_helpful')}>
                    没帮助
                  </button>
                </div>

                {trainingLearningSummary.length ? (
                  <article className="training-goal-card">
                    <strong>这次学到了什么</strong>
                    <ul className="list compact-list">
                      {trainingLearningSummary.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </article>
                ) : null}
              </div>
            ) : (
              <div className="focus-actions">
                <button className="btn" type="button" disabled={sessionBusy} onClick={startTrainingSession}>
                  {sessionBusy ? '启动中...' : '启动会话式训练支持'}
                </button>
              </div>
            )}
          </section>

          <section className="panel">
            <p className="eyebrow">动态调整记录</p>
            {dashboard.recent_adjustments.length ? (
              <div className="training-history-grid balanced-card-grid cols-3">
                {dashboard.recent_adjustments.map((item) => (
                  <article key={item.adjustment_id} className="training-history-card">
                    <strong>{item.title}</strong>
                    <p>{item.summary}</p>
                    <div className="training-pill-row">
                      <span className="training-pill">阶段：{summarizeAdjustmentDelta(item).stage}</span>
                      <span className="training-pill">难度：{summarizeAdjustmentDelta(item).difficulty}</span>
                    </div>
                    <p className="muted">
                      触发：{obstacleLabel[item.trigger as keyof typeof obstacleLabel] ?? item.trigger} · {formatDateTime(item.created_at)}
                    </p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">还没有调整记录，系统会在训练反馈积累后开始调优。</p>
            )}
          </section>
        </>
      ) : null}

      {error ? <div className="panel error">{error}</div> : null}
    </div>
  );
}
