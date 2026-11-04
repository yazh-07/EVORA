import './GraphView.css';
import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createGraphController } from './graphController';
import type { Graph, GraphSelection, GraphState } from './graphController';

// A01 currently preserves source subkinds in the free-form wire kind. Unknown kinds stay explicit.
const nodeShape = (kind: string) => ['device', 'ip', 'entity'].includes(kind) ? 'entity' :
  ['network.activity', 'gps.location', 'event'].includes(kind) ? 'event' : kind === 'evidence' ? 'evidence' : 'other';

type Point = { x: number; y: number };
type GraphViewOptions = { filter: 'All' | 'Evidence' | 'Entities' | 'Events'; query: string; zoom: number };
const defaultView: GraphViewOptions = { filter: 'All', query: '', zoom: 1 };
const shortLabel = (label: string, length = 28) => label.length > length ? `${label.slice(0, length - 1)}…` : label;
const byId = (a: { id: string }, b: { id: string }) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0;

/** Source grouping is provenance, never an inferred relationship. Stable IDs keep refreshes still. */
function clusteredLayout(graph: Graph | null) {
  const nodes = [...(graph?.nodes ?? [])].sort(byId);
  const evidence = new Map(nodes.filter(n => nodeShape(n.kind) === 'evidence').map(n => [n.id, n]));
  const sourceIds = [...new Set(nodes.flatMap(n => n.evidence_ids))].sort();
  const shared = nodes.filter(n => n.kind !== 'evidence' && n.evidence_ids.length > 1);
  const local = new Map(sourceIds.map(id => [id, nodes.filter(n => n.evidence_ids[0] === id &&
    (n.kind === 'evidence' || n.evidence_ids.length === 1))]));
  const positions = new Map<string, Point>();
  const clusters = sourceIds.map(id => {
    const members = local.get(id)!;
    const anchor = evidence.get(id);
    const satellites = members.filter(n => n.id !== anchor?.id);
    const offsets: { id: string; x: number; y: number }[] = [];
    let offset = 0, ring = 0;
    while (offset < satellites.length) {
      const count = Math.min(6 + ring * 4, satellites.length - offset);
      for (let i = 0; i < count; i++) {
        const theta = -Math.PI / 2 + i * Math.PI * 2 / count;
        offsets.push({ id: satellites[offset + i]!.id,
          x: Math.cos(theta) * (330 + ring * 290), y: Math.sin(theta) * (200 + ring * 160) });
      }
      offset += count; ring++;
    }
    return { id, label: anchor?.label ?? `Evidence ${id}`, members, anchor, offsets, x: 0, y: 0,
      rx: Math.max(180, ...offsets.map(p => Math.abs(p.x) + 160)),
      ry: Math.max(110, ...offsets.map(p => Math.abs(p.y) + 100)) };
  });
  const maxRx = Math.max(180, ...clusters.map(c => c.rx));
  const maxRy = Math.max(110, ...clusters.map(c => c.ry));
  const separation = Math.sin(Math.PI / Math.max(2, clusters.length));
  const radiusX = Math.max((maxRx + 80) / separation, maxRx + (shared.length ? 340 : 80));
  const radiusY = Math.max((maxRy + 80) / separation, maxRy + Math.ceil(shared.length / 3) * 65 + 100);
  clusters.forEach((cluster, index) => {
    const angle = clusters.length === 2 ? Math.PI * index : -Math.PI / 2 + index * 2 * Math.PI / clusters.length;
    cluster.x = clusters.length === 1 ? 0 : Math.cos(angle) * radiusX;
    cluster.y = clusters.length <= 2 ? 0 : Math.sin(angle) * radiusY;
    if (cluster.anchor) positions.set(cluster.anchor.id, { x: cluster.x, y: cluster.y });
    cluster.offsets.forEach(p => positions.set(p.id, { x: cluster.x + p.x, y: cluster.y + p.y }));
  });
  const hubs = new Map(clusters.map(c => [c.id, c]));
  for (const n of shared) {
    const sources = n.evidence_ids.map(id => hubs.get(id)!);
    const center = { x: sources.reduce((sum, c) => sum + c.x, 0) / sources.length,
      y: sources.reduce((sum, c) => sum + c.y, 0) / sources.length };
    // Search outward from the source centroid for a vacant label-sized slot.
    let point = center, step = 0;
    while ([...positions.values()].some(p => Math.abs(p.x - point.x) < 310 && Math.abs(p.y - point.y) < 125)) {
      step++;
      const radius = 145 * Math.ceil(step / 8), angle = step * Math.PI / 4;
      point = { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius };
    }
    positions.set(n.id, point);
  }
  const minX = Math.min(0, ...clusters.map(c => c.x - c.rx), ...[...positions.values()].map(p => p.x - 160)) - 60;
  const minY = Math.min(0, ...clusters.map(c => c.y - c.ry - 65), ...[...positions.values()].map(p => p.y - 65)) - 50;
  const maxX = Math.max(0, ...clusters.map(c => c.x + c.rx), ...[...positions.values()].map(p => p.x + 160)) + 60;
  const maxY = Math.max(0, ...clusters.map(c => c.y + c.ry), ...[...positions.values()].map(p => p.y + 65)) + 50;
  return { positions, clusters, shared, minX, minY, width: Math.max(600, maxX - minX), height: Math.max(480, maxY - minY) };
}

