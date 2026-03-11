import { sanitizeDisplayText } from '../lib/displayText';
import type { FrictionSupportPlan, RiskLevel } from '../lib/types';

interface Props {
  plan: FrictionSupportPlan;
  riskLevel?: RiskLevel;
  lowStim: boolean;
  onToggleLowStim: () => void;
}

const riskLabel: Record<RiskLevel, string> = {
  green: '低风险',
  yellow: '中风险',
  red: '高风险'
};

export function FrictionCrisisCard({ plan, riskLevel = 'yellow', lowStim, onToggleLowStim }: Props) {
  return (
    <div className="panel crisis-card friction-crisis-card">
      <div className="crisis-card-top">
        <div>
          <p className="eyebrow">锁屏应急卡</p>
          <h3>{sanitizeDisplayText(plan.crisis_card.title)}</h3>
          <p className="muted">{sanitizeDisplayText(plan.headline)}</p>
        </div>
        <div className="crisis-card-actions">
          <span className={`status-pill ${riskLevel === 'red' ? 'warning' : ''}`}>{riskLabel[riskLevel]}</span>
          <button className="btn secondary" type="button" onClick={onToggleLowStim}>
            {lowStim ? '退出低刺激模式' : '一键低刺激'}
          </button>
        </div>
      </div>

      <div className="chip-row">
        {plan.crisis_card.badges.map((item) => (
          <span key={item} className="info-chip soft">
            {item}
          </span>
        ))}
      </div>

      <div className="crisis-card-grid">
        <div className="crisis-card-section">
          <p className="label">先做什么</p>
          <ol className="list">
            {plan.crisis_card.first_do.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>

        <div className="crisis-card-section">
          <p className="label">不要做什么</p>
          <ul className="list">
            {plan.crisis_card.donts.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="crisis-card-section full-span">
          <p className="label">直接可说的话</p>
          <div className="quote-stack">
            {plan.crisis_card.say_this.map((item) => (
              <blockquote key={item} className="quote-box">
                “{item}”
              </blockquote>
            ))}
          </div>
        </div>

        <div className="crisis-card-section">
          <p className="label">退场方案</p>
          <ol className="list">
            {plan.crisis_card.exit_plan.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>

        <div className="crisis-card-section">
          <p className="label">求助</p>
          <ul className="list">
            {plan.crisis_card.help_now.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="low-stim-strip">
        <strong>{sanitizeDisplayText(plan.low_stim_mode.headline)}</strong>
        <ul className="list">
          {plan.low_stim_mode.actions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
