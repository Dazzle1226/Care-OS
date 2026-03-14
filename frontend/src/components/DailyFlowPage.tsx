import { AnimatePresence, motion } from 'framer-motion';
import { createPortal } from 'react-dom';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import type { CheckinFormPayload } from '../lib/checkinPayload';
import { getTodayCheckin, postCheckin } from '../lib/api';
import {
  buildDailyFlowContent,
  buildCheckinSummary,
  getDailyFlowScenario,
  inferScenarioFromCheckin,
  toCheckinPayloadFromRecord,
  toCheckinInitialValues,
  type DemoScenarioId,
  type QuickActionDefinition
} from '../lib/dailyFlow';
import { createActionFlowContext, type ActionFlowContext, type CareTab } from '../lib/flow';
import type { CheckinTodayStatus } from '../lib/types';
import { CheckinCard } from './CheckinCard';

interface Props {
  token: string;
  familyId: number | null;
  onNavigate: (tab: CareTab) => void;
  onActionContextChange: (context: ActionFlowContext | null) => void;
  openCheckinSignal?: number;
  variant?: 'page' | 'embedded';
}

type FlowStepId = 'checkin' | 'priority' | 'preventive' | 'quick';

const motionTransition = {
  duration: 0.42,
  ease: [0.22, 1, 0.36, 1]
} as const;

function formatDisplayDate() {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long'
  }).format(new Date());
}

function getLocalDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function FlowContainer({ children, quietMode }: { children: ReactNode; quietMode: boolean }) {
  return (
    <motion.div layout className={`daily-flow-shell ${quietMode ? 'is-quiet' : ''}`}>
      <div className="daily-flow-backdrop" aria-hidden="true" />
      <div className="daily-flow-column">{children}</div>
    </motion.div>
  );
}

function CheckinPromptCard({
  onOpen
}: {
  onOpen: () => void;
}) {
  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 20, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={motionTransition}
      className="daily-flow-card is-current"
    >
      <div className="daily-flow-card-header">
        <div>
          <p className="eyebrow">Level 1</p>
          <h2>今日签到</h2>
        </div>
        <span className="daily-flow-step-state">当前步骤</span>
      </div>
      <div className="daily-flow-priority">
        <h3>先完成签到，系统再决定今天的行动层级</h3>
        <p>家长不需要自己判断今天是平稳日还是高压力日。先按原来的签到问题填写，系统会根据答案自动重组后续界面。</p>
      </div>
      <div className="daily-flow-actions">
        <span className="daily-flow-inline-note">签到会以悬浮弹窗打开；完成后页面不跳转，只在这里继续往下长。</span>
        <button type="button" className="btn" onClick={onOpen}>
          开始今日签到
        </button>
      </div>
    </motion.section>
  );
}

function CollapsedStepCard({
  eyebrow,
  title,
  summary,
  actionLabel,
  onAction,
  elevated = false
}: {
  eyebrow: string;
  title: string;
  summary: string;
  actionLabel?: string;
  onAction?: () => void;
  elevated?: boolean;
}) {
  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={motionTransition}
      className={`daily-flow-card is-collapsed ${elevated ? 'is-elevated' : ''}`}
    >
      <div className="daily-flow-card-header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h3>{title}</h3>
        </div>
        <span className="daily-flow-step-state">已完成</span>
      </div>
      <p className="daily-flow-summary">{summary}</p>
      {actionLabel && onAction ? (
        <div className="daily-flow-actions">
          <span className="daily-flow-inline-note">需要的话可以回到弹窗里修改今天签到。</span>
          <button type="button" className="btn secondary" onClick={onAction}>
            {actionLabel}
          </button>
        </div>
      ) : null}
    </motion.section>
  );
}

function PriorityActionCard({
  title,
  body,
  checklist,
  onContinue
}: {
  title: string;
  body: string;
  checklist: string[];
  onContinue: () => void;
}) {
  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 26, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={motionTransition}
      className="daily-flow-card is-current"
    >
      <div className="daily-flow-card-header">
        <div>
          <p className="eyebrow">Level 2</p>
          <h2>今天最重要的一件事</h2>
        </div>
        <span className="daily-flow-step-state">现在先看这个</span>
      </div>
      <div className="daily-flow-priority">
        <h3>{title}</h3>
        <p>{body}</p>
        <ul className="daily-flow-bullet-list">
          {checklist.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div className="daily-flow-actions">
        <span className="daily-flow-inline-note">先确认这件事，下一张卡片才会继续展开。</span>
        <button type="button" className="btn" onClick={onContinue}>
          我知道今天先抓这一件
        </button>
      </div>
    </motion.section>
  );
}

