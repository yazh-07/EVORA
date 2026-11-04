import { useState } from 'react';
import { CaseWorkspace, SessionStatus } from './cases/CaseWorkspace';

export function App() {
  const [caseNavigation, setCaseNavigation] = useState(0);
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
          <span className="platform-name">Forensic Investigation Platform</span>
          <nav className="navigation" aria-label="Workspace">
            <a href="#workspace" aria-current="page" onClick={event => { event.preventDefault(); setCaseNavigation(value => value + 1); }}>Cases</a>
          </nav>
          <SessionStatus />
        </header>
        <main id="workspace" tabIndex={-1}>
          <CaseWorkspace caseNavigation={caseNavigation} />
        </main>
        <footer>EVORA supports investigation. Findings require human verification.</footer>
      </div>
    </>
  );
}
