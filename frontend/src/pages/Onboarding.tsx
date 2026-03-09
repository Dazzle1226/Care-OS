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
    <div className="grid">
      <section className="panel onboarding-hero">
        <div className="onboarding-copy">
          <p className="eyebrow">初次设置</p>
          <h2>先建完整家庭档案，再进入主功能</h2>
          <p>
            首次登录请尽量补齐孩子、家庭、健康、行为和支持网络信息。系统会根据这些资料生成更贴近家庭实际情况的建议。
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
          <p className="muted">能选择的地方都已预置常见选项；也可以随时补充新项，后续编辑时会继续保留。</p>
        </div>
        <div className="onboarding-highlight">
          <div className="welcome-stat">
            <strong>覆盖孩子与家长两侧信息</strong>
            <span>从诊断、健康到学校和家长压力，一次建好基础画像。</span>
          </div>
          <div className="welcome-stat">
            <strong>后续可持续更新</strong>
            <span>家庭页会保留编辑入口，孩子进展变化后可以随时改。</span>
          </div>
          <div className="welcome-stat">
            <strong>常见项 + 自定义补充</strong>
            <span>你补充过的新选项，下次打开档案编辑时会继续出现。</span>
          </div>
        </div>
      </section>

      {mode === 'form' ? (
        <section className="panel onboarding-shell">
          <div className="onboarding-section">
            <div>
              <p className="eyebrow">详细建档</p>
              <h3>尽量一次填清楚，后面系统会更省心</h3>
              <p className="muted">如果暂时不确定，可以先跳过某些文字说明，后续到家庭页继续补充。</p>
            </div>
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
  );
}
