import { useState } from 'react';

import { SafetyBlockCard } from '../components/SafetyBlockCard';
import { generateFrictionSupport, submitFrictionSupportFeedback } from '../lib/api';
import type {
  FrictionChildState,
  FrictionScenario,
  FrictionSupportFeedbackResponse,
  FrictionSupportGenerateResponse
} from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
}

type SupportAvailability = 'none' | 'one' | 'two_plus';
type SensoryLevel = 'none' | 'light' | 'medium' | 'heavy';
type FeedbackEffectiveness = 'helpful' | 'somewhat' | 'not_helpful';
type ChildStateAfter = 'settled' | 'partly_settled' | 'still_escalating';
type CaregiverStateAfter = 'calmer' | 'same' | 'more_overloaded';

function parseEnvChanges(value: string): string[] {
  return value
    .split(/[,\n，]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 4);
}

const riskLabel: Record<string, string> = {
  green: '低',
  yellow: '中',
  red: '高'
};

export function ScriptsPage({ token, familyId }: Props) {
  const [scenario, setScenario] = useState<FrictionScenario>('transition');
  const [childState, setChildState] = useState<FrictionChildState>('transition_block');
  const [sensoryOverloadLevel, setSensoryOverloadLevel] = useState<SensoryLevel>('medium');
  const [transitionDifficulty, setTransitionDifficulty] = useState(8);
  const [meltdownCount, setMeltdownCount] = useState(2);
  const [caregiverStress, setCaregiverStress] = useState(8);
  const [caregiverFatigue, setCaregiverFatigue] = useState(7);
  const [caregiverSleepQuality, setCaregiverSleepQuality] = useState(4);
  const [supportAvailable, setSupportAvailable] = useState<SupportAvailability>('one');
  const [confidenceToFollowPlan, setConfidenceToFollowPlan] = useState(4);
  const [envChangesInput, setEnvChangesInput] = useState('出门, 学校临时变化');
  const [freeText, setFreeText] = useState('');

  const [result, setResult] = useState<FrictionSupportGenerateResponse | null>(null);
  const [feedbackResult, setFeedbackResult] = useState<FrictionSupportFeedbackResponse | null>(null);
  const [effectiveness, setEffectiveness] = useState<FeedbackEffectiveness>('somewhat');
  const [childStateAfter, setChildStateAfter] = useState<ChildStateAfter>('partly_settled');
  const [caregiverStateAfter, setCaregiverStateAfter] = useState<CaregiverStateAfter>('same');
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    if (!familyId) {
      setError('请先创建家庭。');
      return;
    }

    setLoading(true);
    setError('');
    setFeedbackResult(null);
    try {
      const data = await generateFrictionSupport(token, {
        family_id: familyId,
        scenario,
        child_state: childState,
        sensory_overload_level: sensoryOverloadLevel,
        transition_difficulty: transitionDifficulty,
        meltdown_count: meltdownCount,
        caregiver_stress: caregiverStress,
        caregiver_fatigue: caregiverFatigue,
        caregiver_sleep_quality: caregiverSleepQuality,
        support_available: supportAvailable,
        confidence_to_follow_plan: confidenceToFollowPlan,
        env_changes: parseEnvChanges(envChangesInput),
        free_text: freeText,
        high_risk_selected: false
      });
      setResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const submitFeedback = async () => {
    if (!familyId || !result?.incident_id || !result.support) {
      setError('请先生成高摩擦支援方案。');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const data = await submitFrictionSupportFeedback(token, {
        family_id: familyId,
        incident_id: result.incident_id,
        source_card_ids: result.support.source_card_ids,
        effectiveness,
        child_state_after: childStateAfter,
        caregiver_state_after: caregiverStateAfter,
        notes: feedbackNotes
      });
      setFeedbackResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="panel">
        <p className="eyebrow">High Friction</p>
        <h3>高摩擦时刻支援</h3>
        <p className="muted">输入孩子、家长和环境状态后，系统会生成三步行动、可直接照读的话术、退场方案与短时喘息建议。</p>
        <div className="grid two">
          <label>
            <span className="label">场景</span>
            <select className="input" value={scenario} onChange={(e) => setScenario(e.target.value as FrictionScenario)}>
              <option value="transition">过渡困难</option>
              <option value="bedtime">睡前拉扯</option>
              <option value="homework">作业冲突</option>
              <option value="outing">外出失序</option>
              <option value="meltdown">情绪崩溃</option>
            </select>
          </label>
          <label>
            <span className="label">孩子当前状态</span>
            <select className="input" value={childState} onChange={(e) => setChildState(e.target.value as FrictionChildState)}>
              <option value="transition_block">卡在过渡点</option>
              <option value="emotional_wave">情绪波动</option>
              <option value="sensory_overload">感官过载</option>
              <option value="conflict">冲突升级</option>
              <option value="meltdown">已经崩溃</option>
            </select>
          </label>
          <label>
            <span className="label">感官负荷</span>
            <select
              className="input"
              value={sensoryOverloadLevel}
              onChange={(e) => setSensoryOverloadLevel(e.target.value as SensoryLevel)}
            >
              <option value="none">无</option>
              <option value="light">轻微</option>
              <option value="medium">中等</option>
              <option value="heavy">严重</option>
            </select>
          </label>
          <label>
            <span className="label">可用支持</span>
            <select
              className="input"
              value={supportAvailable}
              onChange={(e) => setSupportAvailable(e.target.value as SupportAvailability)}
            >
              <option value="none">无人可接手</option>
              <option value="one">有 1 位支持者</option>
              <option value="two_plus">有 2 位以上支持者</option>
            </select>
          </label>
          <label>
            <span className="label">过渡难度：{transitionDifficulty} / 10</span>
            <input
              className="input"
              type="range"
              min="0"
              max="10"
              value={transitionDifficulty}
              onChange={(e) => setTransitionDifficulty(Number(e.target.value))}
            />
          </label>
          <label>
            <span className="label">今日冲突/崩溃：{meltdownCount}</span>
            <input
              className="input"
              type="range"
              min="0"
              max="3"
              value={meltdownCount}
              onChange={(e) => setMeltdownCount(Number(e.target.value))}
            />
          </label>
          <label>
            <span className="label">家长压力：{caregiverStress} / 10</span>
            <input
              className="input"
              type="range"
              min="0"
              max="10"
              value={caregiverStress}
              onChange={(e) => setCaregiverStress(Number(e.target.value))}
            />
          </label>
          <label>
            <span className="label">家长疲劳：{caregiverFatigue} / 10</span>
            <input
              className="input"
              type="range"
              min="0"
              max="10"
              value={caregiverFatigue}
              onChange={(e) => setCaregiverFatigue(Number(e.target.value))}
            />
          </label>
          <label>
            <span className="label">睡眠质量：{caregiverSleepQuality} / 10</span>
            <input
              className="input"
              type="range"
              min="0"
              max="10"
              value={caregiverSleepQuality}
              onChange={(e) => setCaregiverSleepQuality(Number(e.target.value))}
            />
          </label>
          <label>
            <span className="label">执行信心：{confidenceToFollowPlan} / 10</span>
            <input
              className="input"
              type="range"
              min="0"
              max="10"
              value={confidenceToFollowPlan}
              onChange={(e) => setConfidenceToFollowPlan(Number(e.target.value))}
            />
          </label>
        </div>

        <label className="support-textarea">
          <span className="label">环境变化（用逗号分隔）</span>
          <textarea
            className="input"
            rows={2}
            value={envChangesInput}
            onChange={(e) => setEnvChangesInput(e.target.value)}
            placeholder="例如：外出、学校临时通知、来客"
          />
        </label>

        <label className="support-textarea">
          <span className="label">补充说明</span>
          <textarea
            className="input"
            rows={3}
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            placeholder="例如：刚从学校回来，一提换衣服就大哭。"
          />
        </label>

        <button className="btn" onClick={run} disabled={loading}>
          {loading ? '生成中…' : '生成高摩擦支援'}
        </button>
      </div>

      {result?.blocked && result.safety_block ? <SafetyBlockCard block={result.safety_block} /> : null}

      {!result?.blocked && result?.support ? (
        <>
          <div className="panel">
            <p className="eyebrow">即时摘要</p>
            <h3>{result.support.headline}</h3>
            <p>{result.support.situation_summary}</p>
            <div className="chip-row">
              <span className="info-chip">风险 {riskLabel[result.risk?.risk_level ?? 'yellow'] ?? '中'}</span>
              {result.support.child_signals.map((item) => (
                <span key={item} className="info-chip">{item}</span>
              ))}
              {result.support.caregiver_signals.map((item) => (
                <span key={item} className="info-chip">{item}</span>
              ))}
            </div>
          </div>

          <div className="panel">
            <p className="eyebrow">三步行动</p>
            <div className="support-step-grid">
              {result.support.action_plan.map((step, index) => (
                <div key={`${step.title}-${index}`} className="support-step-card">
                  <div className="label">步骤 {index + 1}</div>
                  <h4>{step.title}</h4>
                  <p>{step.action}</p>
                  <p><strong>可直接说：</strong>{step.parent_script}</p>
                  <p className="muted">{step.why_it_fits}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid two">
            <div className="panel">
              <p className="eyebrow">语音引导</p>
              <ol className="list">
                {result.support.voice_guidance.map((item) => <li key={item}>{item}</li>)}
              </ol>
            </div>
            <div className="panel">
              <p className="eyebrow">退场方案</p>
              <ol className="list">
                {result.support.exit_plan.map((item) => <li key={item}>{item}</li>)}
              </ol>
            </div>
          </div>

          <div className="grid two">
            <div className="panel">
              <p className="eyebrow">微喘息建议</p>
              <h3>{result.support.respite_suggestion.title}</h3>
              <p>{result.support.respite_suggestion.summary}</p>
              <p><strong>建议时长：</strong>{result.support.respite_suggestion.duration_minutes} 分钟</p>
              <p className="muted">{result.support.respite_suggestion.support_plan}</p>
            </div>
            <div className="panel">
              <p className="eyebrow">个性化提示</p>
              <ul className="list">
                {result.support.personalized_strategies.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          </div>

          <div className="panel">
            <p className="eyebrow">家校协作模板</p>
            <blockquote className="quote-box">{result.support.school_message}</blockquote>
            <p className="muted support-citation">引用策略卡：{result.support.citations.join(', ')}</p>
          </div>

          <div className="panel">
            <p className="eyebrow">执行后反馈</p>
            <p>{result.support.feedback_prompt}</p>
            <div className="grid two">
              <label>
                <span className="label">这次建议是否有效</span>
                <select
                  className="input"
                  value={effectiveness}
                  onChange={(e) => setEffectiveness(e.target.value as FeedbackEffectiveness)}
                >
                  <option value="helpful">有效</option>
                  <option value="somewhat">部分有效</option>
                  <option value="not_helpful">无效</option>
                </select>
              </label>
              <label>
                <span className="label">孩子现在的状态</span>
                <select
                  className="input"
                  value={childStateAfter}
                  onChange={(e) => setChildStateAfter(e.target.value as ChildStateAfter)}
                >
                  <option value="settled">更稳定了</option>
                  <option value="partly_settled">稍微稳定</option>
                  <option value="still_escalating">还在升级</option>
                </select>
              </label>
              <label>
                <span className="label">家长现在的状态</span>
                <select
                  className="input"
                  value={caregiverStateAfter}
                  onChange={(e) => setCaregiverStateAfter(e.target.value as CaregiverStateAfter)}
                >
                  <option value="calmer">我更冷静了</option>
                  <option value="same">差不多</option>
                  <option value="more_overloaded">我更累了</option>
                </select>
              </label>
            </div>

            <label className="support-textarea">
              <span className="label">补充反馈</span>
              <textarea
                className="input"
                rows={3}
                value={feedbackNotes}
                onChange={(e) => setFeedbackNotes(e.target.value)}
                placeholder="例如：孩子能跟着进安静角落，但一提作业又开始抗拒。"
              />
            </label>

            <button className="btn" onClick={submitFeedback} disabled={submitting}>
              {submitting ? '提交中…' : '提交反馈'}
            </button>

            {feedbackResult ? (
              <div className="support-feedback-result">
                <strong>系统调整：</strong>{feedbackResult.next_adjustment}
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      {error ? <div className="panel error">{error}</div> : null}
    </div>
  );
}
