import { useEffect, useRef, useState } from 'react';

import { CheckinCard } from '../components/CheckinCard';
import { MicroRespiteModal } from '../components/MicroRespiteModal';
import { RiskLight } from '../components/RiskLight';
import { createActionFlowContext, type ActionFlowContext, type CareTab } from '../lib/flow';
import { getTodayCheckin, postCheckin } from '../lib/api';
import { buildCheckinPayload, type CheckinFormPayload } from '../lib/checkinPayload';
import { sanitizeDisplayText } from '../lib/displayText';
import { createRequestGuard } from '../lib/requestGuard';
import { getHomeActionSuggestions, getHomeReminderCards } from '../lib/todayFocus';
import type { CheckinResponse, CheckinTodayStatus } from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
  onNavigate: (tab: CareTab) => void;
  onActionContextChange: (context: ActionFlowContext | null) => void;
}

function getLocalDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function buildDismissKey(familyId: number | null, date: string) {
  return familyId ? `care_os_daily_checkin_dismissed_${familyId}_${date}` : '';
}

function toTodayStatus(familyId: number, data: CheckinResponse): CheckinTodayStatus {
  return {
    family_id: familyId,
    date: data.checkin.date,
    needs_checkin: false,
    checkin: data.checkin,
    risk: data.risk,
    today_one_thing: sanitizeDisplayText(data.today_one_thing),
    action_plan: {
      ...data.action_plan,
      headline: sanitizeDisplayText(data.action_plan.headline),
      summary: sanitizeDisplayText(data.action_plan.summary),
      reminders: data.action_plan.reminders.map((item) => ({
        eyebrow: sanitizeDisplayText(item.eyebrow),
        title: sanitizeDisplayText(item.title),
        body: sanitizeDisplayText(item.body)
      }))
    }
  };
}

function inferScenario(status: CheckinTodayStatus | null) {
  const checkin = status?.checkin;
  if (!checkin) return 'transition' as const;
  const transitionDifficulty = checkin.transition_difficulty ?? 0;

  if (transitionDifficulty >= 7 || checkin.meltdown_count >= 2) {
    return 'transition' as const;
  }

  if (
    checkin.today_activities.some((item) =>
      ['医生预约', '社交活动', '外出安排', '学校活动', '需要长途通勤'].includes(item)
    ) ||
    checkin.negative_emotions.some((item) => ['焦虑', '恐惧', '社交回避'].includes(item))
  ) {
    return 'outing' as const;
  }

  if (checkin.today_learning_tasks.length) {
    return 'homework' as const;
  }

  if (checkin.child_sleep_hours <= 5 || checkin.caregiver_sleep_quality <= 4) {
    return 'bedtime' as const;
  }

  return 'transition' as const;
}

const riskBadgeLabel = {
  green: '稳定',
  yellow: '谨慎',
  red: '高负荷'
} as const;

