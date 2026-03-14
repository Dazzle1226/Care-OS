import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useState } from 'react';

import { MicroRespiteModal } from './components/MicroRespiteModal';
import { FlowTabs } from './components/FlowTabs';
import { FAMILY_MISSING_EVENT, getOnboardingFamily, isFamilyNotFoundError, login } from './lib/api';
import { readActionFlowContext, type ActionFlowContext, type CareTab, writeActionFlowContext } from './lib/flow';
import { scheduleScrollWorkspaceToTop } from './lib/scroll';
import type { OnboardingSummary } from './lib/types';
import { FamilyPage } from './pages/Family';
import { HomePage } from './pages/Home';
import { OnboardingPage } from './pages/Onboarding';
import { PlanPage } from './pages/Plan';
import { ReviewPage } from './pages/Review';
import { ScriptsPage } from './pages/Scripts';

type TopbarIconName = 'app' | 'family' | 'respite' | 'quiet';
type SecondaryTab = Exclude<CareTab, 'today'>;

const secondaryContentMotion = {
  initial: { opacity: 0, y: 18, filter: 'blur(10px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, y: -12, filter: 'blur(8px)' },
  transition: { duration: 0.22, ease: [0.22, 1, 0.36, 1] as const }
};

function readStorage(key: string, fallback = '') {
  if (typeof window === 'undefined') return fallback;

  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key: string, value: string) {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore storage failures so the app can still render.
  }
}

function removeStorage(key: string) {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore storage failures so the app can still render.
  }
}

