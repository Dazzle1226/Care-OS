import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import { registerSW } from './pwa/registerSW';
import './styles/app.css';

registerSW();

type RootErrorBoundaryProps = {
  children: React.ReactNode;
};

type RootErrorBoundaryState = {
  hasError: boolean;
};

class RootErrorBoundary extends React.Component<RootErrorBoundaryProps, RootErrorBoundaryState> {
  state: RootErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.error('Root render failed', error);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleResetStorage = () => {
    try {
      window.localStorage.removeItem('care_os_token');
      window.localStorage.removeItem('care_os_identifier');
      window.localStorage.removeItem('care_os_family_id');
      window.localStorage.removeItem('care_os_action_flow_context');
    } catch {
      // Ignore storage reset failures and still try to reload.
    }

    window.location.reload();
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <main className="workspace workspace-single">
        <section className="workspace-stage">
          <div className="panel auth-panel">
            <p className="eyebrow">Recovery</p>
            <h3>前端已进入恢复模式</h3>
            <p className="workspace-intro">刚刚发生了运行时异常。你可以先刷新，如果仍不显示，再清理本地缓存后重试。</p>
            <div className="stack-actions">
              <button className="btn" type="button" onClick={this.handleReload}>
                刷新页面
              </button>
              <button className="btn btn-secondary" type="button" onClick={this.handleResetStorage}>
                清理本地状态并刷新
              </button>
            </div>
          </div>
        </section>
      </main>
    );
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </React.StrictMode>
);
