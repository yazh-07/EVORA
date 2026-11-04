import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createEntityEventController } from './entityEventController';
import type { EntityEventState, EntityEventView } from './entityEventController';
import './EntityEventInspector.css';

export function EntityEventInspector({ caseId, inspectEvidence }: { caseId: string; inspectEvidence: (id: string) => void }) {
  const client = useApiClient();
  const controller = useMemo(() => createEntityEventController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <EntityEventPanel state={state} load={controller.load} selectView={controller.selectView} inspectEvidence={inspectEvidence} />;
}

export function EntityEventPanel({ state, load, selectView, inspectEvidence }: {
  state: EntityEventState; load: (offset?: number) => Promise<void>; selectView: (view: EntityEventView) => void;
  inspectEvidence: (id: string) => void;
}) {
  const view = state.activeView;
  const current = state[view];
  const page = current.page;
  const sources = (evidenceIds: string[], observationIds: string[]) => <>
    <h4>Supporting evidence</h4>
    {evidenceIds.length ? <ul className="candidate-sources">{evidenceIds.map((id, index) => <li key={index}>
      <button type="button" aria-label={`Inspect source evidence ${id}`} onClick={() => inspectEvidence(id)}>Inspect source evidence {id}</button>
    </li>)}</ul> : <p>No supporting evidence IDs provided.</p>}
    <h4>Supporting observation IDs</h4>
    {observationIds.length ? <ul>{observationIds.map((id, index) => <li className="identifier" key={index}>{id}</li>)}</ul> : <p>No supporting observation IDs provided.</p>}
  </>;
  return <section className="panel entity-event-inspector" aria-label="Candidate entities and events" aria-busy={current.status === 'loading'}>
    <h2>Entities &amp; Events</h2>
    <p>Extracted candidates are unverified. Confidence does not establish real-world identity or prove that an event occurred.</p>
    <div className="candidate-view-switch" role="group" aria-label="Candidate view">
      <button type="button" aria-pressed={view === 'entities'} onClick={() => selectView('entities')}>Entities</button>
      <button type="button" aria-pressed={view === 'events'} onClick={() => selectView('events')}>Events</button>
    </div>
    <h3>{view === 'entities' ? 'Candidate entities' : 'Extracted events'}</h3>
    {current.status === 'loading' && <p role="status">Loading {view}...</p>}
    {current.status === 'error' && <><p role="alert">{current.message}</p>
      <button type="button" onClick={() => { void load(); }}>Retry {view}</button>
    </>}
    {current.status === 'ready' && page && <>
      <p role="status">Showing {page.items.length ? page.offset + 1 : 0}–{page.items.length ? page.offset + page.items.length : 0} of {page.total}</p>
      {page.items.length === 0 && <p>{page.total === 0 ? `No ${view} extracted for this case.` : `No ${view} on this page. Return to the previous page or refresh.`}</p>}
      {view === 'entities' && state.entities.page && <ul className="candidate-list" aria-label="Candidate entities">
        {state.entities.page.items.map(item => <li key={item.id}>
          <span className="candidate-kind">{item.kind}</span>
          <h4 className="candidate-text">{item.canonical_label}</h4>
          <p className="identifier">Candidate key: {item.candidate_key}</p>
          <p>Confidence: {item.confidence.toFixed(2)}</p>
          {sources(item.evidence_ids, item.observation_ids)}
        </li>)}
      </ul>}
      {view === 'events' && state.events.page && <ul className="candidate-list" aria-label="Extracted events">
        {state.events.page.items.map(item => <li key={item.id}>
          <span className="candidate-kind">{item.kind}</span>
          <h4 className="candidate-text">{item.summary}</h4>
          <p>Observed at (UTC): {item.observed_at_utc ? <time dateTime={item.observed_at_utc}>{item.observed_at_utc}</time> : 'Not provided'}</p>
          <p>Confidence: {item.confidence.toFixed(2)}</p>
          {sources(item.evidence_ids, item.observation_ids)}
        </li>)}
      </ul>}
      <nav className="pagination" aria-label={`${view === 'entities' ? 'Entity' : 'Event'} pages`}>
        <button type="button" disabled={page.offset === 0} onClick={() => { void load(Math.max(0, page.offset - page.limit)); }}>Previous</button>
        <button type="button" disabled={page.offset + page.limit >= page.total} onClick={() => { void load(page.offset + page.limit); }}>Next</button>
      </nav>
      <button type="button" onClick={() => { void load(0); }}>Refresh {view}</button>
    </>}
  </section>;
}