function TopbarIcon({ name }: { name: TopbarIconName }) {
  if (name === 'family') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 12.3a3.3 3.3 0 1 0 0-6.6 3.3 3.3 0 0 0 0 6.6Zm-5.4 4.8a5.4 5.4 0 0 1 10.8 0"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M4.6 10.7a2.6 2.6 0 1 1 0-5.2M19.4 10.7a2.6 2.6 0 1 0 0-5.2M2.9 17.6a4.1 4.1 0 0 1 2.9-3.9M21.1 17.6a4.1 4.1 0 0 0-2.9-3.9"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.6"
        />
      </svg>
    );
  }

  if (name === 'respite') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 3.8v4.4m0 7.6v4.4M3.8 12h4.4m7.6 0h4.4"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
        <path
          d="M12 18.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (name === 'quiet') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M15.7 18.5A7.5 7.5 0 0 1 9.5 5a7.7 7.7 0 1 0 9.5 9.5 7.4 7.4 0 0 1-3.3 4Z"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="4.5" width="17" height="15" rx="4" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M7.5 9.2h9m-9 4.1h5.4"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export default function App() {
  const [tab, setTab] = useState<CareTab>('today');
  const [identifier, setIdentifier] = useState(() => readStorage('care_os_identifier', 'demo@careos'));
  const [token, setToken] = useState(() => readStorage('care_os_token'));
  const [familyId, setFamilyId] = useState<number | null>(() => Number(readStorage('care_os_family_id')) || null);
  const [familySummary, setFamilySummary] = useState<OnboardingSummary | null>(null);
  const [actionContext, setActionContext] = useState<ActionFlowContext | null>(() => readActionFlowContext());
  const [showCompletionCta, setShowCompletionCta] = useState(false);
  const [lowStim, setLowStim] = useState(false);
  const [respiteOpen, setRespiteOpen] = useState(false);
  const [error, setError] = useState('');
  const [validatingFamily, setValidatingFamily] = useState(Boolean(token && familyId));

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', lowStim ? 'low-stim' : 'normal');
    const themeColor = document.querySelector('meta[name="theme-color"]');
    themeColor?.setAttribute('content', lowStim ? '#efe9e2' : '#0f2f2b');
  }, [lowStim]);

  useEffect(() => {
    if (token) writeStorage('care_os_token', token);
  }, [token]);

  useEffect(() => {
    if (familyId) {
      writeStorage('care_os_family_id', String(familyId));
      return;
    }
    removeStorage('care_os_family_id');
  }, [familyId]);

  useEffect(() => {
    if (typeof window === 'undefined' || tab === 'today') return;

    return scheduleScrollWorkspaceToTop(document, window);
  }, [tab]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const handleFamilyMissing = () => {
      setFamilyId(null);
      setFamilySummary(null);
      setActionContext(null);
      writeActionFlowContext(null);
      setShowCompletionCta(false);
      setTab('today');
      setRespiteOpen(false);
      setValidatingFamily(false);
      setError('当前家庭档案不存在，请重新完成一次家庭设置。');
    };

    window.addEventListener(FAMILY_MISSING_EVENT, handleFamilyMissing);
    return () => window.removeEventListener(FAMILY_MISSING_EVENT, handleFamilyMissing);
  }, []);

  useEffect(() => {
    let cancelled = false;

    if (!token || !familyId) {
      setValidatingFamily(false);
      return () => {
        cancelled = true;
      };
    }

    setValidatingFamily(true);
    setError('');
    getOnboardingFamily(token, familyId)
      .then((summary) => {
        if (cancelled) return;
        setFamilySummary((current) => (current?.family.family_id === summary.family.family_id ? current : summary));
      })
      .catch((err) => {
        if (cancelled || isFamilyNotFoundError(err)) return;
        setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setValidatingFamily(false);
      });

    return () => {
      cancelled = true;
    };
  }, [familyId, token]);

  const handleActionContextChange = (nextContext: ActionFlowContext | null) => {
    setActionContext(nextContext);
    writeActionFlowContext(nextContext);
  };

  const doLogin = async () => {
    setError('');
    try {
      const data = await login(identifier);
      setToken(data.access_token);
      writeStorage('care_os_identifier', identifier);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleOnboardingComplete = (summary: OnboardingSummary) => {
    setError('');
    setFamilySummary(summary);
    setFamilyId(summary.family.family_id);
    setTab('today');
    setShowCompletionCta(true);
  };

  const renderSecondaryPage = (currentTab: SecondaryTab) => {
    if (currentTab === 'scripts') {
      return (
        <ScriptsPage
          token={token}
          familyId={familyId}
          lowStim={lowStim}
          onToggleLowStim={() => setLowStim((value) => !value)}
          onNavigate={setTab}
          onActionContextChange={handleActionContextChange}
        />
      );
    }

    if (currentTab === 'plan') {
      return (
        <PlanPage
          token={token}
          familyId={familyId}
          onNavigate={setTab}
          onActionContextChange={handleActionContextChange}
        />
      );
    }

    if (currentTab === 'review') {
      return (
        <ReviewPage
          token={token}
          familyId={familyId}
          actionContext={actionContext}
          onNavigate={setTab}
          onActionContextChange={handleActionContextChange}
        />
      );
    }

    return (
      <FamilyPage
        token={token}
        familyId={familyId}
        summary={familySummary}
        onSummaryChange={(nextSummary) => setFamilySummary(nextSummary)}
        showCompletionCta={showCompletionCta}
        onFinishSetup={() => {
          setShowCompletionCta(false);
          setTab('today');
        }}
      />
    );
  };

  return (
    <div className="app">
      {tab !== 'today' ? (
        <div className={`topbar ${lowStim ? 'topbar-low-stim' : ''}`}>
          <div className="topbar-main">
            <div className="brand-lockup">
              <div className="brand-mark" aria-hidden="true">
                <TopbarIcon name="app" />
              </div>
              <div className="brand-copy">
                <div className="topbar-kicker-row">
                  <span className="eyebrow topbar-kicker">Caregiving Workspace</span>
                  <span className={`workspace-status ${familyId ? 'connected' : 'pending'}`}>
                    {familyId ? '家庭已连接' : '等待建档'}
                  </span>
                </div>
                <div className="brand-row">
                  <div className="brand">赫兹 Hertz</div>
                  {token ? <span className="date-pill subtle">已登录工作台</span> : null}
                </div>
                <div className="tagline">听见那些未曾开口的爱</div>
              </div>
            </div>
          </div>
          <div className="topbar-actions">
            {familyId ? (
              <button
                className={`family-shortcut ${tab === 'family' ? 'active' : ''}`}
                type="button"
                onClick={() => setTab('family')}
              >
                <span className="family-shortcut-icon" aria-hidden="true">
                  <TopbarIcon name="family" />
                </span>
                <span className="family-shortcut-copy">
                  <span className="family-shortcut-label">家庭档案</span>
                  <strong>{familySummary?.family.name ?? `家庭 #${familyId}`}</strong>
                  <span className="family-shortcut-hint">查看关键信息或修改详细档案</span>
                </span>
              </button>
            ) : null}
            {familyId ? (
              <button className="toolbar-btn" type="button" onClick={() => setRespiteOpen(true)}>
                <span className="toolbar-btn-icon" aria-hidden="true">
                  <TopbarIcon name="respite" />
                </span>
                <span className="toolbar-btn-copy">
                  <strong>微喘息</strong>
                  <small>快速重置 3 分钟</small>
                </span>
              </button>
            ) : null}
            <button className={`toolbar-btn ${lowStim ? 'active' : ''}`} onClick={() => setLowStim((value) => !value)}>
              <span className="toolbar-btn-icon" aria-hidden="true">
                <TopbarIcon name="quiet" />
              </span>
              <span className="toolbar-btn-copy">
                <strong>{lowStim ? '退出低刺激模式' : '低刺激模式'}</strong>
                <small>{lowStim ? '恢复标准视觉节奏' : '降低页面刺激强度'}</small>
              </span>
            </button>
          </div>
        </div>
      ) : null}

      {!token ? (
        <main className="workspace workspace-single workspace-native workspace-auth">
          <section className="workspace-stage">
            <div className="content-page-shell auth-page-shell">
              <div className="panel auth-panel">
                <p className="eyebrow">Access</p>
                <h3>进入照护工作台</h3>
                <p className="workspace-intro">先登录演示账号，再进入家庭建档和今日行动流。</p>
                <label>
                  <span className="label">账号标识</span>
                  <input className="input" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
                </label>
                <button className="btn" onClick={doLogin}>
                  登录
                </button>
                {error ? <div className="error">{error}</div> : null}
              </div>
            </div>
          </section>
        </main>
      ) : !familyId ? (
        <main className="workspace workspace-single workspace-native workspace-onboarding">
          <section className="workspace-stage">
            <>
              {error ? <div className="panel error">{error}</div> : null}
              <OnboardingPage token={token} onComplete={handleOnboardingComplete} />
            </>
          </section>
        </main>
      ) : validatingFamily ? (
        <main className="workspace workspace-single workspace-native workspace-status">
          <section className="workspace-stage">
            <div className="content-page-shell status-page-shell">
              <div className="panel">正在校验家庭档案...</div>
            </div>
          </section>
        </main>
      ) : tab === 'today' ? (
        <main className="workspace workspace-home">
          {error ? <div className="panel error">{error}</div> : null}
          <section className="workspace-stage workspace-home-stage">
            <HomePage
              token={token}
              familyId={familyId}
              familySummary={familySummary}
              actionContext={actionContext}
              lowStim={lowStim}
              onNavigate={setTab}
              onActionContextChange={handleActionContextChange}
            />
          </section>
        </main>
      ) : (
        <main className="workspace workspace-native">
          {error ? <div className="panel error">{error}</div> : null}
          <div className="workspace-layout workspace-layout-single">
            <section className="workspace-stage">
              <div className="workspace-inline-nav">
                <div className="workspace-nav-header">
                  <div>
                    <p className="eyebrow">Secondary Nav</p>
                    <h2>次级导航</h2>
                  </div>
                  <p className="workspace-nav-copy">首页承担主入口分流；这里保留所有页面的直接跳转。</p>
                </div>
                <div className="workspace-sidebar-summary">
                  <span className="workspace-sidebar-label">当前家庭</span>
                  <strong>{familySummary?.family.name ?? `家庭 #${familyId}`}</strong>
                  <span>{lowStim ? '低刺激模式已开启，可随时从首页或页面内继续使用。' : '从首页先选入口，再进入具体动作页。'}</span>
                </div>
                <FlowTabs currentTab={tab} reviewReady={Boolean(actionContext)} onChange={setTab} />
              </div>

              <div className="workspace-stage-header">
                <div>
                  <p className="eyebrow">Current View</p>
                  <h2>
                    {tab === 'scripts'
                      ? '高摩擦支持'
                      : tab === 'plan'
                        ? '训练方案'
                        : tab === 'review'
                          ? '行动复盘'
                          : '家庭档案'}
                  </h2>
                </div>
                <p className="workspace-nav-copy">
                  {tab === 'scripts'
                    ? '知道现场卡住时，直接进入预设和三步支援。'
                    : tab === 'plan'
                      ? '直接查看今天任务、当前重点和最近反馈。'
                      : tab === 'review'
                        ? '记录结果、触发器和下一次保留动作。'
                        : '用设置页方式查看和维护家庭资料。'}
                </p>
              </div>

              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={tab}
                  className="workspace-secondary-motion-shell"
                  initial={secondaryContentMotion.initial}
                  animate={secondaryContentMotion.animate}
                  exit={secondaryContentMotion.exit}
                  transition={secondaryContentMotion.transition}
                >
                  {renderSecondaryPage(tab)}
                </motion.div>
              </AnimatePresence>
            </section>
          </div>
        </main>
      )}

      {token ? (
        <MicroRespiteModal
          open={respiteOpen}
          token={token}
          familyId={familyId}
          onClose={() => setRespiteOpen(false)}
        />
      ) : null}
    </div>
  );
}
