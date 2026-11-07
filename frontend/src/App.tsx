import { useEffect, useState } from 'react';
import { CaseWorkspace, SessionStatus } from './cases/CaseWorkspace';
import { useApiClient } from './api/ApiProvider';
import { ActivityProvider, ActivityCenter } from './cases/ActivityCenter';
import { SettingsModal } from './settings/SettingsModal';

export function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('evora-theme');
        if (saved === 'light' || saved === 'dark') return saved;
      } catch {}
    }
    return 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.body.setAttribute('data-theme', theme);
    try { localStorage.setItem('evora-theme', theme); } catch {}
  }, [theme]);

  return (
    <button
      type="button"
      className="theme-toggle-btn"
      onClick={() => setTheme(curr => (curr === 'dark' ? 'light' : 'dark'))}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? 'Light mode' : 'Dark mode'}
    </button>
  );
}

export function App() {
  return <ActivityProvider><Application /></ActivityProvider>;
}

function Application() {
  const client = useApiClient();
  const [caseNavigation, setCaseNavigation] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <>
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <div className="app-shell">
        <header className="app-header">
          <a className="brand" href="#workspace" aria-label="EVORA workspace">
            <svg width="28" height="30" viewBox="0 0 28 30" fill="none" aria-hidden="true">
              <path d="M14 2 25 7v8c0 6-5 10-11 13C8 25 3 21 3 15V7L14 2Z" stroke="currentColor" strokeWidth="2" />
              <path d="M9 10h10M9 15h8M9 20h5" stroke="currentColor" strokeWidth="2" />
            </svg>
            EVORA
          </a>
          <span className="platform-name">Forensic investigation workspace</span>
          <nav className="navigation" aria-label="Workspace">
            <a href="#workspace" aria-current="page" onClick={event => { event.preventDefault(); setCaseNavigation(value => value + 1); }}>Cases</a>
          </nav>
          <div className="header-actions">
            <ActivityCenter />
            <ThemeToggle />
            {(!client.isLocalAuth() || client.getUser()?.role === 'administrator') && <button type="button" onClick={() => setSettingsOpen(true)} aria-haspopup="dialog">Settings</button>}
            <SessionStatus />
          </div>
        </header>
        <main id="workspace" tabIndex={-1}>
          <CaseWorkspace caseNavigation={caseNavigation} />
        </main>
        <footer>EVORA supports investigation. Findings require human verification.</footer>
      </div>
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </>
  );
}
