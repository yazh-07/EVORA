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
          <a href="#workspace" aria-current="page">Evidence</a>
        </nav>
        <main id="workspace" tabIndex={-1}>
          <header className="selection-header">
            <h1>Evidence workspace</h1>
            <p>No case selected.</p>
          </header>
          <div className="workspace-layout">
            <section className="panel" aria-labelledby="evidence-heading">
              <h2 id="evidence-heading">Case evidence</h2>
              <div className="empty-state">
                <h3>Case access is not available yet</h3>
                <p>
                  This workspace is being set up. Sign-in and case access
                  must be connected before evidence can be loaded.
                </p>
              </div>
            </section>
            <aside className="panel inspector" aria-labelledby="inspector-heading">
              <h2 id="inspector-heading">Evidence details</h2>
              <p>Select evidence from a case to inspect its source details.</p>
            </aside>
          </div>
        </main>
        <footer>
          EVORA supports investigation. Findings require human verification.
        </footer>
      </div>
    </>
  );
}
