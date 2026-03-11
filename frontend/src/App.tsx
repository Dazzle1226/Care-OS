import { useEffect, useState } from 'react';

import { MicroRespiteModal } from './components/MicroRespiteModal';
import { FlowTabs } from './components/FlowTabs';
import { FAMILY_MISSING_EVENT, getOnboardingFamily, isFamilyNotFoundError, login } from './lib/api';
import { readActionFlowContext, type ActionFlowContext, type CareTab, writeActionFlowContext } from './lib/flow';
import type { OnboardingSummary } from './lib/types';
import { FamilyPage } from './pages/Family';
import { HomePage } from './pages/Home';
import { OnboardingPage } from './pages/Onboarding';
import { PlanPage } from './pages/Plan';
import { ReviewPage } from './pages/Review';
import { ScriptsPage } from './pages/Scripts';

export default function App() {
  const [tab, setTab] = useState<CareTab>('today');
  const [identifier, setIdentifier] = useState(localStorage.getItem('care_os_identifier') ?? 'demo@careos');
  const [token, setToken] = useState(localStorage.getItem('care_os_token') ?? '');
  const [familyId, setFamilyId] = useState<number | null>(
    Number(localStorage.getItem('care_os_family_id') ?? '') || null
  );
  const [familySummary, setFamilySummary] = useState<OnboardingSummary | null>(null);
  const [actionContext, setActionContext] = useState<ActionFlowContext | null>(() => readActionFlowContext());
  const [showCompletionCta, setShowCompletionCta] = useState(false);
  const [lowStim, setLowStim] = useState(false);
  const [respiteOpen, setRespiteOpen] = useState(false);
  const [error, setError] = useState('');
  const [validatingFamily, setValidatingFamily] = useState(Boolean(token && familyId));

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', lowStim ? 'low-stim' : 'normal');
  }, [lowStim]);

  useEffect(() => {
    if (token) localStorage.setItem('care_os_token', token);
  }, [token]);

  useEffect(() => {
    if (familyId) {
      localStorage.setItem('care_os_family_id', String(familyId));
      return;
    }
    localStorage.removeItem('care_os_family_id');
  }, [familyId]);

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
      localStorage.setItem('care_os_identifier', identifier);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleOnboardingComplete = (summary: OnboardingSummary) => {
    setError('');
    setFamilySummary(summary);
    setFamilyId(summary.family.family_id);
    setTab('family');
    setShowCompletionCta(true);
  };

  return (
    <div className="app">
      <div className="topbar">
        <div>
          <div className="brand">Care OS</div>
          <div className="tagline">照护导航：签到 → 行动 → 高摩擦支援 → 复盘</div>
        </div>
        <div className="topbar-actions">
          {familyId ? (
            <button
              className={`family-shortcut ${tab === 'family' ? 'active' : ''}`}
              type="button"
              onClick={() => setTab('family')}
            >
              <span className="family-shortcut-label">家庭档案</span>
              <strong>{familySummary?.family.name ?? `家庭 #${familyId}`}</strong>
              <span className="family-shortcut-hint">查看关键信息或修改详细档案</span>
            </button>
          ) : null}
          {familyId ? (
            <button className="btn secondary" type="button" onClick={() => setRespiteOpen(true)}>
              微喘息
            </button>
          ) : null}
          <button className="btn secondary" onClick={() => setLowStim((value) => !value)}>
            {lowStim ? '退出低刺激模式' : '低刺激模式'}
          </button>
        </div>
      </div>

      {!token ? (
        <div className="panel">
          <h3>演示登录</h3>
          <label>
            <span className="label">账号标识</span>
            <input className="input" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
          </label>
          <button className="btn" onClick={doLogin}>
            登录
          </button>
          {error ? <div className="error">{error}</div> : null}
        </div>
      ) : !familyId ? (
        <>
          {error ? <div className="panel error">{error}</div> : null}
          <OnboardingPage token={token} onComplete={handleOnboardingComplete} />
        </>
      ) : validatingFamily ? (
        <div className="panel">正在校验家庭档案...</div>
      ) : (
        <>
          {error ? <div className="panel error">{error}</div> : null}
          <FlowTabs currentTab={tab} reviewReady={Boolean(actionContext)} onChange={setTab} />

          {tab === 'today' ? (
            <HomePage
              token={token}
              familyId={familyId}
              onNavigate={setTab}
              onActionContextChange={handleActionContextChange}
            />
          ) : null}

          {tab === 'scripts' ? (
            <ScriptsPage
              token={token}
              familyId={familyId}
              lowStim={lowStim}
              onToggleLowStim={() => setLowStim((value) => !value)}
              onNavigate={setTab}
              onActionContextChange={handleActionContextChange}
            />
          ) : null}

          {tab === 'plan' ? (
            <PlanPage
              token={token}
              familyId={familyId}
              onNavigate={setTab}
              onActionContextChange={handleActionContextChange}
            />
          ) : null}

          {tab === 'review' ? (
            <ReviewPage
              token={token}
              familyId={familyId}
              actionContext={actionContext}
              onNavigate={setTab}
              onActionContextChange={handleActionContextChange}
            />
          ) : null}

          {tab === 'family' ? (
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
          ) : null}
        </>
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
