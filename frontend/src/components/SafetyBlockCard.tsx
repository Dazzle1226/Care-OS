import type { SafetyBlockResponse } from '../lib/types';

export function SafetyBlockCard({ block }: { block: SafetyBlockResponse }) {
  return (
    <div className="panel" style={{ borderColor: 'var(--danger)' }}>
      <h3>安全阻断页</h3>
      <p className="error">{block.block_reason}</p>
      <p className="label">环境安全清单</p>
      <ul className="list">
        {block.environment_checklist.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="label">紧急建议</p>
      <ul className="list">
        {block.emergency_guidance.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="label">联系人消息模板</p>
      <pre>{block.emergency_contact_template}</pre>
    </div>
  );
}
