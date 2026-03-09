import { useEffect, useMemo, useState } from 'react';

import { login } from './lib/api';
import type { OnboardingSummary } from './lib/types';
import { FamilyPage } from './pages/Family';
import { HomePage } from './pages/Home';
import { OnboardingPage } from './pages/Onboarding';
import { PlanPage } from './pages/Plan';
import { ReviewPage } from './pages/Review';
import { ScriptsPage } from './pages/Scripts';

type Tab = 'today' | 'scripts' | 'plan' | 'review' | 'family';

const tabs: { key: Tab; label: string }[] = [
  { key: 'today', label: '今天' },
  { key: 'scripts', label: '高摩擦' },
  { key: 'plan', label: '计划' },
  { key: 'review', label: '复盘' },
  { key: 'family', label: '家庭' }
];

export default function App() {
  const [tab, setTab] = useState<Tab>('today');
  const [identifier, setIdentifier] = useState(localStorage.getItem('care_os_identifier') ?? 'demo@careos');
  const [token, setToken] = useState(localStorage.getItem('care_os_token') ?? '');
  const [familyId, setFamilyId] = useState<number | null>(
    Number(localStorage.getItem('care_os_family_id') ?? '') || null
  );
  const [familySummary, setFamilySummary] = useState<OnboardingSummary | null>(null);
  const [showCompletionCta, setShowCompletionCta] = useState(false);
  const [lowStim, setLowStim] = useState(false);
  const [error, setError] = useState('');

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

  const activePage = useMemo(() => {
    if (!token) return null;
    if (tab === 'today') return <HomePage token={token} familyId={familyId} />;
    if (tab === 'plan') return <PlanPage token={token} familyId={familyId} />;
    if (tab === 'scripts') return <ScriptsPage token={token} familyId={familyId} />;
    if (tab === 'review') return <ReviewPage token={token} familyId={familyId} />;
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
  }, [tab, token, familyId, familySummary, showCompletionCta]);

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
    setFamilySummary(summary);
    setFamilyId(summary.family.family_id);
    setTab('family');
    setShowCompletionCta(true);
  };

  return (
    <div className="app">
      <div className="topbar">
        <div>
          <div className="brand">Care OS Pro Max</div>
          <div className="tagline">ASD 家庭照护操作系统 · 48h 降负荷行动流</div>
        </div>
        <button className="btn secondary" onClick={() => setLowStim((v) => !v)}>
          {lowStim ? '退出低刺激模式' : '低刺激模式'}
        </button>
      </div>

      {!token ? (
        <div className="panel">
          <h3>Demo 登录</h3>
          <label>
            <span className="label">账号标识</span>
            <input className="input" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
          </label>
          <button className="btn" onClick={doLogin}>登录</button>
          {error ? <div className="error">{error}</div> : null}
        </div>
      ) : !familyId ? (
        <OnboardingPage token={token} onComplete={handleOnboardingComplete} />
      ) : (
        <>
          <div className="tabs">
            {tabs.map((item) => (
              <button
                key={item.key}
                className={`tab-btn ${tab === item.key ? 'active' : ''}`}
                onClick={() => setTab(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          {activePage}
        </>
      )}
    </div>
  );
}
