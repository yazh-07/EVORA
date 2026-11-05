import { LocalLogin } from '../auth/LocalLogin';
import { PasswordChange } from '../auth/AccountDialog';
import { SessionControls } from '../auth/SessionControls';
import type { SourceFocus } from './mediaLocators';
export { createTranscriptController } from './transcriptController';
export { TranscriptViewer, TranscriptPanel } from './TranscriptViewer';
export { EvidenceProcessingInspection } from './EvidenceWorkspace';
export { createFindingController } from './findingController';
export { createEntityEventController } from './entityEventController';
export { EntityEventInspector, EntityEventPanel } from './EntityEventInspector';
import { EntityEventInspector } from './EntityEventInspector';
export { createQuestionController } from './questionController';
export { QuestionAnswer, QuestionAnswerPanel } from './QuestionAnswer';
import { QuestionAnswer } from './QuestionAnswer';
export { FindingInspector, FindingPanel } from './FindingInspector';
export { ConflictPanel } from './ConflictPanel';
export { GapPanel } from './GapPanel';
export { ClusterPanel } from './ClusterPanel';
export { AnomalyPanel } from './AnomalyPanel';
export { HypothesisPanel } from './HypothesisPanel';
export { ReliabilityInspector } from './ReliabilityInspector';
export { FindingKindFilter } from './InvestigationTabs';
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
import { InvestigationOverview } from './InvestigationOverview';
import { TimelineWorkspace } from './TimelineWorkspace';
import { ReportWorkspace } from './ReportWorkspace';
export { filterTimeline } from './TimelineWorkspace';
export { buildReportText } from './ReportWorkspace';
export { collectPages, loadTimeline, loadReport } from './workspaceData';
export { ExecutiveBriefPanel, createExecutiveBriefController } from './ExecutiveBrief';
export { detectEvidenceKind } from './evidenceDetection';
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
  if (client.isLocalAuth()) return <SessionControls />;
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
  if (client.getUser()?.must_change_password) return <PasswordChange required />;
  return <>
    {!activeCase && <header className={`selection-header ${!client.hasToken() ? 'sign-in-heading' : ''}`}>
      <h1 ref={browsingHeading}>Case workspace</h1>
      <p>{client.hasToken() ? 'Select a case to continue your investigation, or create a new one.' : 'Secure access to your investigations and evidence.'}</p>
    </header>}
    {!client.hasToken() && <LocalLogin />}
    <div style={{ display: !activeCase && client.hasToken() ? 'block' : 'none' }}>
      {client.hasToken() && client.getUser()?.role !== 'reviewer' && <CaseCreation state={state} create={(title, description) => store.create(title, description)} />}
      <CasePanels state={state} load={offset => { void store.load(offset); }} select={id => { void store.select(id); }} />
    </div>
    {activeCase && <CaseAnalysisWorkspace key={activeCase.id} caseId={activeCase.id} caseDetails={activeCase}
      onBack={() => { returningToCases.current = true; void store.load(state.page?.offset ?? 0); }}>
      <CaseEvidenceWorkspace caseId={activeCase.id} caseTitle={activeCase.title} />
    </CaseAnalysisWorkspace>}
  </>;
}

export function CaseEvidenceWorkspace({ caseId, caseTitle = 'Investigation' }: { caseId: string; caseTitle?: string }) {
  const [selection, setSelection] = useState<{ id: string; focus?: SourceFocus }>();
  const [activeTab, setActiveTab] = useState<InvestigationTab>('overview');
  const [visited, setVisited] = useState<Set<InvestigationTab>>(() => new Set(['overview']));
  const [tool, setTool] = useState('findings');
  const [visitedTools, setVisitedTools] = useState(() => new Set(['findings']));
  const [intakeRequest, setIntakeRequest] = useState(0);
  const navigate = (tab: InvestigationTab) => { setActiveTab(tab); setVisited(value => new Set([...value, tab])); };
  const inspectEvidence = (id: string, focus?: SourceFocus) => {
    setSelection({ id, focus }); navigate('evidence');
  };
  const addEvidence = () => { setIntakeRequest(value => value + 1); navigate('evidence'); };
  const tools = [
    ['findings', 'Review findings', 'Check the source evidence and record your assessment.'],
    ['graph', 'Explore connections', 'Follow relationships between sources, devices, accounts, and events.'],
    ['entities', 'Browse entities', 'Inspect extracted candidates and the evidence that mentions them.'],
    ['triage', 'Prioritize evidence', 'See which sources warrant attention and record priority decisions.'],
    ['questions', 'Ask about the case', 'Ask focused questions and verify every answer against its citations.'],
  ] as const;
  return <div className="investigation-layout">
    <aside className="workspace-sidebar"><span className="section-label">CASE WORKSPACE</span><InvestigationTabs activeTab={activeTab} onSelect={navigate} /><div className="sidebar-note"><strong>Keep the source in sight</strong><p>Every finding is a lead until you verify its supporting evidence.</p></div></aside>
    <div className="investigation-content">
      {(['overview', 'evidence', 'timeline', 'investigation', 'report'] as const).map(tab => <div key={tab} id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} tabIndex={0} hidden={activeTab !== tab}>
        {visited.has(tab) && <>
          {tab === 'overview' && <InvestigationOverview caseId={caseId} navigate={navigate} addEvidence={addEvidence} />}
          {tab === 'evidence' && <><header className="workspace-section-heading"><span className="section-label">START WITH THE SOURCE</span><h2>Your evidence library</h2><p>Add original files, extract their contents, and inspect the records behind each finding.</p></header><EvidenceWorkspace caseId={caseId} sourceSelection={selection} intakeRequest={intakeRequest} /></>}
          {tab === 'timeline' && <TimelineWorkspace caseId={caseId} inspectEvidence={inspectEvidence} />}
          {tab === 'investigation' && <>
            <header className="workspace-section-heading"><span className="section-label">FOLLOW THE EVIDENCE</span><h2>Investigate and verify</h2><p>{tools.find(item => item[0] === tool)?.[2]}</p></header>
            <div className="investigation-tool-switch" role="group" aria-label="Investigation tools">{tools.map(([id, label]) => <button key={id} type="button" aria-pressed={tool === id} onClick={() => { setTool(id); setVisitedTools(value => new Set([...value, id])); }}>{label}</button>)}</div>
            {tools.map(([id]) => <div key={id} hidden={tool !== id}>{visitedTools.has(id) && <>
              {id === 'findings' && <FindingInspector inspectEvidence={inspectEvidence} />}
              {id === 'graph' && <GraphView inspectEvidence={inspectEvidence} />}
              {id === 'entities' && <EntityEventInspector caseId={caseId} inspectEvidence={inspectEvidence} />}
              {id === 'triage' && <PriorityList inspectEvidence={inspectEvidence} />}
              {id === 'questions' && <QuestionAnswer caseId={caseId} inspectEvidence={inspectEvidence} />}
            </>}</div>)}
          </>}
          {tab === 'report' && <ReportWorkspace caseId={caseId} caseTitle={caseTitle} investigate={() => { setTool('findings'); navigate('investigation'); }} />}
        </>}
      </div>)}
    </div>
  </div>;
}

