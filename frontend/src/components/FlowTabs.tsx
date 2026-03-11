import { careTabs, type CareTab } from '../lib/flow';

interface Props {
  currentTab: CareTab;
  reviewReady: boolean;
  onChange: (tab: CareTab) => void;
}

export function FlowTabs({ currentTab, reviewReady, onChange }: Props) {
  const navigationTabs = careTabs.filter((item) => item.key !== 'family');

  return (
    <div className="flow-tabs" role="tablist" aria-label="核心行动流导航">
      {navigationTabs.map((item, index) => (
        <button
          key={item.key}
          type="button"
          className={`flow-tab-btn ${currentTab === item.key ? 'active' : ''}`}
          onClick={() => onChange(item.key)}
        >
          <div className="flow-step-top">
            <h4>
              {index + 1}. {item.label}
            </h4>
            <span className={`status-chip ${currentTab === item.key ? 'active' : 'muted'}`}>
              {item.key === 'review' && reviewReady ? '待复盘' : currentTab === item.key ? '当前页面' : '打开'}
            </span>
          </div>
          <p className="muted">{item.hint}</p>
        </button>
      ))}
    </div>
  );
}
