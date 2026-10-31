import { EvidenceWorkspace } from './EvidenceWorkspace';
export { EvidencePanels } from './EvidenceWorkspace';
export { createEvidenceStore } from './evidenceStore';
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createCaseStore } from './store';
import type { CaseState } from './store';

export function CaseWorkspace() {
  const client = useApiClient();
  const store = useMemo(() => createCaseStore(client), [client]);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const [tokenError, setTokenError] = useState('');
  useEffect(() => { void store.load(); return () => store.dispose(); }, [store]);
  return <>
    <section className="panel session-panel" aria-labelledby="session-heading">
      <h2 id="session-heading">Case access</h2>
      {client.hasToken() ? <button type="button" onClick={() => client.clearToken()}>End session</button> :
        <form onSubmit={event => {
          event.preventDefault();
          const form = event.currentTarget;
          const token = String(new FormData(form).get('access-token') ?? '');
          form.reset();
          try { client.setToken(token); setTokenError(''); }
          catch { setTokenError('Enter a valid access token.'); }
        }}>
          <label htmlFor="access-token">Access token</label>
          <input id="access-token" name="access-token" type="password" autoComplete="off" required aria-describedby="session-help" />
          <button type="submit">Open cases</button>
        </form>}
      <p id="session-help">Use an authorized token from your local administrator. It is kept only for this session.</p>
      {tokenError && <p role="alert">{tokenError}</p>}
    </section>
    {client.hasToken() && <CaseCreation state={state} create={(title, description) => store.create(title, description)} />}
    <CasePanels state={state} load={offset => { void store.load(offset); }} select={id => { void store.select(id); }} />
    {state.detailStatus === 'ready' && state.detail && <EvidenceWorkspace key={state.detail.id} caseId={state.detail.id} />}
  </>;
}

export function CasePanels({ state, load, select }: { state: CaseState; load: (offset: number) => void; select: (id: string) => void }) {
  const page = state.page;
  const detailHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (state.detailStatus === 'ready' || state.detailStatus === 'error') detailHeading.current?.focus();
  }, [state.detailStatus, state.detail]);
  return <div className="workspace-layout">
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
            <p className="identifier">{item.id}</p>
            <p>Created <time dateTime={item.created_at}>{item.created_at}</time></p>
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
    <h2 id="create-heading">New case</h2>
    <form noValidate aria-busy={busy} onSubmit={async event => {
      event.preventDefault();
      if (await create(title, description)) { setTitle(''); setDescription(''); }
      else titleInput.current?.focus();
    }}>
      <label htmlFor="case-title">Title (required)</label>
      <input ref={titleInput} id="case-title" name="title" required maxLength={200} value={title}
        disabled={busy} aria-invalid={state.createStatus === 'error'} aria-describedby={state.createMessage ? 'create-error' : undefined}
        onChange={event => setTitle(event.target.value)} />
      <label htmlFor="case-description">Description (optional)</label>
      <textarea id="case-description" name="description" maxLength={5000} value={description} disabled={busy}
        onChange={event => setDescription(event.target.value)} />
      {state.createMessage && <p id="create-error" role="alert">{state.createMessage}</p>}
      <button type="submit" disabled={busy}>{busy ? 'Creating case...' : 'Create case'}</button>
    </form>
  </section>;
}
