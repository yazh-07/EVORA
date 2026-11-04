export { createFindingController } from './findingController';
export { createQuestionController } from './questionController';
export { QuestionAnswer, QuestionAnswerPanel } from './QuestionAnswer';
import { QuestionAnswer } from './QuestionAnswer';
export { FindingInspector, FindingPanel } from './FindingInspector';
import { FindingInspector } from './FindingInspector';
export { createGraphController } from './graphController';
export { GraphView, GraphPanel } from './GraphView';
import { GraphView } from './GraphView';
export { createTriageController } from './triageController';
export { PriorityList, PriorityListPanel } from './PriorityList';
import { PriorityList } from './PriorityList';
export { createAnalysisController } from './analysisController';
export { StartAnalysis, CaseAnalysisWorkspace, useAnalysisWorkspace } from './StartAnalysis';
import { CaseAnalysisWorkspace } from './StartAnalysis';
export { createCaseOverviewController } from './caseOverviewController';
export { CaseOverviewPanel } from './CaseOverview';
import { CaseOverview } from './CaseOverview';
export { createObservationController } from './observationController';
export { ObservationPanel } from './ObservationInspector';
export { createProcessingStatusController } from './processingStatusController';
export { ProcessingStatusPanel } from './ProcessingStatus';
import { EvidenceWorkspace } from './EvidenceWorkspace';
export { EvidencePanels } from './EvidenceWorkspace';
export { createEvidenceStore } from './evidenceStore';
export { createProcessingController } from './processingController';
export { StartProcessing, StartProcessingPanel } from './StartProcessing';
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createCaseStore } from './store';
import type { CaseState } from './store';
import { InvestigationTabs, type InvestigationTab } from './InvestigationTabs';

export function SessionStatus() {
  const client = useApiClient();
  return <div className="session-status">
    <span className={`session-pill ${client.hasToken() ? 'session-active' : ''}`}>
      <span className="status-dot" aria-hidden="true" />{client.hasToken() ? 'Session active' : 'Signed out'}
    </span>
    {client.hasToken() && <button type="button" onClick={() => client.clearToken()}>End session</button>}
  </div>;
}

export function CaseWorkspace({ caseNavigation = 0 }: { caseNavigation?: number }) {
  const client = useApiClient();
  const store = useMemo(() => createCaseStore(client), [client]);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const [tokenError, setTokenError] = useState('');
  const [token, setToken] = useState('');
  const tokenInput = useRef<HTMLInputElement>(null);
  const browsingHeading = useRef<HTMLHeadingElement>(null);
  const returningToCases = useRef(false);
  const lastCaseNavigation = useRef(caseNavigation);
  const activeCase = state.detailStatus === 'ready' ? state.detail : null;
  useEffect(() => { void store.load(); return () => store.dispose(); }, [store]);
  useEffect(() => {
    if (lastCaseNavigation.current === caseNavigation) return;
    lastCaseNavigation.current = caseNavigation;
    returningToCases.current = true;
    void store.load(state.page?.offset ?? 0);
  }, [caseNavigation, store, state.page?.offset]);
  useEffect(() => {
    if (returningToCases.current && !activeCase) {
      if (browsingHeading.current) { browsingHeading.current.tabIndex = -1; browsingHeading.current.focus(); }
      returningToCases.current = false;
    }
  }, [activeCase, caseNavigation]);
  return <>
    {!activeCase && <header className={`selection-header ${!client.hasToken() ? 'sign-in-heading' : ''}`}>
      <h1 ref={browsingHeading}>Case workspace</h1>
      <p>{client.hasToken() ? 'Select a case to continue your investigation, or create a new one.' : 'Secure access to your investigations and evidence.'}</p>
    </header>}
    {!client.hasToken() && <section className="panel session-panel" aria-labelledby="session-heading">
      <span className="section-label">INVESTIGATOR ACCESS</span>
      <h2 id="session-heading">Case access</h2>
      <p>Sign in to open your authorized cases.</p>
      <form onSubmit={event => {
        event.preventDefault();
        try { client.setToken(token); setToken(''); setTokenError(''); }
        catch { setTokenError('Enter a valid access token.'); }
      }}>
        <label htmlFor="access-token">Access token</label>
        <input ref={tokenInput} id="access-token" name="access-token" type="password" autoComplete="off" required
          value={token} onChange={event => setToken(event.target.value)} aria-describedby="session-help" />
        <button className="button-primary" type="submit">Open cases</button>
      </form>
      <p id="session-help">Use an authorized token from your local administrator. It is kept only for this session.</p>
      <div className="demo-access">
        <p>Local demo · synthetic accounts</p>
        <div>{['u02-synthetic-one', 'u02-synthetic-two'].map(value => <button key={value} type="button" className="demo-token identifier"
          onClick={() => { setToken(value); tokenInput.current?.focus(); }}>{value}</button>)}</div>
      </div>
      {tokenError && <p role="alert">{tokenError}</p>}
    </section>}
    <div style={{ display: !activeCase && client.hasToken() ? 'block' : 'none' }}>
      {client.hasToken() && <CaseCreation state={state} create={(title, description) => store.create(title, description)} />}
      <CasePanels state={state} load={offset => { void store.load(offset); }} select={id => { void store.select(id); }} />
    </div>
    {activeCase && <CaseAnalysisWorkspace key={activeCase.id} caseId={activeCase.id} caseDetails={activeCase}
      onBack={() => { returningToCases.current = true; void store.load(state.page?.offset ?? 0); }}>
      <CaseEvidenceWorkspace caseId={activeCase.id} />
    </CaseAnalysisWorkspace>}
  </>;
}

