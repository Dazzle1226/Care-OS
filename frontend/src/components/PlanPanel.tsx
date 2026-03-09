import type { Plan48hResponse } from '../lib/types';

export function PlanPanel({ plan }: { plan: Plan48hResponse }) {
  return (
    <div className="panel">
      <h3>48h 降负荷行动面板</h3>
      <p className="label">A. 今天不做什么</p>
      <ul className="list">{plan.today_cut_list.map((x) => <li key={x}>{x}</li>)}</ul>

      <p className="label">B. 场景优先级</p>
      <ul className="list">{plan.priority_scenarios.map((x) => <li key={x}>{x}</li>)}</ul>

      <p className="label">C. 微喘息排班</p>
      <ul className="list">
        {plan.respite_slots.map((slot, i) => (
          <li key={i}>{slot.duration_minutes} 分钟 · {slot.resource}</li>
        ))}
      </ul>

      <p className="label">D. 沟通模板</p>
      <ul className="list">
        {plan.messages.map((m, i) => (
          <li key={i}><strong>{m.target}</strong>：{m.text}</li>
        ))}
      </ul>

      <p className="label">E. 升级退场卡（3步）</p>
      <ol className="list">{plan.exit_card_3steps.map((x) => <li key={x}>{x}</li>)}</ol>

      <p className="label">策略卡引用</p>
      <div>{plan.citations.join(', ')}</div>
    </div>
  );
}