function PreventiveSuggestionCard({
  title,
  body,
  suggestions,
  hasQuickActions,
  onContinue,
  isSettled,
  hideAction
}: {
  title: string;
  body: string;
  suggestions: string[];
  hasQuickActions: boolean;
  onContinue: () => void;
  isSettled: boolean;
  hideAction?: boolean;
}) {
  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 24, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={motionTransition}
      className={`daily-flow-card is-current ${isSettled ? 'is-settled' : ''}`}
    >
      <div className="daily-flow-card-header">
        <div>
          <p className="eyebrow">Level 3</p>
          <h2>预防性建议</h2>
        </div>
        <span className="daily-flow-step-state">{isSettled ? '已准备好' : '下一步马上展开'}</span>
      </div>
      <div className="daily-flow-preventive">
        <h3>{title}</h3>
        <p>{body}</p>
        <div className="daily-flow-preventive-list">
          {suggestions.map((item, index) => (
            <article key={item} className="daily-flow-preventive-item">
              <span>0{index + 1}</span>
              <p>{item}</p>
            </article>
          ))}
        </div>
      </div>
      <div className="daily-flow-actions">
        <span className="daily-flow-inline-note">
          {hasQuickActions ? '确认后，系统会继续推送最相关的执行入口。' : '今天就按这一个主任务加这一条提醒走。'}
        </span>
        {!hideAction ? (
          <button type="button" className="btn" onClick={onContinue}>
            {hasQuickActions ? '继续，我要看直接入口' : isSettled ? '今天先按这个执行' : '确认，今天就按这个节奏走'}
          </button>
        ) : null}
      </div>
    </motion.section>
  );
}

function QuickActionEntryCard({
  actions,
  activeAction,
  onActionChange,
  onNavigate,
  onLowStimulus
}: {
  actions: QuickActionDefinition[];
  activeAction: QuickActionDefinition;
  onActionChange: (action: QuickActionDefinition) => void;
  onNavigate: (target: 'scripts' | 'review') => void;
  onLowStimulus: () => void;
}) {
  const handlePrimaryAction = () => {
    if (activeAction.ctaTarget) onNavigate(activeAction.ctaTarget);
  };

  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 22, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={motionTransition}
      className="daily-flow-card is-current is-quick"
    >
      <div className="daily-flow-card-header">
        <div>
          <p className="eyebrow">Level 4</p>
          <h2>直接入口</h2>
        </div>
        <span className="daily-flow-step-state">保持最小下一步</span>
      </div>

      <div className="daily-flow-quick-grid">
        {actions.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`daily-flow-quick-button ${item.id === activeAction.id ? 'is-active' : ''}`}
            onClick={() => {
              onActionChange(item);
              if (item.id === 'lowStim') onLowStimulus();
            }}
          >
            <strong>{item.title}</strong>
            <span>{item.description}</span>
          </button>
        ))}
      </div>

      <motion.div
        key={activeAction.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={motionTransition}
        className="daily-flow-quick-detail"
      >
        <p className="eyebrow">当前入口</p>
        <h3>{activeAction.detailTitle}</h3>
        <p>{activeAction.detailBody}</p>
        <ul className="daily-flow-bullet-list">
          {activeAction.steps.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <div className="daily-flow-actions">
          <span className="daily-flow-inline-note">只开一个入口，避免今天再在多个模块里跳来跳去。</span>
          <div className="daily-flow-action-group">
            {activeAction.id === 'lowStim' ? (
              <button type="button" className="btn secondary" onClick={onLowStimulus}>
                保持低刺激模式
              </button>
            ) : null}
            {activeAction.ctaLabel && activeAction.ctaTarget ? (
              <button type="button" className="btn" onClick={handlePrimaryAction}>
                {activeAction.ctaLabel}
              </button>
            ) : null}
          </div>
        </div>
      </motion.div>
    </motion.section>
  );
}