export function CaseEvidenceWorkspace({ caseId }: { caseId: string }) {
  const [selection, setSelection] = useState<{ id: string }>();
  const [activeTab, setActiveTab] = useState<InvestigationTab>('evidence');
  const inspectEvidence = (id: string) => {
    setSelection({ id });
    setActiveTab('evidence');
  };
  return <>
    <InvestigationTabs activeTab={activeTab} onSelect={setActiveTab} />
    {/* Keep every panel mounted: source context, pagination and test contracts survive tab changes. */}
    <div id="panel-evidence" role="tabpanel" aria-labelledby="tab-evidence" tabIndex={0} style={{ display: activeTab === 'evidence' ? 'block' : 'none' }}>
      <EvidenceWorkspace caseId={caseId} sourceSelection={selection} />
    </div>
    <div id="panel-triage" role="tabpanel" aria-labelledby="tab-triage" tabIndex={0} style={{ display: activeTab === 'triage' ? 'block' : 'none' }}>
      <PriorityList inspectEvidence={inspectEvidence} />
    </div>
    <div id="panel-graph" role="tabpanel" aria-labelledby="tab-graph" tabIndex={0} style={{ display: activeTab === 'graph' ? 'block' : 'none' }}>
      <GraphView inspectEvidence={inspectEvidence} />
    </div>
    <div id="panel-findings" role="tabpanel" aria-labelledby="tab-findings" tabIndex={0} style={{ display: activeTab === 'findings' ? 'block' : 'none' }}>
      <FindingInspector inspectEvidence={inspectEvidence} />
    </div>
    <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" tabIndex={0} style={{ display: activeTab === 'overview' ? 'block' : 'none' }}>
      <CaseOverview caseId={caseId} />
    </div>
    <div id="panel-questions" role="tabpanel" aria-labelledby="tab-questions" tabIndex={0} style={{ display: activeTab === 'questions' ? 'block' : 'none' }}>
      <QuestionAnswer key={caseId} caseId={caseId} inspectEvidence={inspectEvidence} />
    </div>
  </>;
}