// Stop lines at shape boundaries so direction arrows and labels never cover a node's title.
function boundary(center: Point, target: Point, shape: string): Point {
  const dx = target.x - center.x, dy = target.y - center.y;
  if (!dx && !dy) return center;
  const scale = shape === 'entity' ? 1 / Math.sqrt((dx / 124) ** 2 + (dy / 42) ** 2) :
    shape === 'event' ? 1 / (Math.abs(dx) / 150 + Math.abs(dy) / 54) :
      1 / Math.max(Math.abs(dx) / 124, Math.abs(dy) / 38);
  return { x: center.x + dx * scale, y: center.y + dy * scale };
}

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
  const scope = `${caseId}:${analysis_run_id ?? ''}`;
  const [presentation, setPresentation] = useState({ scope, view: defaultView });
  const view = presentation.scope === scope ? presentation.view : defaultView;
  return <GraphPanel state={visible} load={controller.load} select={controller.select} inspectEvidence={inspectEvidence}
    view={view} onViewChange={next => setPresentation({ scope, view: next })} />;
}

export function GraphPanel({ state, load, select, inspectEvidence, view = defaultView, onViewChange }: {
  state: GraphState; load: () => Promise<void>; select: (selection: GraphSelection) => Promise<void>;
  inspectEvidence?: (id: string) => void;
  view?: GraphViewOptions; onViewChange?: (view: GraphViewOptions) => void;
}) {
  const graph = state.graph;
  const selection = state.selection;
  const node = selection?.kind === 'node' ? graph?.nodes.find(n => n.id === selection.id) : undefined;
  const edge = selection?.kind === 'edge' ? graph?.edges.find(e => e.id === selection.id) : undefined;
  const record = node ?? edge;
  const layout = clusteredLayout(graph);
  const { positions } = layout;
  const query = view.query.trim().toLocaleLowerCase();
  const matches = (n: NonNullable<typeof graph>['nodes'][number]) =>
    [n.label, n.kind, n.id, ...n.evidence_ids].some(value => value.toLocaleLowerCase().includes(query));
  const filterShape = { All: '', Evidence: 'evidence', Entities: 'entity', Events: 'event' }[view.filter];
  const visibleNodes = graph?.nodes.filter(n => !filterShape || nodeShape(n.kind) === filterShape) ?? [];
  const visibleIds = new Set(visibleNodes.map(n => n.id));
  const visibleEdges = graph?.edges.filter(e => visibleIds.has(e.from_id) && visibleIds.has(e.to_id)) ?? [];
  const edgeGroups = new Map<string, typeof visibleEdges>();
  for (const e of visibleEdges) {
    const key = [e.from_id, e.to_id].sort().join(':');
    const group = edgeGroups.get(key) ?? [];
    group.push(e); edgeGroups.set(key, group);
  }
  edgeGroups.forEach(group => group.sort(byId));
  const nodeById = new Map(graph?.nodes.map(n => [n.id, n]));
  const arrowId = `graph-arrow-${graph?.case_id}-${graph?.analysis_run_id}`;
  const changeView = (change: Partial<GraphViewOptions>) => onViewChange?.({ ...view, ...change });
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
          <div className="graph-toolbar" role="group" aria-label="Graph controls">
            <div className="graph-view-controls" role="group" aria-label="View controls">
              <button type="button" aria-label="Zoom in" disabled={view.zoom >= 2.4} onClick={() => changeView({ zoom: Math.min(2.4, view.zoom + .2) })}>+</button>
              <output aria-label="Graph zoom">{Math.round(view.zoom * 100)}%</output>
              <button type="button" aria-label="Zoom out" disabled={view.zoom <= .4} onClick={() => changeView({ zoom: Math.max(.4, view.zoom - .2) })}>−</button>
              <button type="button" aria-label="Reset view" onClick={event => {
                changeView({ zoom: 1 });
                event.currentTarget.closest('.knowledge-graph')?.querySelector('.graph-scroll')?.scrollTo(0, 0);
              }}>⟲</button>
            </div>
            <div className="graph-filters" role="group" aria-label="Filter node types">
              {(['All', 'Evidence', 'Entities', 'Events'] as const).map(filter =>
                <button type="button" key={filter} aria-pressed={view.filter === filter} onClick={() => changeView({ filter })}>{filter}</button>)}
            </div>
            <label className="graph-search">Search nodes
              <input type="search" value={view.query} placeholder="Label, kind or source ID…"
                onChange={event => changeView({ query: event.target.value })} />
            </label>
          </div>
          <div className="graph-summary"><span>{graph.nodes.length} nodes; {graph.edges.length} candidate relationships</span>
            <span>{layout.clusters.length} evidence sources · {layout.shared.length} multi-source nodes</span></div>
          <p className="graph-provenance-note">Grouped by source evidence. Proximity shows provenance; only labeled lines represent candidate relationships.</p>
          {graph.edges.length === 0 && <p className="graph-unlinked">No candidate relationships in this snapshot. Source clusters remain available for inspection.</p>}
          <p className="graph-filter-status" role="status">{visibleNodes.length} nodes shown{query && ` · ${visibleNodes.filter(matches).length} search matches`}{visibleNodes.length === 0 && ' · No nodes match this filter.'}</p>
          <div className="graph-scroll" role="region" aria-label="Case graph diagram" tabIndex={0}>
            <svg width={layout.width} height={layout.height} viewBox={`${layout.minX} ${layout.minY} ${layout.width} ${layout.height}`}
              style={{ width: `${view.zoom * 100}%`, minWidth: Math.min(layout.width, 900) * view.zoom }} aria-label="Candidate relationship diagram">
              <defs><pattern id={`${arrowId}-grid`} width="32" height="32" patternUnits="userSpaceOnUse">
                <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#26344b" strokeWidth=".6" />
              </pattern><marker id={arrowId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
              </marker></defs>
              <rect className="graph-grid" x={layout.minX} y={layout.minY} width={layout.width} height={layout.height} fill={`url(#${arrowId}-grid)`} pointerEvents="none" />
              <g className="graph-clusters" aria-label="Source evidence clusters">
                {layout.clusters.map(c => <g key={c.id} className="graph-cluster" data-evidence-id={c.id}>
                  <ellipse cx={c.x} cy={c.y} rx={c.rx} ry={c.ry} />
                  <text x={c.x} y={c.y - c.ry - 35} textAnchor="middle"><title>{c.label} · {c.id}</title>{shortLabel(c.label, 46)}</text>
                  <text className="graph-cluster-caption" x={c.x} y={c.y - c.ry - 13} textAnchor="middle">Source evidence · {c.members.length} local nodes</text>
                </g>)}
              </g>
              {visibleEdges.map(e => {
                const fromCenter = positions.get(e.from_id)!, toCenter = positions.get(e.to_id)!;
                const from = boundary(fromCenter, toCenter, nodeShape(nodeById.get(e.from_id)!.kind));
                const to = boundary(toCenter, fromCenter, nodeShape(nodeById.get(e.to_id)!.kind));
                const siblings = edgeGroups.get([e.from_id, e.to_id].sort().join(':'))!;
                const lane = siblings.findIndex(other => other.id === e.id);
                const t = siblings.length === 1 ? .5 : .25 + .5 * lane / Math.max(1, siblings.length - 1);
                // Canonical endpoint order keeps opposite-direction edge labels in separate slots.
                const start = e.from_id < e.to_id ? from : to, end = e.from_id < e.to_id ? to : from;
                const label = { x: start.x + (end.x - start.x) * t, y: start.y + (end.y - start.y) * t };
                const labelWidth = Math.max(150, e.kind.length * 7 + 66);
                return <g key={e.id} className="graph-edge" data-kind={e.kind} role="button" tabIndex={0}
                  data-cross-source={e.evidence_ids.length > 1 || new Set([...nodeById.get(e.from_id)!.evidence_ids, ...nodeById.get(e.to_id)!.evidence_ids]).size > 1}
                  aria-label={`Inspect relationship ${e.kind} ${e.id}`} aria-pressed={edge?.id === e.id}
                  onClick={() => { void select({ kind: 'edge', id: e.id }); }}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void select({ kind: 'edge', id: e.id }); } }}>
                  <line className="graph-edge-hit" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} markerEnd={`url(#${arrowId})`} strokeDasharray={e.kind === 'shared_identifier' ? '8 4' : e.kind === 'supported_by' ? undefined : '2 4'} />
                  <rect className="graph-edge-label" x={label.x - labelWidth / 2} y={label.y - 15} width={labelWidth} height="30" rx="6" />
                  <text x={label.x} y={label.y + 4} textAnchor="middle">{e.kind} · {e.confidence.toFixed(2)}</text>
                </g>;
              })}
              {visibleNodes.map(n => {
                const { x, y } = positions.get(n.id)!;
                return <g key={n.id} role="button" tabIndex={0} aria-label={`Inspect node ${n.kind}: ${n.label}`} aria-pressed={node?.id === n.id}
                  data-evidence-ids={n.evidence_ids.join(' ')} data-cross-source={n.evidence_ids.length > 1}
                  data-search-match={query ? matches(n) : undefined}
                  onClick={() => { void select({ kind: 'node', id: n.id }); }}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void select({ kind: 'node', id: n.id }); } }} className={`graph-node graph-node-${nodeShape(n.kind)}`}>
                  {nodeShape(n.kind) === 'entity' ? <ellipse cx={x} cy={y} rx="124" ry="42" /> : nodeShape(n.kind) === 'event' ?
                    <polygon points={`${x},${y - 54} ${x + 150},${y} ${x},${y + 54} ${x - 150},${y}`} /> :
                    <rect x={x - 124} y={y - 38} width="248" height="76" rx="6" />}
                  <text x={x} y={y - 3} textAnchor="middle"><title>{n.label}</title>{shortLabel(n.label, 27)}</text>
                  <text className="graph-node-kind" x={x} y={y + 19} textAnchor="middle">{shortLabel(n.kind, 22)}{n.evidence_ids.length > 1 ? ` · ${n.evidence_ids.length} sources` : ''}</text>
                  {n.evidence_ids.length > 1 && <text className="graph-shared-label" x={x} y={y + 66} textAnchor="middle">Cross-source correlation</text>}
                </g>;
              })}
            </svg>
          </div>
          <ul className="graph-legend" aria-label="Graph legend">
            <li><span className="graph-legend-evidence" aria-hidden="true" />Evidence (Rect)</li>
            <li><span className="graph-legend-entity" aria-hidden="true" />Entity (Ellipse)</li>
            <li><span className="graph-legend-event" aria-hidden="true" />Event (Diamond)</li>
            <li><span className="graph-legend-edge" aria-hidden="true" />Candidate Relationship</li>
          </ul>
          <p>Select a node or line to inspect its complete label and sources. Edge direction is from → to. Scroll the canvas to explore; use zoom for detail.</p>
          <details className="graph-record-browser"><summary>Browse graph records</summary><div className="graph-records">
            <div><h3>Nodes</h3>{visibleNodes.map(n => <button key={n.id} type="button" aria-pressed={node?.id === n.id}
              onClick={() => { void select({ kind: 'node', id: n.id }); }}>{n.kind}: {n.label}</button>)}</div>
            <div><h3>Candidate relationships</h3>{visibleEdges.map(e => <button key={e.id} type="button" aria-pressed={edge?.id === e.id}
              onClick={() => { void select({ kind: 'edge', id: e.id }); }}>{graph.nodes.find(n => n.id === e.from_id)?.label} → {e.kind} → {graph.nodes.find(n => n.id === e.to_id)?.label} · confidence {e.confidence.toFixed(2)}</button>)}</div>
          </div></details>
        </>}
      </div><aside className="graph-inspector" aria-label="Graph record details" aria-live="polite">
        {!record ? <><h3>Record inspector</h3><p>Select a node or relationship to inspect sources.</p><p>Review source evidence and observation locators before drawing conclusions.</p></> : <>
          <h3>{node ? 'Node details' : 'Candidate relationship details'}</h3>
          {node && !visibleIds.has(node.id) && <p>Selected node is hidden by the current filter.</p>}
          {edge && !visibleEdges.some(e => e.id === edge.id) && <p>Selected relationship is hidden by the current filter.</p>}
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
