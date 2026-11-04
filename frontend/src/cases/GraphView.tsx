import './GraphView.css';
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createGraphController } from './graphController';
import type { GraphSelection, GraphState } from './graphController';

// A01 currently preserves source subkinds in the free-form wire kind. Unknown kinds stay explicit.
const nodeShape = (kind: string) => ['device', 'ip', 'entity'].includes(kind) ? 'entity' :
  ['network.activity', 'gps.location', 'event'].includes(kind) ? 'event' : kind === 'evidence' ? 'evidence' : 'other';

export function GraphView({ inspectEvidence }: { inspectEvidence?: (id: string) => void }) {
  const client = useApiClient();
  const { caseId, analysis_run_id, selectCompletedRun } = useAnalysisWorkspace();
  const controller = useMemo(() => createGraphController(client, caseId, analysis_run_id ?? undefined, selectCompletedRun),
    [client, caseId, analysis_run_id, selectCompletedRun]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  // Latest discovery must first become the shared workspace pin before displaying nonempty results.
  const visible = state.graph?.analysis_run_id && state.graph.analysis_run_id !== analysis_run_id ?
    { ...state, status: 'loading' as const, graph: null } : state;
  return <GraphPanel state={visible} load={controller.load} select={controller.select} inspectEvidence={inspectEvidence} />;
}

export function GraphPanel({ state, load, select, inspectEvidence }: {
  state: GraphState; load: () => Promise<void>; select: (selection: GraphSelection) => Promise<void>;
  inspectEvidence?: (id: string) => void;
}) {
  const graph = state.graph;
  const selection = state.selection;
  const node = selection?.kind === 'node' ? graph?.nodes.find(n => n.id === selection.id) : undefined;
  const edge = selection?.kind === 'edge' ? graph?.edges.find(e => e.id === selection.id) : undefined;
  const record = node ?? edge;
  const height = Math.max(200, Math.ceil((graph?.nodes.length ?? 0) / 3) * 180);
  const positions = new Map(graph?.nodes.map((n, i) => [n.id, { x: 170 + (i % 3) * 280, y: 60 + Math.floor(i / 3) * 180 }]));
  const source = (id: string, label = id) => inspectEvidence ?
    <button type="button" className="identifier" onClick={() => inspectEvidence(id)} aria-label={`Inspect source evidence ${id}: ${label}`}>{label}</button> : <span className="identifier">{label}</span>;
  return <section className="panel knowledge-graph" aria-label="Knowledge Graph" aria-busy={state.status === 'loading'}>
    <h2>Knowledge Graph</h2>
    <p>Candidate relationships require human verification; confidence does not establish identity, source reliability or guilt.</p>
    {state.status === 'loading' && <p role="status">Loading graph...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void load(); }}>Retry graph</button>}
    {state.status === 'ready' && graph && <>
      {graph.analysis_run_id && <p className="identifier">Selected completed analysis: {graph.analysis_run_id}</p>}
      <div className="graph-layout"><div className="graph-primary">
      {!graph.analysis_run_id ? <p>No analysis run completed yet. Start analysis to generate graph.</p> :
        graph.nodes.length === 0 ? <p>No graph nodes in this completed analysis. Available inputs may not contain extracted relationships.</p> : <>
          <p>{graph.nodes.length} nodes; {graph.edges.length} candidate relationships. Evidence: rectangle; entities: ellipse; events: diamond. Exact source kinds appear below.</p>
          <div className="graph-scroll" role="region" aria-label="Case graph diagram" tabIndex={0}>
            <svg width="900" height={height} viewBox={`0 0 900 ${height}`} aria-label="Candidate relationship diagram">
              {graph.edges.map((e, index) => {
                const from = positions.get(e.from_id)!, to = positions.get(e.to_id)!;
                return <g key={e.id} className="graph-edge" data-kind={e.kind} role="button" tabIndex={0}
                  aria-label={`Inspect relationship ${e.kind} ${e.id}`} aria-pressed={edge?.id === e.id}
                  onClick={() => { void select({ kind: 'edge', id: e.id }); }}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void select({ kind: 'edge', id: e.id }); } }}>
                  <line className="graph-edge-hit" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} strokeDasharray={e.kind === 'shared_identifier' ? '8 4' : e.kind === 'supported_by' ? undefined : '2 4'} />
                  <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 + 55 + (index % 3) * 18} textAnchor="middle">{e.kind} · {e.confidence.toFixed(2)}</text>
                </g>;
              })}
              {graph.nodes.map(n => {
                const { x, y } = positions.get(n.id)!;
                return <g key={n.id} role="button" tabIndex={0} aria-label={`Inspect node ${n.kind}: ${n.label}`} aria-pressed={node?.id === n.id}
                  onClick={() => { void select({ kind: 'node', id: n.id }); }}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void select({ kind: 'node', id: n.id }); } }} className={`graph-node graph-node-${nodeShape(n.kind)}`}>
                  {nodeShape(n.kind) === 'entity' ? <ellipse cx={x} cy={y} rx="115" ry="28" /> : nodeShape(n.kind) === 'event' ?
                    <polygon points={`${x},${y - 35} ${x + 125},${y} ${x},${y + 35} ${x - 125},${y}`} /> :
                    <rect x={x - 120} y={y - 28} width="240" height="56" rx="4" />}
                  <text x={x} y={y + 5} textAnchor="middle"><title>{n.label}</title>{n.label.length > 28 ? `${n.label.slice(0, 25)}…` : n.label}</text>
                </g>;
              })}
            </svg>
          </div>
          <p>Select a record below to inspect its complete label and sources. Edge direction is from → to.</p>
          <details className="graph-record-browser"><summary>Browse graph records</summary><div className="graph-records">
            <div><h3>Nodes</h3>{graph.nodes.map(n => <button key={n.id} type="button" aria-pressed={node?.id === n.id}
              onClick={() => { void select({ kind: 'node', id: n.id }); }}>{n.kind}: {n.label}</button>)}</div>
            <div><h3>Candidate relationships</h3>{graph.edges.map(e => <button key={e.id} type="button" aria-pressed={edge?.id === e.id}
              onClick={() => { void select({ kind: 'edge', id: e.id }); }}>{graph.nodes.find(n => n.id === e.from_id)?.label} → {e.kind} → {graph.nodes.find(n => n.id === e.to_id)?.label} · confidence {e.confidence.toFixed(2)}</button>)}</div>
          </div></details>
        </>}
      </div><aside className="graph-inspector" aria-label="Graph record details" aria-live="polite">
        {!record ? <p>Select a node or relationship to inspect sources.</p> : <>
          <h3>{node ? 'Node details' : 'Candidate relationship details'}</h3>
          <dl><dt>ID</dt><dd className="identifier">{record.id}</dd><dt>Kind</dt><dd>{record.kind}</dd>
            {node && <><dt>Label</dt><dd>{node.label}</dd></>}
            {edge && <><dt>From → to</dt><dd className="identifier">{edge.from_id} → {edge.to_id}</dd><dt>Relationship confidence</dt><dd>{edge.confidence.toFixed(2)}</dd></>}
          </dl>
          <h4>Source evidence IDs</h4><ul>{record.evidence_ids.map(id => <li key={id}>{source(id)}</li>)}</ul>
          {edge && <><h4>Observation citations</h4><ul>{edge.observation_ids.map(id => <li key={id} className="identifier">{id}</li>)}</ul>
            {state.citationStatus === 'loading' && <p role="status">Resolving historical source locators...</p>}
            {state.citationMessage && <p role="alert">{state.citationMessage}</p>}
            {state.citationStatus === 'error' && <button type="button" onClick={() => { void select({ kind: 'edge', id: edge.id }); }}>Retry citations</button>}
            {state.citations.map(item => <div key={item.id}><p className="identifier">Observation {item.id} · processing run {item.processing_run_id}</p>
              {source(item.evidence_id, item.source_locator)}</div>)}
            <p>Locators refer to this analysis snapshot. Source actions open evidence metadata and the authorized original download; the separate evidence panel labels its live processing view.</p>
          </>}
        </>}
      </aside></div>
      <button type="button" onClick={() => { void load(); }}>Refresh selected graph</button>
    </>}
  </section>;
}