export function HomePage({ token, familyId, onNavigate, onActionContextChange }: Props) {
  const today = getLocalDateString();
  const actionPlanRef = useRef<HTMLDivElement | null>(null);
  const todayStatusRequestGuardRef = useRef(createRequestGuard());

  const [status, setStatus] = useState<CheckinTodayStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [respiteOpen, setRespiteOpen] = useState(false);
  const [executionMode, setExecutionMode] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    if (!familyId) {
      todayStatusRequestGuardRef.current.invalidate();
      setStatus(null);
      setModalOpen(false);
      setExecutionMode(false);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setError('');
    const requestId = todayStatusRequestGuardRef.current.begin();
    getTodayCheckin(token, familyId, today)
      .then((data) => {
        if (cancelled || !todayStatusRequestGuardRef.current.isCurrent(requestId)) return;
        setStatus({
          ...data,
          today_one_thing: sanitizeDisplayText(data.today_one_thing),
          action_plan: data.action_plan
            ? {
                ...data.action_plan,
                headline: sanitizeDisplayText(data.action_plan.headline),
                summary: sanitizeDisplayText(data.action_plan.summary),
                reminders: data.action_plan.reminders.map((item) => ({
                  eyebrow: sanitizeDisplayText(item.eyebrow),
                  title: sanitizeDisplayText(item.title),
                  body: sanitizeDisplayText(item.body)
                }))
              }
            : data.action_plan
        });
        setExecutionMode(false);
        const dismissed = localStorage.getItem(buildDismissKey(familyId, today)) === '1';
        setModalOpen(data.needs_checkin && !dismissed);
      })
      .catch((err) => {
        if (cancelled || !todayStatusRequestGuardRef.current.isCurrent(requestId)) return;
        setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled && todayStatusRequestGuardRef.current.isCurrent(requestId)) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [familyId, token, today]);

  const createTodayActionContext = () => {
    if (!status?.action_plan || status.needs_checkin) return null;

    return createActionFlowContext({
      source: 'today',
      scenario: inferScenario(status),
      title: status.today_one_thing ?? status.action_plan.headline,
      summary: status.action_plan.summary,
      suggestedTriggers: status.risk?.reasons ?? [],
      suggestedFollowup: status.action_plan.three_step_action[0] ?? '',
      cardIds: []
    });
  };

  const submit = async (payload: CheckinFormPayload) => {
    if (!familyId) {
      setError('请先在【家庭】页创建家庭。');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const data = await postCheckin(token, { ...buildCheckinPayload(payload), family_id: familyId });
      todayStatusRequestGuardRef.current.invalidate();
      localStorage.setItem(buildDismissKey(familyId, today), '1');
      setStatus(toTodayStatus(familyId, data));
      setExecutionMode(false);
      setModalOpen(false);
      setLoading(false);
      onActionContextChange(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const openCheckin = () => setModalOpen(true);

  const startTodayAction = () => {
    const nextContext = createTodayActionContext();
    if (nextContext) {
      onActionContextChange(nextContext);
    }
    setExecutionMode(true);
    window.setTimeout(() => {
      actionPlanRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  };

  const goToReview = () => {
    const nextContext = createTodayActionContext();
    if (nextContext) {
      onActionContextChange(nextContext);
    }
    onNavigate('review');
  };

  const goToFrictionSupport = () => {
    const nextContext = createTodayActionContext();
    if (nextContext) {
      onActionContextChange(nextContext);
    }
    onNavigate('scripts');
  };

  const dismissModal = () => {
    if (familyId) {
      localStorage.setItem(buildDismissKey(familyId, today), '1');
    }
    setModalOpen(false);
  };

  const initialValues = status?.checkin
    ? {
        child_sleep_hours: status.checkin.child_sleep_hours,
        child_sleep_quality: status.checkin.child_sleep_quality,
        sleep_issues: status.checkin.sleep_issues,
        sensory_overload_level: status.checkin.sensory_overload_level,
        meltdown_count: status.checkin.meltdown_count,
        child_mood_state: status.checkin.child_mood_state,
        physical_discomforts: status.checkin.physical_discomforts,
        aggressive_behaviors: status.checkin.aggressive_behaviors,
        negative_emotions: status.checkin.negative_emotions,
        transition_difficulty: status.checkin.transition_difficulty,
        caregiver_stress: status.checkin.caregiver_stress,
        support_available: status.checkin.support_available,
        caregiver_sleep_quality: status.checkin.caregiver_sleep_quality,
        today_activities: status.checkin.today_activities,
        today_learning_tasks: status.checkin.today_learning_tasks
      }
    : undefined;

  const needs48hPlan = Boolean(status?.risk?.trigger_48h || status?.risk?.risk_level === 'red');
  const showCheckinEmptyState = Boolean(familyId && !loading && status?.needs_checkin);
  const showTodayActionPanel = Boolean(familyId && !loading && !status?.needs_checkin && status?.action_plan);
  const showNextStepPanel = !loading && !showCheckinEmptyState && !showTodayActionPanel;
  const todayActionSuggestions = getHomeActionSuggestions(status);
  const reminderCards = getHomeReminderCards(status);

  const nextStep = (() => {
    if (!familyId) {
      return {
        eyebrow: '现在先做什么',
        title: '先完成家庭档案',
        description: '先补孩子特点、常见触发器和有效安抚方式，后面的建议才会更贴近你家。',
        primaryLabel: '去家庭页建档',
        primaryAction: () => onNavigate('family'),
        secondaryActions: [] as { label: string; action: () => void }[]
      };
    }

    if (loading) {
      return {
        eyebrow: '正在准备',
        title: '正在同步今天状态',
        description: '正在读取今天是否已签到，以及今天更适合正常推进还是先放慢节奏。',
        primaryLabel: '稍后再试',
        primaryAction: () => undefined,
        secondaryActions: [] as { label: string; action: () => void }[]
      };
    }

    if (status?.needs_checkin) {
      return {
        eyebrow: '现在先做什么',
        title: '先花 30 秒签到',
        description: '先标出孩子和家长今天的状态，再决定今天先做什么。',
        primaryLabel: '开始签到',
        primaryAction: openCheckin,
        secondaryActions: [{ label: '查看家庭档案', action: () => onNavigate('family') }]
      };
    }

    if (needs48hPlan) {
      return {
        eyebrow: '优先稳住节奏',
        title: '今天先放慢节奏，只保留最低负荷任务',
        description: '先保住稳定和配合度，不追求额外推进；长期目标和训练进度仍放在训练跟踪页统一查看。',
        primaryLabel: '打开长期训练跟踪',
        primaryAction: () => onNavigate('plan'),
        secondaryActions: [{ label: '孩子卡住时去高摩擦页', action: goToFrictionSupport }]
      };
    }

    return {
      eyebrow: '现在先做什么',
      title: status?.today_one_thing ?? '先按今天行动卡开始',
      description: '先做眼前这一步；如果现场卡住，直接去高摩擦支援。',
      primaryLabel: '开始按这张卡执行',
      primaryAction: startTodayAction,
      secondaryActions: [
        { label: '孩子卡住时去高摩擦页', action: goToFrictionSupport },
        { label: '做完后快速复盘', action: goToReview }
      ]
    };
  })();

  return (
    <div className="grid">
      <section className="panel today-hero">
        <div>
          <p className="eyebrow">今日首页</p>
          <h2>先看今天状态，再照着下一步做</h2>
          <p className="muted">先签到确认今天情况，再按页面给出的下一步执行；孩子卡住时去高摩擦，做完后补一条复盘。</p>
        </div>
        <div className="hero-side">
          <span className="date-pill">{today}</span>
          {familyId ? (
            <button className="btn" type="button" onClick={openCheckin}>
              {status?.needs_checkin === false ? '修改今日签到' : '开始签到'}
            </button>
          ) : null}
        </div>
      </section>

      {!familyId ? (
        <div className="panel">
          <h3>还没有家庭档案</h3>
          <p className="muted">请先到【家庭】页创建家庭，再开始每日签到。</p>
        </div>
      ) : null}

      {loading ? <div className="panel">正在读取今日签到状态...</div> : null}

      {showNextStepPanel ? (
        <section className="panel next-step-panel">
          <div className="focus-header">
            <div>
              <p className="eyebrow">{nextStep.eyebrow}</p>
              <h3>{nextStep.title}</h3>
            </div>
            {status?.risk ? (
              <span className={`status-chip ${status.risk.risk_level}`}>风险 {riskBadgeLabel[status.risk.risk_level]}</span>
            ) : null}
          </div>
          <p>{nextStep.description}</p>
          <div className="focus-actions">
            <button className="btn" type="button" onClick={nextStep.primaryAction} disabled={loading}>
              {nextStep.primaryLabel}
            </button>
            {nextStep.secondaryActions.map((item) => (
              <button key={item.label} className="btn secondary" type="button" onClick={item.action}>
                {item.label}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {showCheckinEmptyState ? (
        <div className="panel empty-state">
          <p className="eyebrow">待完成</p>
          <h3>今天还没有签到</h3>
          <p className="muted">用几个问题标出今天状态，系统会告诉你今天先做什么。</p>
          <button className="btn" type="button" onClick={openCheckin}>
            现在签到
          </button>
        </div>
      ) : null}

      {status?.risk ? <RiskLight level={status.risk.risk_level} /> : null}

      {showTodayActionPanel && status && status.action_plan ? (
        <>
          <section className="panel today-focus-panel">
            <div className="focus-header">
              <div>
                <p className="eyebrow">今天最重要的一件事</p>
                <h2>{status.today_one_thing}</h2>
              </div>
              <span className={`status-chip ${needs48hPlan ? 'warning' : 'done'}`}>
                {needs48hPlan ? '轻量执行' : '直接行动'}
              </span>
            </div>
            <p className="focus-summary">{status.action_plan.headline}</p>
            {todayActionSuggestions.length ? (
              <div className="today-action-suggestions" aria-label="今日行动建议">
                <p className="eyebrow">按这个顺序直接做</p>
                <div className="today-action-list">
                  {todayActionSuggestions.map((item, index) => (
                    <article key={`${index + 1}-${item}`} className="today-action-item">
                      <span className="today-action-index">0{index + 1}</span>
                      <p>{item}</p>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="focus-actions">
              <button className="btn" type="button" onClick={needs48hPlan ? () => onNavigate('plan') : startTodayAction}>
                {needs48hPlan ? '打开长期训练跟踪' : '开始按这张卡执行'}
              </button>
              <button className="btn secondary" type="button" onClick={goToFrictionSupport}>
                现场卡住时，去高摩擦支援
              </button>
              <button className="btn secondary" type="button" onClick={goToReview}>
                做完后快速复盘
              </button>
            </div>
          </section>

          <section className="panel compact-panel reminder-panel">
            <div className="compact-panel-head">
              <div>
                <p className="eyebrow">执行前先看</p>
                <h3>预防性建议</h3>
              </div>
              <span className="status-chip muted">这部分解决怎么提前防</span>
            </div>
            <div className="reminder-grid">
              {reminderCards.map((item, index) => (
                <article key={`${item.eyebrow}-${item.title}`} className="reminder-card">
                  <span className="reminder-index">0{index + 1}</span>
                  <div className="reminder-copy">
                    <p className="eyebrow">{item.eyebrow}</p>
                    <h4>{item.title}</h4>
                    <p>{item.body}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>

          {executionMode ? (
            <section ref={actionPlanRef} className="panel execution-panel">
              <div className="focus-header">
                <div>
                  <p className="eyebrow">执行模式</p>
                  <h3>现在就照着这 3 步做</h3>
                </div>
                <span className="status-pill">只盯当下，不展开多余信息</span>
              </div>

              <div className="execution-step-grid">
                {status.action_plan.three_step_action.map((item, index) => (
                  <article key={item} className="execution-step-card">
                    <span className="execution-step-index">0{index + 1}</span>
                    <p>{item}</p>
                  </article>
                ))}
              </div>

              <div className="execution-support-grid">
                <div className="execution-support-card">
                  <p className="eyebrow">可以直接说</p>
                  <p className="quote-box">“{status.action_plan.parent_phrase}”</p>
                </div>
                <div className="execution-support-card">
                  <p className="eyebrow">给自己留退路</p>
                  <p>{status.action_plan.respite_suggestion}</p>
                </div>
              </div>

              <div className="focus-actions">
                <button className="btn secondary" type="button" onClick={goToFrictionSupport}>
                  现场卡住了，切到高摩擦支援
                </button>
                <button className="btn" type="button" onClick={goToReview}>
                  做完后去轻复盘
                </button>
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      {error ? <div className="panel error">{error}</div> : null}

      <CheckinCard
        open={modalOpen}
        date={today}
        submitting={submitting}
        initialValues={initialValues}
        onClose={dismissModal}
        onSubmit={submit}
      />

      <MicroRespiteModal
        open={respiteOpen}
        token={token}
        familyId={familyId}
        initialCheckin={status?.checkin}
        risk={status?.risk}
        onClose={() => setRespiteOpen(false)}
      />
    </div>
  );
}
