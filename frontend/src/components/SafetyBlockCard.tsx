import type { SafetyBlockResponse } from '../lib/types';

interface Props {
  block: SafetyBlockResponse;
  lowStim?: boolean;
  onToggleLowStim?: () => void;
}

const severityLabel: Record<SafetyBlockResponse['severity'], string> = {
  high_risk: '高风险阻断',
  conflict: '禁忌冲突阻断',
  quality: '安全转向'
};

export function SafetyBlockCard({ block, lowStim = false, onToggleLowStim }: Props) {
  return (
    <div className={`panel crisis-card safety-card severity-${block.severity}`}>
      <div className="crisis-card-top">
        <div>
          <p className="eyebrow">安全转向</p>
          <h3>{severityLabel[block.severity]}</h3>
          <p className="error">{block.block_reason}</p>
        </div>
        {block.low_stim_recommended && onToggleLowStim ? (
          <button className="btn secondary" type="button" onClick={onToggleLowStim}>
            {lowStim ? '低刺激已开启' : '切到低刺激模式'}
          </button>
        ) : null}
      </div>

      <div className="crisis-card-grid">
        <div className="crisis-card-section">
          <p className="label">现在先做</p>
          <ol className="list">
            {block.safe_next_steps.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>

        <div className="crisis-card-section">
          <p className="label">不要做</p>
          <ul className="list">
            {block.do_not_do.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="crisis-card-section full-span">
          <p className="label">直接可说的话</p>
          <blockquote className="quote-box">“{block.say_this_now}”</blockquote>
        </div>

        <div className="crisis-card-section">
          <p className="label">退场方案</p>
          <ol className="list">
            {block.exit_plan.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>

        <div className="crisis-card-section">
          <p className="label">求助</p>
          <ul className="list">
            {block.help_now.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      {block.conflict_explanation ? (
        <div className="safety-explain">
          <p className="label">为什么被阻断</p>
          <p>{block.conflict_explanation}</p>
        </div>
      ) : null}

      {block.alternatives.length ? (
        <div className="safety-explain">
          <p className="label">替代方案</p>
          <ul className="list">
            {block.alternatives.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="safety-explain">
        <p className="label">联系人消息模板</p>
        <pre>{block.emergency_contact_template}</pre>
      </div>
    </div>
  );
}
