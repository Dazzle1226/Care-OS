import { useState } from 'react';

import { PlanPanel } from '../components/PlanPanel';
import { SafetyBlockCard } from '../components/SafetyBlockCard';
import { generatePlan } from '../lib/api';
import type { PlanGenerateResponse } from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
}

export function PlanPage({ token, familyId }: Props) {
  const [scenario, setScenario] = useState('transition');
  const [freeText, setFreeText] = useState('');
  const [result, setResult] = useState<PlanGenerateResponse | null>(null);
  const [error, setError] = useState('');

  const run = async () => {
    if (!familyId) {
      setError('请先创建家庭。');
      return;
    }
    setError('');
    try {
      const data = await generatePlan(token, {
        family_id: familyId,
        context: 'manual',
        scenario,
        manual_trigger: true,
        free_text: freeText,
        high_risk_selected: false
      });
      setResult(data);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div>
      <div className="panel">
        <h3>48 小时行动计划生成</h3>
        <div className="grid two">
          <label>
            <span className="label">优先场景</span>
            <select className="input" value={scenario} onChange={(e) => setScenario(e.target.value)}>
              <option value="transition">transition</option>
              <option value="bedtime">bedtime</option>
              <option value="homework">homework</option>
              <option value="outing">outing</option>
            </select>
          </label>
          <label>
            <span className="label">补充说明</span>
            <input className="input" value={freeText} onChange={(e) => setFreeText(e.target.value)} />
          </label>
        </div>
        <button className="btn" onClick={run}>生成计划</button>
      </div>

      {result?.blocked && result.safety_block ? <SafetyBlockCard block={result.safety_block} /> : null}
      {!result?.blocked && result?.plan ? <PlanPanel plan={result.plan} /> : null}
      {error ? <div className="panel error">{error}</div> : null}
    </div>
  );
}
