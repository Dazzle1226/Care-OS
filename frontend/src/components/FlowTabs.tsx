import type { ReactNode } from 'react';

import { careTabs, type CareTab } from '../lib/flow';

interface Props {
  currentTab: CareTab;
  reviewReady: boolean;
  onChange: (tab: CareTab) => void;
}

type NavigationTab = (typeof careTabs)[number] & { key: Exclude<CareTab, 'family'> };

const tabIcons: Record<Exclude<CareTab, 'family'>, ReactNode> = {
  today: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M7 3.8v3.1M17 3.8v3.1M4.8 9.2h14.4M6.4 20.2h11.2a1.9 1.9 0 0 0 1.9-1.9V7.7a1.9 1.9 0 0 0-1.9-1.9H6.4a1.9 1.9 0 0 0-1.9 1.9v10.6a1.9 1.9 0 0 0 1.9 1.9Z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  ),
  scripts: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M6.2 8.2h11.6M6.2 12h8.2M6.2 15.8h6.1M5.7 20h12.6a1.7 1.7 0 0 0 1.7-1.7V5.7A1.7 1.7 0 0 0 18.3 4H5.7A1.7 1.7 0 0 0 4 5.7v12.6A1.7 1.7 0 0 0 5.7 20Z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  ),
  plan: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M5 18.8h14M7.2 15.2l3-3 2.2 2.2 4.4-5.1"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <circle cx="7.2" cy="15.2" r="1.2" fill="currentColor" />
      <circle cx="10.2" cy="12.2" r="1.2" fill="currentColor" />
      <circle cx="12.4" cy="14.4" r="1.2" fill="currentColor" />
      <circle cx="16.8" cy="9.3" r="1.2" fill="currentColor" />
    </svg>
  ),
  review: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M7 18.2h10M8.1 14.8h7.8M8.1 11.3h7.8M8.1 7.8h5.1M6.2 20h11.6a1.8 1.8 0 0 0 1.8-1.8V5.8A1.8 1.8 0 0 0 17.8 4H6.2a1.8 1.8 0 0 0-1.8 1.8v12.4A1.8 1.8 0 0 0 6.2 20Z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  )
};

export function FlowTabs({ currentTab, reviewReady, onChange }: Props) {
  const navigationTabs = careTabs.filter((item): item is NavigationTab => item.key !== 'family');

  return (
    <div className="flow-tabs" role="tablist" aria-label="核心行动流导航">
      {navigationTabs.map((item) => (
        <button
          key={item.key}
          type="button"
          className={`flow-tab-btn ${item.key === 'today' ? 'is-primary-nav' : 'is-secondary-nav'} ${
            currentTab === item.key ? 'active' : ''
          }`}
          onClick={() => onChange(item.key)}
          title={item.hint}
        >
          <div className="flow-tab-leading">
            <span className="flow-tab-icon" aria-hidden="true">
              {tabIcons[item.key]}
            </span>
            <span className="flow-tab-label">{item.label}</span>
          </div>
          <div className="flow-tab-meta">
            {item.key === 'today' ? (
              <span className="flow-tab-state">主入口</span>
            ) : item.key === 'review' && reviewReady ? (
              <span className="flow-tab-state">待复盘</span>
            ) : currentTab === item.key ? (
              <span className="flow-tab-state">当前</span>
            ) : null}
          </div>
        </button>
      ))}
    </div>
  );
}
