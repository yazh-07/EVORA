import { useState } from 'react';
import { useActionMenus } from './ui/useActionMenus';
import { useApiClient } from './api/ApiProvider';
import { CaseWorkspace, SessionStatus } from './cases/CaseWorkspace';
import { ActivityProvider, ActivityCenter } from './cases/ActivityCenter';
import { SettingsModal, type SettingsSection } from './settings/SettingsModal';
import { UpdatesProvider, useUpdates } from './settings/Updates';

export function App() {
  return <UpdatesProvider><ActivityProvider><Application /></ActivityProvider></UpdatesProvider>;
}

function Application() {
  useActionMenus();
  const client = useApiClient();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>('appearance');
  const { state: updates } = useUpdates();
  return (
    <>
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <div className="app-shell">
        <header className="app-header">
          <a className="brand" href="#workspace" aria-label="EVORA workspace">
            <img src="/brand/icon.png" width="32" height="32" alt="" />
            EVORA
          </a>
          <div className="header-actions">
            {updates.data?.available && <button type="button" className="header-update" onClick={() => { setSettingsSection('updates'); setSettingsOpen(true); }}>Update available</button>}
            {client.hasToken() && <ActivityCenter />}
            <button type="button" className="header-settings" onClick={() => setSettingsOpen(true)} aria-haspopup="dialog" aria-label="Settings"><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><polygon points="9.09,4.98 9.92,2.22 14.08,2.22 14.91,4.98 14.91,4.98 17.45,3.61 20.39,6.55 19.02,9.09 19.02,9.09 21.78,9.92 21.78,14.08 19.02,14.91 19.02,14.91 20.39,17.45 17.45,20.39 14.91,19.02 14.91,19.02 14.08,21.78 9.92,21.78 9.09,19.02 9.09,19.02 6.55,20.39 3.61,17.45 4.98,14.91 4.98,14.91 2.22,14.08 2.22,9.92 4.98,9.09 4.98,9.09 3.61,6.55 6.55,3.61 9.09,4.98" strokeLinejoin="round"/><circle cx="12" cy="12" r="3"/></svg><span>Settings</span></button>
            <SessionStatus />
          </div>
        </header>
        <main id="workspace" tabIndex={-1}>
          <CaseWorkspace />
        </main>
      </div>
      {settingsOpen && <SettingsModal initialSection={settingsSection} onClose={() => { setSettingsOpen(false); setSettingsSection('appearance'); }} />}
    </>
  );
}