function FlowModal({
  open,
  quietMode,
  onClose,
  children
}: {
  open: boolean;
  quietMode: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
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

  if (!open || typeof document === 'undefined') return null;

  return createPortal(
    <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="daily-flow-modal-title">
      <div className="modal-backdrop" onClick={onClose} />
      <motion.div
        layout
        initial={{ opacity: 0, y: 16, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={motionTransition}
        className={`modal-card modal-card-fixed-close daily-flow-modal-card ${quietMode ? 'is-quiet' : ''}`}
      >
        <button
          className="icon-btn modal-close-fixed"
          type="button"
          onClick={onClose}
          aria-label="关闭今日行动流"
        >
          ×
        </button>
        <div className="modal-scroll-area daily-flow-modal-scroll">{children}</div>
      </motion.div>
    </div>,
    document.body
  );
}

export function DailyFlowPage({
  token,
  familyId,
  onNavigate,
  onActionContextChange,
  openCheckinSignal = 0,
  variant = 'page'
}: Props) {
  const isEmbedded = variant === 'embedded';
  const today = useMemo(() => getLocalDateString(), []);
  const dateLabel = useMemo(() => formatDisplayDate(), []);
  const cardRefs = useRef<Partial<Record<FlowStepId, HTMLDivElement | null>>>({});
  const [checkinOpen, setCheckinOpen] = useState(false);
  const [flowModalOpen, setFlowModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submittedCheckin, setSubmittedCheckin] = useState<CheckinFormPayload | null>(null);
  const [todayStatus, setTodayStatus] = useState<CheckinTodayStatus | null>(null);
  const [loadingTodayStatus, setLoadingTodayStatus] = useState(false);
  const [todayStatusReady, setTodayStatusReady] = useState(false);
  const [currentStep, setCurrentStep] = useState<FlowStepId>('checkin');
  const [priorityDone, setPriorityDone] = useState(false);
  const [preventiveDone, setPreventiveDone] = useState(false);
  const [settledAfterPreventive, setSettledAfterPreventive] = useState(false);
  const [preventiveExecutionConfirmed, setPreventiveExecutionConfirmed] = useState(false);
  const [manualQuietMode, setManualQuietMode] = useState(false);
  const [activeQuickActionId, setActiveQuickActionId] = useState<QuickActionDefinition['id'] | null>(null);

  const scenarioId = useMemo<DemoScenarioId | null>(
    () => (submittedCheckin ? inferScenarioFromCheckin(submittedCheckin) : null),
    [submittedCheckin]
  );
  const scenario = useMemo(() => (scenarioId ? getDailyFlowScenario(scenarioId) : null), [scenarioId]);
  const flowContent = useMemo(() => buildDailyFlowContent(todayStatus, scenario), [todayStatus, scenario]);
  const quietMode = manualQuietMode || Boolean(scenario?.lowStimulus);

  useEffect(() => {
    const nextCard = cardRefs.current[currentStep];
    if (!nextCard) return;
    window.setTimeout(() => {
      nextCard.focus();
      nextCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 120);
  }, [currentStep]);

  useEffect(() => {
    if (!scenario) {
      setActiveQuickActionId(null);
      return;
    }
    setActiveQuickActionId(scenario.quickActions[0]?.id ?? null);
  }, [scenario]);

  useEffect(() => {
    let cancelled = false;

    if (!familyId) {
      setTodayStatus(null);
      setSubmittedCheckin(null);
      setTodayStatusReady(true);
      return () => {
        cancelled = true;
      };
    }

    setLoadingTodayStatus(true);
    setTodayStatusReady(false);

    getTodayCheckin(token, familyId, today)
      .then((status) => {
        if (cancelled) return;

        setTodayStatus(status);

        if (status.needs_checkin || !status.checkin) {
          setSubmittedCheckin(null);
          setCurrentStep('checkin');
          setPriorityDone(false);
          setPreventiveDone(false);
          setSettledAfterPreventive(false);
          setPreventiveExecutionConfirmed(false);
          setManualQuietMode(false);
          return;
        }

        const restoredCheckin = toCheckinPayloadFromRecord(status.checkin);
        const restoredScenario = getDailyFlowScenario(inferScenarioFromCheckin(restoredCheckin));

        setSubmittedCheckin(restoredCheckin);
        setPriorityDone(true);
        setPreventiveExecutionConfirmed(false);
        setManualQuietMode(false);

        if (restoredScenario.quickActions.length > 0) {
          setPreventiveDone(true);
          setSettledAfterPreventive(false);
          setCurrentStep('quick');
          return;
        }

        setPreventiveDone(false);
        setSettledAfterPreventive(true);
        setCurrentStep('preventive');
      })
      .catch(() => {
        if (cancelled) return;
        setTodayStatus(null);
      })
      .finally(() => {
        if (cancelled) return;
        setLoadingTodayStatus(false);
        setTodayStatusReady(true);
      });

    return () => {
      cancelled = true;
    };
  }, [familyId, today, token]);

  useEffect(() => {
    if (!openCheckinSignal || !todayStatusReady) return;
    if (submittedCheckin) {
      setFlowModalOpen(true);
      return;
    }
    setCheckinOpen(true);
  }, [openCheckinSignal, submittedCheckin, todayStatusReady]);

  const createMockActionContext = () => {
    if (!scenario) return null;
    return createActionFlowContext({
      source: 'today',
      scenario: 'transition',
      title: flowContent.priorityTitle || scenario.primaryTitle,
      summary: flowContent.priorityBody || scenario.primaryBody,
      suggestedTriggers: submittedCheckin ? buildCheckinSummary(submittedCheckin) : [],
      suggestedFollowup: flowContent.preventiveSuggestions[0] ?? scenario.preventiveSuggestions[0] ?? scenario.primaryChecklist[0] ?? '',
      cardIds: []
    });
  };

  const handleCheckinSubmit = async (payload: CheckinFormPayload) => {
    setSubmitting(true);

    try {
      const response = await postCheckin(token, {
        family_id: familyId,
        ...payload,
      });

      setSubmittedCheckin(toCheckinPayloadFromRecord(response.checkin));
      setTodayStatus({
        family_id: familyId ?? 0,
        date: response.checkin.date,
        needs_checkin: false,
        checkin: response.checkin,
        risk: response.risk,
        today_one_thing: response.today_one_thing,
        action_plan: response.action_plan,
      });
      setCurrentStep('priority');
      setPriorityDone(false);
      setPreventiveDone(false);
      setSettledAfterPreventive(false);
      setPreventiveExecutionConfirmed(false);
      setManualQuietMode(false);
      setFlowModalOpen(true);
      setCheckinOpen(false);
      onActionContextChange(null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickNavigate = (target: 'scripts' | 'review') => {
    const nextContext = createMockActionContext();
    if (nextContext) onActionContextChange(nextContext);
    onNavigate(target);
  };

  const handlePreventiveContinue = () => {
    if (!scenario) return;

    if (scenario.quickActions.length > 0) {
      setPreventiveDone(true);
      setCurrentStep('quick');
      return;
    }

    if (settledAfterPreventive) {
      const nextContext = createMockActionContext();
      setPreventiveExecutionConfirmed(true);
      if (nextContext) onActionContextChange(nextContext);
      setFlowModalOpen(false);
      return;
    }

    setPreventiveDone(true);
    setSettledAfterPreventive(true);
    setCurrentStep('preventive');
  };

  const activeQuickAction =
    scenario?.quickActions.find((item) => item.id === activeQuickActionId) ?? scenario?.quickActions[0] ?? null;

  const renderFlowSequence = (showHeader: boolean) =>
    submittedCheckin && scenario ? (
      <div className="daily-flow-modal-stack">
        {showHeader ? (
        <div className="daily-flow-modal-head">
          <div>
            <p className="eyebrow">Daily Flow</p>
            <h2 id="daily-flow-modal-title">签到已完成，系统正在带你往下走</h2>
          </div>
          <div className="daily-flow-modal-meta">
            <span className="date-pill">{dateLabel}</span>
            <span
              className={`daily-flow-risk-chip ${
                scenario.id === 'high' ? 'is-high' : scenario.id === 'watch' ? 'is-watch' : 'is-stable'
              }`}
            >
              {scenario.riskLabel}
            </span>
          </div>
        </div>
        ) : null}

        <div
          ref={(node) => {
            cardRefs.current.checkin = node;
          }}
          tabIndex={-1}
        >
          <CollapsedStepCard
            eyebrow="已完成签到"
            title="今天状态已记录"
            summary={buildCheckinSummary(submittedCheckin).slice(0, 3).join(' · ')}
            actionLabel="修改今日签到"
            onAction={() => {
              setFlowModalOpen(false);
              setCheckinOpen(true);
            }}
            elevated
          />
        </div>

        <AnimatePresence initial={false}>
          {priorityDone && currentStep !== 'priority' ? (
            <div
              ref={(node) => {
                cardRefs.current.priority = node;
              }}
              tabIndex={-1}
            >
              <CollapsedStepCard eyebrow="已确认主任务" title="今天先抓这一件" summary={scenario.primaryTitle} />
            </div>
          ) : null}

          {currentStep === 'priority' ? (
            <div
              ref={(node) => {
                cardRefs.current.priority = node;
              }}
              tabIndex={-1}
            >
              <PriorityActionCard
                title={flowContent.priorityTitle}
                body={flowContent.priorityBody}
                checklist={flowContent.priorityChecklist}
                onContinue={() => {
                  setPriorityDone(true);
                  setCurrentStep('preventive');
                }}
              />
            </div>
          ) : null}

          {(priorityDone || currentStep === 'preventive' || currentStep === 'quick') && currentStep !== 'priority' ? (
            <>
              {preventiveDone && currentStep === 'quick' ? (
                <div
                  ref={(node) => {
                    cardRefs.current.preventive = node;
                  }}
                  tabIndex={-1}
                >
                  <CollapsedStepCard
                    eyebrow="已确认预防动作"
                    title="今天先这样提前减负"
                    summary={flowContent.preventiveSuggestions.join(' · ')}
                  />
                </div>
              ) : (
                <div
                  ref={(node) => {
                    cardRefs.current.preventive = node;
                  }}
                  tabIndex={-1}
                >
                  <PreventiveSuggestionCard
                    title={flowContent.preventiveTitle}
                  body={flowContent.preventiveBody}
                  suggestions={flowContent.preventiveSuggestions}
                  hasQuickActions={scenario.quickActions.length > 0}
                  isSettled={settledAfterPreventive}
                  hideAction={preventiveExecutionConfirmed}
                  onContinue={handlePreventiveContinue}
                />
              </div>
              )}
            </>
          ) : null}

          {currentStep === 'quick' && activeQuickAction ? (
            <div
              ref={(node) => {
                cardRefs.current.quick = node;
              }}
              tabIndex={-1}
            >
              <QuickActionEntryCard
                actions={scenario.quickActions}
                activeAction={activeQuickAction}
                onActionChange={(action) => setActiveQuickActionId(action.id)}
                onNavigate={handleQuickNavigate}
                onLowStimulus={() => setManualQuietMode(true)}
              />
            </div>
          ) : null}
        </AnimatePresence>
      </div>
    ) : null;

  const flowSequence = renderFlowSequence(!isEmbedded);

  return (
    <div className={`daily-flow-page ${isEmbedded ? 'is-embedded' : ''}`}>
      {!isEmbedded ? (
        <section className="daily-flow-header panel">
          <div className="daily-flow-header-copy">
            <p className="eyebrow">Daily Flow</p>
            <h1>每日签到 → 今日行动计划</h1>
            <p>{scenario?.greeting ?? '先完成今日签到，系统会根据你的回答自动判断今天更适合怎样推进。'}</p>
            <p className="muted">{scenario?.helper ?? '签到完成后页面不会跳转，而是把今天最值得优先处理的内容原地推到你眼前。'}</p>
          </div>
          <div className="daily-flow-header-side">
            <span className="date-pill">{dateLabel}</span>
            {scenario ? (
              <span
                className={`daily-flow-risk-chip ${
                  scenario.id === 'high' ? 'is-high' : scenario.id === 'watch' ? 'is-watch' : 'is-stable'
                }`}
              >
                {scenario.riskLabel}
              </span>
            ) : (
              <span className="daily-flow-risk-chip">等待签到</span>
            )}
            {submittedCheckin ? (
              <button
                type="button"
                className={`btn secondary ${quietMode ? 'is-active' : ''}`}
                onClick={() => setManualQuietMode((value) => !value)}
              >
                {quietMode ? '退出低刺激模式' : '低刺激模式'}
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      {!familyId ? (
        <section className="daily-flow-card">
          <p className="eyebrow">先完成准备</p>
          <h3>当前还没有家庭档案</h3>
          <p>先去家庭页完成建档，首页行动流才会绑定到具体家庭场景。</p>
          <div className="daily-flow-actions">
            <span className="daily-flow-inline-note">首页 demo 已准备好，但正式使用仍需要家庭档案。</span>
            <button type="button" className="btn" onClick={() => onNavigate('family')}>
              去家庭页建档
            </button>
          </div>
        </section>
      ) : (
        <>
          <FlowContainer quietMode={quietMode}>
            {loadingTodayStatus && !todayStatusReady ? (
              <section className="daily-flow-card is-current">
                <div className="daily-flow-card-header">
                  <div>
                    <p className="eyebrow">正在恢复</p>
                    <h3>读取今天已保存的签到记录</h3>
                  </div>
                  <span className="daily-flow-step-state">请稍候</span>
                </div>
                <p className="daily-flow-summary">如果今天已经签过到，这里会直接恢复已生成的行动建议，不会要求重新填写。</p>
              </section>
            ) : submittedCheckin ? (
              isEmbedded ? (
                <section className="daily-flow-embedded-review">
                  <div className="daily-flow-embedded-review-head">
                    <div>
                      <p className="eyebrow">已生成今日行动流</p>
                      <h3>弹窗生成后，这里也能继续回看</h3>
                    </div>
                    <div className="daily-flow-embedded-review-actions">
                      <button type="button" className="btn secondary" onClick={() => setCheckinOpen(true)}>
                        修改签到
                      </button>
                      <button type="button" className="btn" onClick={() => setFlowModalOpen(true)}>
                        打开悬浮弹窗
                      </button>
                    </div>
                  </div>
                  <div className="daily-flow-embedded-scroll" aria-label="今日行动流回看区">
                    {renderFlowSequence(false)}
                  </div>
                </section>
              ) : (
                <div
                  ref={(node) => {
                    cardRefs.current.checkin = node;
                  }}
                  tabIndex={-1}
                >
                  <CollapsedStepCard
                    eyebrow="已完成签到"
                    title="今天状态已记录"
                    summary={buildCheckinSummary(submittedCheckin).slice(0, 3).join(' · ')}
                    actionLabel="查看今日行动流"
                    onAction={() => setFlowModalOpen(true)}
                  />
                </div>
              )
            ) : (
              <div
                ref={(node) => {
                  cardRefs.current.checkin = node;
                }}
                tabIndex={-1}
              >
                <CheckinPromptCard onOpen={() => setCheckinOpen(true)} />
              </div>
            )}
          </FlowContainer>

          {!isEmbedded ? (
            <section className="daily-flow-footer-nav">
              <button type="button" className="daily-flow-footer-link" onClick={() => onNavigate('family')}>
                家庭档案
              </button>
              <button
                type="button"
                className="daily-flow-footer-link"
                onClick={() => {
                  const nextContext = createMockActionContext();
                  if (nextContext) onActionContextChange(nextContext);
                  onNavigate('scripts');
                }}
              >
                高摩擦支援
              </button>
              <button
                type="button"
                className="daily-flow-footer-link"
                onClick={() => {
                  const nextContext = createMockActionContext();
                  if (nextContext) onActionContextChange(nextContext);
                  onNavigate('review');
                }}
              >
                轻复盘
              </button>
            </section>
          ) : null}
        </>
      )}

      <CheckinCard
        open={checkinOpen}
        date={today}
        submitting={submitting}
        initialValues={toCheckinInitialValues(submittedCheckin)}
        onClose={() => setCheckinOpen(false)}
        onSubmit={handleCheckinSubmit}
      />

      <FlowModal open={flowModalOpen && Boolean(submittedCheckin && scenario)} quietMode={quietMode} onClose={() => setFlowModalOpen(false)}>
        {flowSequence}
      </FlowModal>
    </div>
  );
}
