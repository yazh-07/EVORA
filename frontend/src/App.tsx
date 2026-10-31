import { CaseWorkspace } from './cases/CaseWorkspace';
export function App() {
  return (
    <>
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <div className="app-shell">
        <header className="app-header">
          <span className="brand">EVORA</span>
          <span>Investigation workspace</span>
        </header>
        <nav className="navigation" aria-label="Workspace">
          <a href="#workspace" aria-current="page">Cases</a>
        </nav>
        <main id="workspace" tabIndex={-1}>
          <header className="selection-header">
            <h1>Case workspace</h1>
            <p>Select an authorized case to review its details.</p>
          </header>
          <CaseWorkspace />
        </main>
        <footer>
          EVORA supports investigation. Findings require human verification.
        </footer>
      </div>
    </>
  );
}
