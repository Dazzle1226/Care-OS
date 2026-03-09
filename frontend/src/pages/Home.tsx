import { useEffect, useState } from 'react';

import { CheckinCard, type CheckinFormPayload } from '../components/CheckinCard';
import { MicroRespiteModal } from '../components/MicroRespiteModal';
import { RiskLight } from '../components/RiskLight';
import { getTodayCheckin, postCheckin } from '../lib/api';
import type { CheckinResponse, CheckinTodayStatus } from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
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
    today_one_thing: data.today_one_thing,
    action_plan: data.action_plan
  };
}

export function HomePage({ token, familyId }: Props) {
  const today = getLocalDateString();
  const [status, setStatus] = useState<CheckinTodayStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [respiteOpen, setRespiteOpen] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    if (!familyId) {
      setStatus(null);
      setModalOpen(false);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setError('');
    getTodayCheckin(token, familyId, today)
      .then((data) => {
        if (cancelled) return;
        setStatus(data);
        const dismissed = localStorage.getItem(buildDismissKey(familyId, today)) === '1';
        setModalOpen(data.needs_checkin && !dismissed);
      })
      .catch((err) => {
        if (cancelled) return;
        setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [familyId, token, today]);

  const submit = async (payload: CheckinFormPayload) => {
    if (!familyId) {
      setError('请先在【家庭】页创建家庭。');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const data = await postCheckin(token, { ...payload, family_id: familyId });
      localStorage.setItem(buildDismissKey(familyId, today), '1');
      setStatus(toTodayStatus(familyId, data));
      setModalOpen(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const openCheckin = () => setModalOpen(true);

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

  return (
    <div className="grid">
      <div className="panel today-hero">
        <div>
          <p className="eyebrow">今日签到</p>
          <h2>先看状态，再做决定</h2>
          <p className="muted">每天第一次打开时快速签到，系统会即时生成今日行动卡片。</p>
        </div>
        <div className="hero-side">
          <span className="date-pill">{today}</span>
          {familyId ? (
            <button className="btn" type="button" onClick={openCheckin}>
              {status?.needs_checkin === false ? '修改今日签到' : '开始签到'}
            </button>
          ) : null}
        </div>
      </div>

      {!familyId ? (
        <div className="panel">
          <h3>还没有家庭档案</h3>
          <p className="muted">请先到【家庭】页创建家庭，再开始每日签到。</p>
        </div>
      ) : null}

      {loading ? <div className="panel">正在读取今日签到状态...</div> : null}

      {familyId && !loading && status?.needs_checkin ? (
        <div className="panel empty-state">
          <p className="eyebrow">待完成</p>
          <h3>今天还没有签到</h3>
          <p className="muted">只需几个滑条和单选项，30 秒内拿到今日计划。</p>
          <button className="btn" type="button" onClick={openCheckin}>
            现在签到
          </button>
        </div>
      ) : null}

      {status?.risk ? <RiskLight level={status.risk.risk_level} /> : null}

      {familyId && !status?.needs_checkin && status?.action_plan ? (
        <div className="dashboard-grid">
          <div className="panel summary-panel">
            <p className="eyebrow">计划概览</p>
            <h3>{status.action_plan.headline}</h3>
            <p>{status.action_plan.summary}</p>
            <div className="chip-row">
              {status.action_plan.plan_overview.map((item) => (
                <span key={item} className="info-chip">
                  {item}
                </span>
              ))}
            </div>
            <div className="summary-meta">
              <p>
                <strong>今日一件事：</strong>
                {status.today_one_thing}
              </p>
              <p className="muted">风险解释：{status.risk?.reasons.join('；')}</p>
            </div>
          </div>

          <div className="panel action-plan-panel">
            <p className="eyebrow">今日行动卡片</p>
            <div className="action-block">
              <h4>3 步行动</h4>
              <ol className="list">
                {status.action_plan.three_step_action.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ol>
            </div>

            <div className="action-block">
              <h4>家长话术</h4>
              <p className="quote-box">“{status.action_plan.parent_phrase}”</p>
            </div>

            <div className="action-block">
              <h4>退场方案</h4>
              <ul className="list">
                {status.action_plan.meltdown_fallback.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="action-block">
              <h4>喘息安排</h4>
              <p>{status.action_plan.respite_suggestion}</p>
              <button className="btn secondary" type="button" onClick={() => setRespiteOpen(true)}>
                开始微喘息
              </button>
            </div>
          </div>
        </div>
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
