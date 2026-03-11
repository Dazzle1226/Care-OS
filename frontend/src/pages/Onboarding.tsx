import { useState } from 'react';

import { ProfileForm } from '../components/ProfileForm';
import { completeOnboarding } from '../lib/api';
import { createEmptyProfileForm } from '../lib/profileForm';
import type { OnboardingSetupPayload, OnboardingSummary } from '../lib/types';

interface Props {
  token: string;
  onComplete: (summary: OnboardingSummary) => void;
}

export function OnboardingPage({ token, onComplete }: Props) {
  const [mode, setMode] = useState<'welcome' | 'form'>('welcome');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState<OnboardingSetupPayload>(createEmptyProfileForm());

  const updateForm = (patch: Partial<OnboardingSetupPayload>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const runSample = async () => {
    setSaving(true);
    setError('');
    try {
      const summary = await completeOnboarding(token, { use_sample: true, timezone: 'Asia/Shanghai' });
      onComplete(summary);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const finishManual = async () => {
    setSaving(true);
    setError('');
    try {
      const summary = await completeOnboarding(token, form);
      onComplete(summary);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-shell onboarding-modal-shell" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className="modal-backdrop" />
      <div className="modal-card modal-card-wide onboarding-modal-card">
        <div className="grid">
          <section className="panel onboarding-hero">
            <div className="onboarding-copy">
              <p className="eyebrow">初次设置</p>
              <h2 id="onboarding-title">建档信息填写</h2>
              <p>
                第一次建档先填这些，其他信息都放在页面里稍后补充。填写时会停留在当前页面上的悬浮窗里完成。
              </p>
              <div className="onboarding-actions">
                <button
                  className="btn onboarding-primary"
                  type="button"
                  onClick={() => setMode('form')}
                >
                  开始建档
                </button>
                <button className="btn secondary onboarding-secondary" type="button" onClick={runSample} disabled={saving}>
                  {saving ? '正在载入示例…' : '选择示例家庭'}
                </button>
              </div>
              <p className="muted">只先填写最必要的信息；其他内容都可以之后继续补充，你之前补过的新项也会保留。</p>
            </div>
          </section>

          {mode === 'form' ? (
            <section className="panel onboarding-shell">
              <div className="onboarding-banner">
                <p className="eyebrow">建档信息填写</p>
                <h3>先完成“第一次建档先填这些”</h3>
                <p>点“继续”后会自动跳到下一页顶部。当前先以必填资料为主，后两层都可以稍后补充。</p>
              </div>

              <ProfileForm form={form} onChange={updateForm} />

              <div className="onboarding-footer">
                <p className="privacy-note">所有资料仅用于家庭支持计划与个性化建议，不会用于外部公开展示。</p>
                <div className="footer-actions">
                  <button className="btn secondary" type="button" onClick={() => setMode('welcome')}>
                    返回欢迎页
                  </button>
                  <button className="btn" type="button" onClick={finishManual} disabled={saving}>
                    {saving ? '正在生成家庭档案…' : '完成设置'}
                  </button>
                </div>
              </div>
            </section>
          ) : null}

          {error ? <div className="panel error">{error}</div> : null}
        </div>
      </div>
    </div>
  );
}