export function CasePanels({ state, load, select }: { state: CaseState; load: (offset: number) => void; select: (id: string) => void }) {
  const page = state.page;
  const [query, setQuery] = useState('');
  const visibleCases = page?.items.filter(item => `${item.title} ${item.id}`.toLowerCase().includes(query.toLowerCase().trim())) ?? [];
  const detailHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (state.detailStatus === 'ready' || state.detailStatus === 'error') detailHeading.current?.focus();
  }, [state.detailStatus, state.detail]);
  return <div className={`workspace-layout case-browser ${state.detailStatus === 'idle' ? 'case-browser-idle' : ''}`}>
    <section className="panel" aria-labelledby="cases-heading" aria-busy={state.status === 'loading'}>
      <div className="section-heading"><div><span className="section-label">INVESTIGATIONS</span><h2 id="cases-heading" tabIndex={-1}>Your cases</h2></div><label className="search-field">Find a case<input type="search" placeholder="Search this page…" value={query} onChange={event => setQuery(event.target.value)} /></label></div>
      {state.status === 'signed-out' && <p>Sign in to load your cases.</p>}
      {state.status === 'loading' && <p role="status">Loading cases...</p>}
      {state.status === 'error' && <><p role="alert">{state.message}</p><button onClick={() => load(0)}>Try again</button></>}
      {state.status === 'ready' && page && <>
        <p role="status">{page.total} accessible cases. {page.items.length ? `Showing ${page.offset + 1}-${page.offset + page.items.length}.` : 'Showing 0 cases on this page.'}</p>
        {page.items.length === 0 ? <p>{page.total === 0 ? 'No cases are available to this account.' : 'No cases on this page. Return to the first page or refresh.'}</p> :
          <ul className="case-list">{visibleCases.map(item => <li key={item.id}>
            <button onClick={() => select(item.id)} aria-pressed={state.detail?.id === item.id}>{item.title}</button>
            <p className="case-description">{item.description || 'Open this case to continue reviewing its evidence.'}</p>
            <p className="case-created">Created <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })}</time></p>
            <button className="case-open" onClick={() => select(item.id)} aria-label={`Open case ${item.title}`}>Open case <span aria-hidden="true">→</span></button>
          </li>)}</ul>}
        {query && <p role="status">{visibleCases.length} matching cases on this page.</p>}
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
      <input ref={titleInput} id="case-title" name="title" required placeholder="e.g. November network review" value={title}
        disabled={busy} aria-invalid={state.createStatus === 'error'} aria-describedby={state.createMessage ? 'create-error' : undefined}
        onChange={event => setTitle(event.target.value)} />
      <p>Give the case a recognizable name. You can describe your scope and investigative questions below.</p>
      <label htmlFor="case-description">Scope and investigative questions (optional)</label>
      <textarea id="case-description" name="description" placeholder="What are you investigating? Add context for your review." value={description} disabled={busy}
        onChange={event => setDescription(event.target.value)} />
      {state.createMessage && <p id="create-error" role="alert">{state.createMessage}</p>}
      <button type="submit" disabled={busy}>{busy ? 'Creating case...' : 'Create case'}</button>
    </form>
    </details>
  </section>;
}
