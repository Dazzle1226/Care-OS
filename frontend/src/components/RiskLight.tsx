import type { RiskLevel } from '../lib/types';

const colorMap: Record<RiskLevel, string> = {
  green: 'var(--ok)',
  yellow: 'var(--warn)',
  red: 'var(--danger)'
};

const labelMap: Record<RiskLevel, string> = {
  green: '稳定',
  yellow: '需要留意',
  red: '高负荷'
};

export function RiskLight({ level }: { level: RiskLevel }) {
  return (
    <div className="panel" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: 999,
          display: 'inline-block',
          background: colorMap[level],
          boxShadow: `0 0 12px ${colorMap[level]}`
        }}
      />
      <strong>今日风险灯：{labelMap[level]}</strong>
    </div>
  );
}
