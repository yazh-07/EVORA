import { useCallback, useMemo, useState } from 'react';
import type { ApiClient } from '../api/client';
import { loadTimeline, useWorkspaceData } from './workspaceData';
import type { EventRecord } from './workspaceData';

export function filterTimeline(events: EventRecord[], query: string, source: string, from: string, to: string, undated: boolean) {
  return events.filter(event => (!source || event.evidence_ids.includes(source)) &&
    `${event.summary} ${event.kind} ${event.observed_at_raw ?? ''}`.toLowerCase().includes(query.trim().toLowerCase()) &&
    (undated ? !event.observed_at_utc : !!event.observed_at_utc &&
      (!from || Date.parse(event.observed_at_utc) >= Date.parse(`${from}T00:00:00Z`)) &&
      (!to || Date.parse(event.observed_at_utc) <= Date.parse(`${to}T23:59:59.999Z`))))
    .sort((a, b) => (Date.parse(a.observed_at_utc ?? '') || 0) - (Date.parse(b.observed_at_utc ?? '') || 0) || a.id.localeCompare(b.id));
}
export function TimelineWorkspace({ caseId, inspectEvidence }: { caseId: string; inspectEvidence: (id: string) => void }) {
  const loader = useCallback((client: ApiClient, signal: AbortSignal) => loadTimeline(client, caseId, signal), [caseId]);
  const { data, loading, error, refresh } = useWorkspaceData(loader);
  const [query, setQuery] = useState(''), [source, setSource] = useState('');
  const [from, setFrom] = useState(''), [to, setTo] = useState('');
  const [undated, setUndated] = useState(false), [limit, setLimit] = useState(50);
  const events = useMemo(() => filterTimeline(data?.events ?? [], query, source, from, to, undated), [data, query, source, from, to, undated]);
  const names = new Map(data?.evidence.map(item => [item.id, item.source_label || item.filename]));
  const reset = () => { setQuery(''); setSource(''); setFrom(''); setTo(''); setLimit(50); };
  return <section className="panel timeline-workspace" aria-label="Case timeline" aria-busy={loading}>
    <div className="section-heading"><div><span className="section-label">RECONSTRUCT THE SEQUENCE</span><h2>What happened, and when?</h2>
      <p>Compare extracted events across your evidence. Open a source to verify its context.</p></div>
      <button type="button" onClick={refresh} disabled={loading}>Refresh timeline</button></div>
    <p className="scope-note">Live extracted events · normalized times shown in UTC · relative or missing times stay undated. This view is independent of the selected analysis.</p>
    {loading && <p role="status">Loading events and source names…</p>}
    {error && <p role="alert">{error}</p>}
    {data && <>
      <div className="view-switch" role="group" aria-label="Timeline date availability">
        <button type="button" aria-pressed={!undated} onClick={() => { setUndated(false); setLimit(50); }}>Dated events <span>{data.events.filter(event => event.observed_at_utc).length}</span></button>
        <button type="button" aria-pressed={undated} onClick={() => { setUndated(true); setLimit(50); }}>Undated events <span>{data.events.filter(event => !event.observed_at_utc).length}</span></button>
      </div>
      <div className="timeline-filters">
        <label>Search all events<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Device, activity, account…" /></label>
        <label>Evidence source<select value={source} onChange={event => setSource(event.target.value)}><option value="">All sources</option>{data.evidence.map(item => <option value={item.id} key={item.id}>{item.source_label || item.filename}</option>)}</select></label>
        {!undated && <><label>From (UTC)<input type="date" value={from} onChange={event => setFrom(event.target.value)} /></label>
          <label>Through (UTC)<input type="date" value={to} min={from} onChange={event => setTo(event.target.value)} /></label></>}
        <button type="button" onClick={reset}>Clear filters</button>
      </div>
      {from && to && from > to && !undated && <p role="alert">The end date must be on or after the start date.</p>}
      <p role="status">{events.length} matching {undated ? 'undated' : 'dated'} events across this case. Showing {Math.min(limit, events.length)}.</p>
      {!events.length && <div className="workflow-empty"><h3>{data.events.length ? 'No events match these filters' : 'Your timeline starts with processed evidence'}</h3><p>{data.events.length ? 'Try a different source, date range, or the other date category.' : 'Open Evidence, select a source, and start processing. Supported event sources will appear here.'}</p></div>}
      <ol className="timeline-list">{events.slice(0, limit).map(event => <li key={event.id}>
        <div className="timeline-time">{event.observed_at_utc ? <time dateTime={event.observed_at_utc}>{new Date(event.observed_at_utc).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })}<strong>{new Date(event.observed_at_utc).toISOString().slice(11, 19)} <small>UTC</small></strong></time> : <strong>Time unknown</strong>}</div>
        <article><span className="kind-badge">{event.kind.replaceAll('_', ' ')}</span><h3>{event.summary}</h3>
          <div className="timeline-sources">{event.evidence_ids.map((id, i) => <button key={id} type="button" onClick={() => inspectEvidence(id)}>{names.get(id) ?? `Source ${i + 1}`} <span aria-hidden="true">↗</span></button>)}</div>
          <details className="technical-details"><summary>Timestamp and extraction details</summary><p>Source timestamp: {event.observed_at_raw || 'Not recorded'}</p><p>Normalized UTC: {event.observed_at_utc || 'Unavailable; no timestamp inferred'}</p><p>Extraction score: {event.confidence} · requires source verification</p><p className="identifier">Event: {event.id}</p><p className="identifier">Observations: {event.observation_ids.join(', ')}</p></details>
        </article>
      </li>)}</ol>
      {events.length > limit && <button type="button" onClick={() => setLimit(value => value + 50)}>Show 50 more events</button>}
    </>}
  </section>;
}
