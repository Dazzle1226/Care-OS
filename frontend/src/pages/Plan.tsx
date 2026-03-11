import { TrainingPlanWorkspace } from '../components/TrainingPlanWorkspace';
import type { ActionFlowContext, CareTab } from '../lib/flow';

interface Props {
  token: string;
  familyId: number | null;
  onNavigate: (tab: CareTab) => void;
  onActionContextChange: (context: ActionFlowContext | null) => void;
}

export function PlanPage({ token, familyId, onNavigate, onActionContextChange }: Props) {
  return (
    <div className="grid">
      <TrainingPlanWorkspace
        token={token}
        familyId={familyId}
        onNavigate={onNavigate}
        onActionContextChange={onActionContextChange}
      />
    </div>
  );
}
