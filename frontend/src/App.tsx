import { useState } from 'react';
import { useActionMenus } from './ui/useActionMenus';
import { useApiClient } from './api/ApiProvider';
import { CaseWorkspace, SessionStatus } from './cases/CaseWorkspace';
import { ActivityProvider, ActivityCenter } from './cases/ActivityCenter';
import { SettingsModal } from './settings/SettingsModal';

export function App() {
  return <ActivityProvider><Application /></ActivityProvider>;
}

function Application() {
  useActionMenus();
  const client = useApiClient();
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <>
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <div className="app-shell">
        <header className="app-header">
          <a className="brand" href="#workspace" aria-label="EVORA workspace">
            <svg width="28" height="30" viewBox="0 0 28 30" fill="none" aria-hidden="true">
              <path d="M4 3h20M4 15h15M4 27h20M4 3v24" stroke="currentColor" strokeWidth="3" /><circle cx="23" cy="15" r="3" fill="currentColor" />
            </svg>
            EVORA
          </a>
          <div className="header-actions">
            {client.hasToken() && <ActivityCenter />}
            <button type="button" className="header-settings" onClick={() => setSettingsOpen(true)} aria-haspopup="dialog" aria-label="Settings"><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m9 3-1 3-3 1-2 3 2 2-1 3 3 2 1 4h4l1-3 3-1 3-3-2-2 1-3-3-2-1-4H9Z"/><circle cx="10" cy="12" r="3"/></svg><span>Settings</span></button>
            <SessionStatus />
          </div>
        </header>
        <main id="workspace" tabIndex={-1}>
          <CaseWorkspace />
        </main>
      </div>
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </>
  );
}