export function CasePanels({ state, load, select }: { state: CaseState; load: (offset: number) => void; select: (id: string) => void }) {
  const page = state.page;
  const detailHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (state.detailStatus === 'ready' || state.detailStatus === 'error') detailHeading.current?.focus();
  }, [state.detailStatus, state.detail]);
  return <div className={`workspace-layout case-browser ${state.detailStatus === 'idle' ? 'case-browser-idle' : ''}`}>
    <section className="panel" aria-labelledby="cases-heading" aria-busy={state.status === 'loading'}>
      <h2 id="cases-heading" tabIndex={-1}>Your cases</h2>
      {state.status === 'signed-out' && <p>Enter an access token to load your cases.</p>}
      {state.status === 'loading' && <p role="status">Loading cases...</p>}
      {state.status === 'error' && <><p role="alert">{state.message}</p><button onClick={() => load(0)}>Try again</button></>}
      {state.status === 'ready' && page && <>
        <p role="status">{page.total} accessible cases. {page.items.length ? `Showing ${page.offset + 1}-${page.offset + page.items.length}.` : 'Showing 0 cases on this page.'}</p>
        {page.items.length === 0 ? <p>{page.total === 0 ? 'No cases are available to this account.' : 'No cases on this page. Return to the first page or refresh.'}</p> :
          <ul className="case-list">{page.items.map(item => <li key={item.id}>
            <button onClick={() => select(item.id)} aria-pressed={state.detail?.id === item.id}>{item.title}</button>
            <p className="identifier case-record-id">{item.id}</p>
            <p className="case-created">Created <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })}</time></p>
            <button className="case-open" onClick={() => select(item.id)} aria-label={`Open case ${item.title}`}>Open case <span aria-hidden="true">→</span></button>
          </li>)}</ul>}
        <nav className="pagination" aria-label="Case pages">
          <button onClick={() => load(Math.max(0, page.offset - page.limit))} disabled={page.offset === 0}>Previous</button>
          <button onClick={() => load(page.offset + page.limit)} disabled={page.offset + page.limit >= page.total}>Next</button>
          <button onClick={() => load(0)}>Refresh cases</button>
        </nav>
      </>}
    </section>
    <aside className="panel inspector" aria-labelledby="inspector-heading" aria-busy={state.detailStatus === 'loading'}>
      <h2 id="inspector-heading" tabIndex={-1} ref={detailHeading}>Case details</h2>
      {state.detailStatus === 'idle' && <p>Select a case to inspect its details.</p>}
      {state.detailStatus === 'loading' && <p role="status">Loading case details...</p>}
      {state.detailStatus === 'error' && <p role="alert">{state.detailMessage} Select the case again to retry.</p>}
      {state.detailStatus === 'ready' && state.detail && <>
        <h3>{state.detail.title}</h3><p className="identifier">{state.detail.id}</p>
        <p>{state.detail.description ?? 'No description provided.'}</p>
        <p>Created <time dateTime={state.detail.created_at}>{state.detail.created_at}</time></p>
      </>}
      {state.detailStatus !== 'idle' && <a href="#cases-heading">Back to cases</a>}
    </aside>
  </div>;
}

export function CaseCreation({ state, create }: { state: CaseState; create: (title: string, description: string) => Promise<boolean> }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const titleInput = useRef<HTMLInputElement>(null);
  const busy = state.createStatus === 'submitting';
  return <section className="panel case-creation" aria-labelledby="create-heading">
    <details>
    <summary><h2 id="create-heading">New case</h2><span>Create an investigation workspace</span><span className="creation-toggle" aria-hidden="true">＋</span></summary>
    <form noValidate aria-busy={busy} onSubmit={async event => {
      event.preventDefault();
      if (await create(title, description)) { setTitle(''); setDescription(''); }
      else titleInput.current?.focus();
    }}>
      <label htmlFor="case-title">Title (required)</label>
      <input ref={titleInput} id="case-title" name="title" required value={title}
        disabled={busy} aria-invalid={state.createStatus === 'error'} aria-describedby={state.createMessage ? 'create-error' : undefined}
        onChange={event => setTitle(event.target.value)} />
      <p>Title: 1 to 200 characters. Description: up to 5000 characters.</p>
      <label htmlFor="case-description">Description (optional)</label>
      <textarea id="case-description" name="description" value={description} disabled={busy}
        onChange={event => setDescription(event.target.value)} />
      {state.createMessage && <p id="create-error" role="alert">{state.createMessage}</p>}
      <button type="submit" disabled={busy}>{busy ? 'Creating case...' : 'Create case'}</button>
    </form>
    </details>
  </section>;
}
