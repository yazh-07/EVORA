import type { CSSProperties } from 'react';
import { compactGraph, isVisualCandidate } from './graphPresentation';
import { forensicTypes, graphAppearance, isRawLogEvent } from './graphAppearance';
import type { SourceFocus } from './mediaLocators';
import './GraphView.css';
import { useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createGraphController } from './graphController';
import type { Graph, GraphSelection, GraphState } from './graphController';
import { defaultSettings, useSettings, type Settings } from '../settings/settings';

// A01 currently preserves source subkinds in the free-form wire kind. Unknown kinds stay explicit.
const nodeShape = (kind: string) => ['person', 'face', 'vehicle', 'plate', 'device', 'ip', 'location', 'account', 'document', 'video', 'camera', 'entity', 'visual_candidate'].includes(kind) ? 'entity' :
  ['network.activity', 'gps.location', 'visual.detected', 'transaction.record', 'mobile.activity', 'event'].includes(kind) ? 'event' : kind === 'evidence' ? 'evidence' : 'other';

type Point = { x: number; y: number };
type GraphViewOptions = { filter: 'All' | 'Evidence' | 'Entities' | 'Events'; query: string; zoom: number; hideRawEvents?: boolean; focusSelection?: boolean; compact?: boolean };
const defaultView: GraphViewOptions = { filter: 'All', query: '', zoom: 1, compact: true };
const shortLabel = (label: string, length = 28) => label.length > length ? `${label.slice(0, length - 1)}…` : label;
const byId = (a: { id: string }, b: { id: string }) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
const nodeCategory = (n: Graph['nodes'][number]) => isVisualCandidate(n) ? (n.kind === 'visual.detected' ? 'visual detection event' : 'unverified visual candidate') : n.properties?.filename && n.properties.kind === 'image' ? 'image file' : n.properties?.filename && n.properties.kind === 'video' ? 'video file' : n.kind;
const isEvidence = (n: Graph['nodes'][number]) => ['evidence', 'camera', 'document'].includes(n.kind);

function displayLabels(nodes: Graph['nodes'], preference: Settings['default_node_label'] = 'source_description') {
  const key = preference === 'filename' ? 'filename' : 'source_label';
  const labels = new Map(nodes.map(n => {
    const text = (value: unknown) => typeof value === 'string' && value.trim() ? value.trim() : undefined;
    const filename = text(n.properties?.filename)?.split(/[\\/]/).at(-1);
    const label = isEvidence(n) ? (key === 'filename' ? filename : text(n.properties?.source_label))
      || text(n.properties?.source_label) || filename || (n.label === n.id ? 'Evidence source' : n.label) : n.label;
    return [n.id, label];
  }));
  const groups = new Map<string, Graph['nodes']>();
  for (const n of nodes.filter(isEvidence).sort(byId)) {
    // Compare visible text too: distinct long source labels can truncate identically.
    const key = shortLabel(labels.get(n.id)!, 27);
    const group = groups.get(key) ?? [];
    group.push(n); groups.set(key, group);
  }
  for (const group of groups.values()) {
    if (group.length > 1) group.forEach((n, i) => labels.set(n.id, `#${i + 1} · ${labels.get(n.id)}`));
  }
  return labels;
}

/** Deterministic starting positions; provenance springs are never rendered as candidate links. */
const layoutCache = new WeakMap<Graph, ReturnType<typeof seedLayout>>();
function clusteredLayout(graph: Graph | null) {
  if (!graph) return seedLayout(null);
  let layout = layoutCache.get(graph);
  if (!layout) { layout = seedLayout(graph); layoutCache.set(graph, layout); }
  return layout;
}
function seedLayout(graph: Graph | null) {
  const nodes = [...(graph?.nodes ?? [])].sort(byId);
  const labels = displayLabels(nodes);
  const evidence = new Map(nodes.filter(isEvidence).map(n => [n.id, n]));
  const sourceIds = [...new Set(nodes.flatMap(n => n.evidence_ids))].sort();
  const shared = nodes.filter(n => n.kind !== 'evidence' && n.evidence_ids.length > 1);
  const positions = new Map<string, Point>();
  const radius = sourceIds.length <= 1 ? 0 : Math.max(240, sourceIds.length * 65);
  const clusters = sourceIds.map((id, index) => {
    const angle = sourceIds.length === 2 ? index * Math.PI : -Math.PI / 2 + index * Math.PI * 2 / sourceIds.length;
    const x = Math.cos(angle) * radius, y = sourceIds.length <= 2 ? 0 : Math.sin(angle) * radius;
    const anchor = evidence.get(id);
    const members = nodes.filter(n => n.evidence_ids[0] === id && (n.kind === 'evidence' || n.evidence_ids.length === 1));
    if (anchor) positions.set(anchor.id, { x, y });
    const satellites = members.filter(n => n.id !== anchor?.id);
    satellites.forEach((n, i) => {
      const theta = i * 2.399963229728653 - Math.PI / 2;
      const distance = 105 + 27 * Math.sqrt(i);
      positions.set(n.id, { x: x + Math.cos(theta) * distance, y: y + Math.sin(theta) * distance });
    });
    return { id, label: anchor ? labels.get(anchor.id)! : `Evidence ${id}`, members, x, y };
  });
  const hubs = new Map(clusters.map(c => [c.id, c]));
  shared.forEach((n, i) => {
    const sources = n.evidence_ids.map(id => hubs.get(id)!);
    const offset = i === 0 ? 0 : 60 * Math.sqrt(i);
    positions.set(n.id, { x: sources.reduce((sum, c) => sum + c.x, 0) / sources.length + Math.cos(i * 2.4) * offset,
      y: sources.reduce((sum, c) => sum + c.y, 0) / sources.length + Math.sin(i * 2.4) * offset });
  });
  // Reserve source hubs and shared centroids first, then resolve compact particle collisions.
  const occupied: Point[] = [];
  [...nodes.filter(n => n.kind === 'evidence' || n.evidence_ids.length > 1),
    ...nodes.filter(n => n.kind !== 'evidence' && n.evidence_ids.length === 1)].forEach(n => {
    const origin = positions.get(n.id)!;
    let p = origin, attempt = 0;
    while (occupied.some(other => Math.hypot(p.x - other.x, p.y - other.y) < 42)) {
      attempt++;
      p = { x: origin.x + Math.cos(attempt * 2.4) * 45 * Math.sqrt(attempt),
        y: origin.y + Math.sin(attempt * 2.4) * 45 * Math.sqrt(attempt) };
    }
    positions.set(n.id, p); occupied.push(p);
  });
  const width = Math.max(960, ...[...positions.values()].map(p => Math.abs(p.x) * 2 + 280));
  const height = Math.max(680, ...[...positions.values()].map(p => Math.abs(p.y) * 2 + 180));
  return { positions, clusters, shared, labels, minX: -width / 2, minY: -height / 2, width, height };
}

type Particle = Point & { vx: number; vy: number; pinned: boolean };
function forceSimulation(graph: Graph) {
  const { positions } = clusteredLayout(graph);
  const particles = new Map<string, Particle>([...positions].map(([id, p]) => [id, { ...p, vx: 0, vy: 0, pinned: false }]));
  const values = [...particles.values()];
  const springs = graph.edges.filter(e => e.from_id !== e.to_id).map(e => ({ from: e.from_id, to: e.to_id, length: 175, strength: .009 }));
  const linked = new Set(springs.map(s => [s.from, s.to].sort().join(':')));
  graph.nodes.forEach(n => n.evidence_ids.forEach(id => {
    if (id !== n.id && particles.has(id) && !linked.has([n.id, id].sort().join(':'))) {
      springs.push({ from: id, to: n.id, length: 130, strength: .004 });
    }
  }));
  function tick() {
    // Spatial buckets bound repulsion work on large snapshots. Distant fields use their centroid.
    const cells = new Map<string, { x: number; y: number; members: Particle[] }>();
    values.forEach(p => {
      const key = `${Math.floor(p.x / 180)},${Math.floor(p.y / 180)}`;
      const cell = cells.get(key) ?? { x: 0, y: 0, members: [] };
      cell.x += p.x; cell.y += p.y; cell.members.push(p); cells.set(key, cell);
    });
    for (const cell of cells.values()) { cell.x /= cell.members.length; cell.y /= cell.members.length; }
    values.forEach((p, index) => {
      if (p.pinned) return;
      const repel = (x: number, y: number, count: number) => {
        let dx = p.x - x, dy = p.y - y;
        if (Math.abs(dx) + Math.abs(dy) < .01) { dx = Math.cos(index * 2.4); dy = Math.sin(index * 2.4); }
        const d2 = Math.max(400, dx * dx + dy * dy), distance = Math.sqrt(d2);
        const force = Math.min(3, 6200 * count / d2) + (count === 1 ? Math.max(0, 40 - distance) * .15 : 0);
        p.vx += dx / distance * force; p.vy += dy / distance * force;
      };
      for (const cell of cells.values()) {
        if ((p.x - cell.x) ** 2 + (p.y - cell.y) ** 2 > 360 ** 2) repel(cell.x, cell.y, cell.members.length);
        else cell.members.forEach(other => { if (other !== p) repel(other.x, other.y, 1); });
      }
      p.vx -= p.x * .0009; p.vy -= p.y * .0009;
    });
    springs.forEach(s => {
      const a = particles.get(s.from)!, b = particles.get(s.to)!;
      const dx = b.x - a.x, dy = b.y - a.y, distance = Math.hypot(dx, dy) || 1;
      const force = Math.max(-4, Math.min(4, (distance - s.length) * s.strength));
      if (!a.pinned) { a.vx += dx / distance * force; a.vy += dy / distance * force; }
      if (!b.pinned) { b.vx -= dx / distance * force; b.vy -= dy / distance * force; }
    });
    let energy = 0;
    values.forEach(p => {
      if (p.pinned) { p.vx = 0; p.vy = 0; return; }
      p.vx = Math.max(-12, Math.min(12, p.vx * .88)); p.vy = Math.max(-12, Math.min(12, p.vy * .88));
      p.x += p.vx; p.y += p.vy; energy = Math.max(energy, p.vx * p.vx + p.vy * p.vy);
    });
    return energy;
  }
  return { particles, tick };
}

function boundary(center: Point, target: Point, shape: string): Point {
  const dx = target.x - center.x, dy = target.y - center.y;
  const distance = Math.hypot(dx, dy) || 1;
  const radius = Math.min(distance / 2, shape === 'evidence' ? 17 : 15);
  return { x: center.x + dx / distance * radius, y: center.y + dy / distance * radius };
}

/** Own animation and gestures outside React's render cycle; inspector updates never restart physics. */
function GraphMotion({ graph, view, onViewChange, selection }: { graph: Graph; view: GraphViewOptions; selection: GraphSelection | null; onViewChange?: (view: GraphViewOptions) => void }) {
  const anchor = useRef<SVGGElement>(null);
  const current = useRef({ view, onViewChange, selection });
  const runtime = useRef<{ redraw: () => void; zoom: (value: number) => void; highlight: () => void } | null>(null);
  current.current = { view, onViewChange, selection };
  useLayoutEffect(() => {
    const svg = anchor.current!.ownerSVGElement!;
    const world = svg.querySelector<SVGGElement>('.graph-world')!;
    const canvas = svg.parentElement!;
    const simulation = forceSimulation(graph), layout = clusteredLayout(graph), seed = layout.positions;
    const nodeById = new Map(graph.nodes.map(n => [n.id, n]));
    const neighbors = new Map(graph.nodes.map(n => [n.id, new Set([n.id])]));
    graph.edges.forEach(e => { neighbors.get(e.from_id)!.add(e.to_id); neighbors.get(e.to_id)!.add(e.from_id); });
    let pan = { x: 0, y: 0 }, zoom = current.current.view.zoom, frame = 0, quiet = 0, last = 0, visible = true, autoFit = true;
    let bounds = { left: layout.minX, top: layout.minY, right: layout.minX + layout.width, bottom: layout.minY + layout.height };
    let gesture: { pointer: number; node?: string; start: Point; previous: Point; moved: boolean; offset: Point; capture: Element } | undefined;
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const point = (event: { clientX: number; clientY: number }) => {
      const matrix = svg.getScreenCTM();
      return matrix ? new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse()) : new DOMPoint();
    };
    const transform = () => world.setAttribute('transform', `translate(${pan.x} ${pan.y}) scale(${zoom})`);
    const resizeViewport = () => {
      // On phones, keep particles and labels legible and let panning reveal the wider graph.
      if (canvas.clientWidth > 0 && canvas.clientWidth < 560) {
        const width = canvas.clientWidth / .85, height = canvas.clientHeight / .85;
        svg.setAttribute('viewBox', `${(bounds.left + bounds.right - width) / 2} ${(bounds.top + bounds.bottom - height) / 2} ${width} ${height}`);
      } else svg.setAttribute('viewBox', `${bounds.left} ${bounds.top} ${bounds.right - bounds.left} ${bounds.bottom - bounds.top}`);
    };
    const redraw = () => {
      // Let the initial layout breathe without clipping floating labels. A gesture takes control.
      if (autoFit) {
        const points = [...simulation.particles.values()];
        if (points.length) {
          const left = Math.min(...points.map(p => p.x)) - 60, right = Math.max(...points.map(p => p.x)) + 195;
          const top = Math.min(...points.map(p => p.y)) - 60, bottom = Math.max(...points.map(p => p.y)) + 65;
          const width = Math.max(720, right - left), height = Math.max(480, bottom - top);
          const target = { left: (left + right - width) / 2, right: (left + right + width) / 2,
            top: (top + bottom - height) / 2, bottom: (top + bottom + height) / 2 };
          for (const key of ['left', 'right', 'top', 'bottom'] as const) bounds[key] += (target[key] - bounds[key]) * (motion.matches ? 1 : .12);
        }
        resizeViewport();
      }
      svg.querySelectorAll<SVGGElement>('[data-node-id]').forEach(el => {
        const id = el.dataset.nodeId!, p = simulation.particles.get(id)!, origin = seed.get(id)!;
        el.setAttribute('transform', `translate(${p.x - origin.x} ${p.y - origin.y})`);
      });
      svg.querySelectorAll<SVGGElement>('[data-edge-id]').forEach(el => {
        const a = simulation.particles.get(el.dataset.from!)!, b = simulation.particles.get(el.dataset.to!)!;
        const from = boundary(a, b, nodeShape(nodeById.get(el.dataset.from!)!.kind));
        const to = boundary(b, a, nodeShape(nodeById.get(el.dataset.to!)!.kind));
        el.querySelectorAll('line').forEach(line => {
          line.setAttribute('x1', String(from.x)); line.setAttribute('y1', String(from.y));
          line.setAttribute('x2', String(to.x)); line.setAttribute('y2', String(to.y));
        });
        const t = Number(el.dataset.lane), start = el.dataset.from! < el.dataset.to! ? from : to, end = start === from ? to : from;
        el.querySelector('.graph-edge-caption')?.setAttribute('transform', `translate(${start.x + (end.x - start.x) * t} ${start.y + (end.y - start.y) * t})`);
      });
      svg.querySelectorAll<SVGLineElement>('.graph-provenance-ray').forEach(line => {
        const from = simulation.particles.get(line.dataset.from!);
        const to = simulation.particles.get(line.dataset.to!);
        if (from && to) {
          line.setAttribute('x1', String(from.x)); line.setAttribute('y1', String(from.y));
          line.setAttribute('x2', String(to.x)); line.setAttribute('y2', String(to.y));
        }
      });
      transform();
    };
    const animate = (time: number) => {
      frame = 0;
      if (!visible || document.hidden) return;
      // Fixed simulation steps keep damping consistent on 60Hz and high-refresh displays.
      if (!last) last = time - 16.67;
      last = Math.max(last, time - 50);
      let steps = Math.min(3, Math.floor((time - last) / 16.67));
      while (steps-- > 0) { const energy = simulation.tick(); quiet = energy < .001 ? quiet + 1 : 0; last += 16.67; }
      redraw();
      if (quiet < 45 || gesture?.node) frame = requestAnimationFrame(animate);
    };
    const wake = () => {
      quiet = 0; last = 0;
      if (motion.matches) { cancelAnimationFrame(frame); frame = 0; for (let i = 0; i < 180; i++) simulation.tick(); redraw(); }
      else if (!frame && visible && !document.hidden) frame = requestAnimationFrame(animate);
    };
    const illuminate = (id?: string, otherId?: string) => {
      if (!id && current.current.selection) {
        const selected = current.current.selection;
        if (selected.kind === 'node') id = selected.id;
        else { const edge = graph.edges.find(e => e.id === selected.id); id = edge?.from_id; otherId = edge?.to_id; }
      }
      const connected = id ? new Set([...(neighbors.get(id) ?? []), ...(otherId ? neighbors.get(otherId) ?? [] : [])]) : undefined;
      svg.querySelectorAll<SVGGElement>('[data-node-id]').forEach(el => {
        el.dataset.dimmed = String(!!connected && !connected.has(el.dataset.nodeId!));
        el.dataset.neighbor = String(!!connected?.has(el.dataset.nodeId!));
      });
      svg.querySelectorAll<SVGGElement>('[data-edge-id]').forEach(el => {
        const incident = !!id && (el.dataset.from === id || el.dataset.to === id);
        el.dataset.dimmed = String(!!id && !incident); el.dataset.neighbor = String(incident);
      });
      svg.querySelectorAll<SVGLineElement>('.graph-provenance-ray').forEach(line => {
        const active = !!id && (line.dataset.from === id || line.dataset.to === id);
        line.dataset.active = String(active);
        line.dataset.dimmed = String(!!id && !active);
      });
    };
    const down = (event: PointerEvent) => {
      if (event.button !== 0 || gesture) return;
      const target = (event.target as Element).closest<SVGGElement>('[data-node-id]');
      if (!target && (event.target as Element).closest('[data-edge-id]')) return;
      autoFit = false;
      const start = point(event), id = target?.dataset.nodeId, p = id ? simulation.particles.get(id)! : undefined;
      gesture = { pointer: event.pointerId, node: id, start, previous: start, moved: false,
        offset: p ? { x: p.x - (start.x - pan.x) / zoom, y: p.y - (start.y - pan.y) / zoom } : { x: 0, y: 0 }, capture: target ?? svg };
      if (p) p.pinned = true;
      gesture.capture.setPointerCapture(event.pointerId); canvas.classList.add('is-dragging');
      event.preventDefault(); if (p) wake();
    };
    const move = (event: PointerEvent) => {
      if (!gesture) return;
      if (gesture.pointer !== event.pointerId) return;
      const next = point(event);
      gesture.moved ||= Math.hypot(next.x - gesture.start.x, next.y - gesture.start.y) > 4 / (svg.getScreenCTM()?.a || 1);
      if (gesture.node) {
        const p = simulation.particles.get(gesture.node)!;
        p.x = (next.x - pan.x) / zoom + gesture.offset.x; p.y = (next.y - pan.y) / zoom + gesture.offset.y;
        redraw(); if (!motion.matches) wake();
      } else { pan.x += next.x - gesture.previous.x; pan.y += next.y - gesture.previous.y; transform(); }
      gesture.previous = next;
    };
    let suppressClick = false;
    const up = (event: PointerEvent) => {
      if (!gesture || gesture.pointer !== event.pointerId) return;
      if (gesture.node) { simulation.particles.get(gesture.node)!.pinned = false; wake(); }
      suppressClick = gesture.moved || event.type === 'pointercancel';
      const capture = gesture.capture; gesture = undefined;
      if (capture.hasPointerCapture(event.pointerId)) capture.releasePointerCapture(event.pointerId);
      canvas.classList.remove('is-dragging');
    };
    const click = (event: MouseEvent) => { if (suppressClick) { event.stopPropagation(); event.preventDefault(); suppressClick = false; } };
    const wheel = (event: WheelEvent) => {
      event.preventDefault(); autoFit = false;
      const next = Math.max(.4, Math.min(2.4, zoom * Math.exp(-event.deltaY * (event.deltaMode === 1 ? .025 : .0015))));
      const cursor = point(event), ratio = next / zoom;
      pan = { x: cursor.x - (cursor.x - pan.x) * ratio, y: cursor.y - (cursor.y - pan.y) * ratio };
      zoom = next; transform(); current.current.onViewChange?.({ ...current.current.view, zoom });
    };
    const over = (event: Event) => {
      if (gesture) return;
      const target = (event.target as Element).closest<SVGGElement>('[data-node-id], [data-edge-id]');
      illuminate(target?.dataset.nodeId ?? target?.dataset.from, target?.dataset.to);
    };
    const leave = () => { if (!gesture) illuminate(); };
    const reset = () => {
      pan = { x: 0, y: 0 }; zoom = 1; autoFit = true;
      bounds = { left: layout.minX, top: layout.minY, right: layout.minX + layout.width, bottom: layout.minY + layout.height };
      redraw();
    };
    const visibility = () => { if (document.hidden) { cancelAnimationFrame(frame); frame = 0; } else wake(); };
    const observer = new IntersectionObserver(entries => {
      visible = entries[0]?.isIntersecting ?? true;
      if (visible) wake(); else { cancelAnimationFrame(frame); frame = 0; }
    });
    observer.observe(svg);
    const resize = new ResizeObserver(resizeViewport); resize.observe(canvas);
    svg.addEventListener('pointerdown', down); svg.addEventListener('pointermove', move);
    svg.addEventListener('pointerup', up); svg.addEventListener('pointercancel', up); svg.addEventListener('lostpointercapture', up);
    svg.addEventListener('click', click, true); svg.addEventListener('wheel', wheel, { passive: false });
    svg.addEventListener('pointerover', over); svg.addEventListener('pointerleave', leave);
    svg.addEventListener('focusin', over); svg.addEventListener('focusout', leave);
    canvas.addEventListener('graph-reset', reset); document.addEventListener('visibilitychange', visibility); motion.addEventListener('change', wake);
    runtime.current = { redraw, highlight: () => illuminate(), zoom: value => { if (zoom !== value) autoFit = false; zoom = value; transform(); } };
    wake();
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); resize.disconnect(); runtime.current = null;
      svg.removeEventListener('pointerdown', down); svg.removeEventListener('pointermove', move);
      svg.removeEventListener('pointerup', up); svg.removeEventListener('pointercancel', up); svg.removeEventListener('lostpointercapture', up);
      svg.removeEventListener('click', click, true); svg.removeEventListener('wheel', wheel);
      svg.removeEventListener('pointerover', over); svg.removeEventListener('pointerleave', leave);
      svg.removeEventListener('focusin', over); svg.removeEventListener('focusout', leave);
      canvas.removeEventListener('graph-reset', reset); document.removeEventListener('visibilitychange', visibility); motion.removeEventListener('change', wake);
      canvas.classList.remove('is-dragging');
    };
  }, [graph]);
  useLayoutEffect(() => { runtime.current?.redraw(); });
  useEffect(() => { runtime.current?.highlight(); }, [selection]);
  useEffect(() => { runtime.current?.zoom(view.zoom); }, [view.zoom]);
  return <g ref={anchor} aria-hidden="true" />;
}

export function GraphView({ inspectEvidence }: { inspectEvidence?: (id: string, focus?: SourceFocus) => void }) {
  const client = useApiClient();
  const settings = useSettings();
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
  return <GraphPanel settings={settings} state={visible} load={controller.load} select={controller.select} dismiss={() => {
      const selected = document.querySelector<SVGGElement>('.graph-node[aria-pressed="true"], .graph-edge[aria-pressed="true"]');
      controller.clearSelection(); selected?.focus();
    }} inspectEvidence={inspectEvidence}
    view={view} onViewChange={next => setPresentation({ scope, view: next })} />;
}

export function GraphPanel({ state, load, select, inspectEvidence, view = defaultView, onViewChange, dismiss, settings = defaultSettings }: {
  state: GraphState; load: () => Promise<void>; select: (selection: GraphSelection) => Promise<void>;
  inspectEvidence?: (id: string, focus?: SourceFocus) => void;
  dismiss?: () => void; view?: GraphViewOptions; onViewChange?: (view: GraphViewOptions) => void;
  settings?: Settings;
}) {
  const graph = state.graph && view.compact ? compactGraph(state.graph) : state.graph;
  const selection = state.selection;
  const node = selection?.kind === 'node' ? (graph?.nodes.find(n => n.id === selection.id) ?? state.graph?.nodes.find(n => n.id === selection.id)) : undefined;
  const edge = selection?.kind === 'edge' ? graph?.edges.find(e => e.id === selection.id) : undefined;
  const record = node ?? edge;
  const layout = clusteredLayout(graph);
  const { positions } = layout;
  const labels = displayLabels(graph?.nodes ?? [], settings.default_node_label);
  const query = view.query.trim().toLocaleLowerCase();
  const matches = (n: NonNullable<typeof graph>['nodes'][number]) =>
    [labels.get(n.id)!, n.label, n.kind, n.id, ...n.evidence_ids].some(value => value.toLocaleLowerCase().includes(query));
  const filterShape = { All: '', Evidence: 'evidence', Entities: 'entity', Events: 'event' }[view.filter];
  const neighborhood = new Set<string>(node ? [node.id] : []);
  if (node) for (const link of graph?.edges ?? []) {
    if (link.from_id === node.id) neighborhood.add(link.to_id);
    if (link.to_id === node.id) neighborhood.add(link.from_id);
  }
  const visibleNodes = graph?.nodes.filter(n => (!filterShape || nodeShape(n.kind) === filterShape)
    && (!view.hideRawEvents || !isRawLogEvent(n.kind, n.entity_type))
    && (!view.focusSelection || !node || neighborhood.has(n.id))) ?? [];
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
  const source = (id: string, label = id, focus?: SourceFocus) => inspectEvidence ?
    <button type="button" className="identifier" onClick={() => inspectEvidence(id, focus)} aria-label={`Inspect source evidence ${id}: ${label}`}>{label}</button> : <span className="identifier">{label}</span>;
  return <section className="panel knowledge-graph" aria-label="Knowledge Graph" aria-busy={state.status === 'loading'}>
    <h2>Connections</h2>
    {view.compact && <span className="kind-badge">Grouped candidates · unverified</span>}
    <details className="context-help"><summary>About connections</summary><p>Groups share exact identifiers or reported coordinates; identity is unverified. Use Show all source records for raw events, files and visual candidates. Source evidence binds each cluster. Only labeled lines represent candidate relationships.</p><p>Candidate relationships require human verification; confidence does not establish identity, source reliability or guilt.</p></details>
    {state.status === 'loading' && <p role="status">Loading graph...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void load(); }}>Retry graph</button>}
    {state.status === 'ready' && graph && <>
      {graph.analysis_run_id && <details className="technical-details"><summary>Analysis reference</summary><p className="identifier">{graph.analysis_run_id}</p></details>}
      <div className="graph-layout" data-inspecting={!!record}><div className="graph-primary">
      {!graph.analysis_run_id ? <p>No analysis run completed yet. Start analysis to generate graph.</p> :
        state.graph?.nodes.length === 0 ? <p>No graph nodes in this completed analysis.</p> : <>
          <div className="graph-toolbar" role="group" aria-label="Graph controls">
            <button type="button" aria-pressed={!!view.compact} onClick={() => changeView({ compact: !view.compact, ...(!view.compact ? { filter: 'All' } : {}) })}>{view.compact ? 'Show all source records' : 'Group identifiers and hide raw candidates'}</button>
            <div className="graph-view-controls" role="group" aria-label="View controls">
              <button type="button" aria-label="Zoom in" disabled={view.zoom >= 2.4} onClick={() => changeView({ zoom: Math.min(2.4, view.zoom + .2) })}>+</button>
              <output aria-label="Graph zoom">{Math.round(view.zoom * 100)}%</output>
              <button type="button" aria-label="Zoom out" disabled={view.zoom <= .4} onClick={() => changeView({ zoom: Math.max(.4, view.zoom - .2) })}>−</button>
              <button type="button" aria-label="Reset view" onClick={event => {
                changeView({ zoom: 1 });
                const canvas = event.currentTarget.closest('.knowledge-graph')?.querySelector('.graph-scroll');
                canvas?.scrollTo(0, 0);
                canvas?.dispatchEvent?.(new Event('graph-reset'));
              }}>⟲</button>
            </div>
            <div className="graph-filters" role="group" aria-label="Filter node types">
              {(['All', 'Evidence', 'Entities', 'Events'] as const).map(filter =>
                <button type="button" key={filter} aria-pressed={view.filter === filter} onClick={() => changeView({ filter, ...(['Evidence','Events'].includes(filter) ? { compact: false } : {}), ...(filter === 'Events' ? { hideRawEvents: false } : {}) })}>{filter}</button>)}
            </div>
            <button type="button" disabled={!node && !view.focusSelection} aria-pressed={!!view.focusSelection} onClick={() => changeView({ focusSelection: !view.focusSelection })}>Focus on selected node</button>
            <button type="button" aria-pressed={!!view.hideRawEvents} onClick={() => changeView({ hideRawEvents: !view.hideRawEvents })}>Hide raw log events</button>
            <label className="graph-search">Search nodes
              <input type="search" value={view.query} placeholder="Label, kind or source ID…"
                onChange={event => changeView({ query: event.target.value })} />
            </label>
          </div>
          {view.compact && graph.nodes.length === 0 && <p className="scope-note">No grouped subjects in this view. Use Show all source records to inspect files, raw events and unverified candidates.</p>}
          <div className="graph-summary"><span>{graph.nodes.length} nodes; {graph.edges.length} candidate relationships</span>
            <span>{layout.clusters.length} evidence sources · {layout.shared.length} multi-source nodes</span></div>
          {graph.edges.length === 0 && <p className="graph-unlinked">{view.compact ? 'No subject-to-subject relationships in this grouped view. Exact-identifier matches are summarized on nodes.' : 'No candidate relationships in this snapshot. Source clusters remain available for inspection.'}</p>}
          <p className="graph-filter-status" role="status">{visibleNodes.length} nodes shown{query && ` · ${visibleNodes.filter(matches).length} search matches`}{visibleNodes.length === 0 && ' · No nodes match this filter.'}</p>
          <div className="graph-scroll" role="region" aria-label="Case graph diagram" tabIndex={0}>
            <svg width="100%" height="100%" viewBox={`${layout.minX} ${layout.minY} ${layout.width} ${layout.height}`}
              style={{ width: '100%', touchAction: 'none' }} aria-label="Candidate relationship diagram">
              <defs><marker id={arrowId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#8b949e" />
              </marker></defs>
              <g className="graph-world">
              <g className="graph-clusters" aria-label="Source evidence clusters">
                {(view.compact ? [] : layout.clusters).map(c => <g key={c.id} className="graph-cluster" data-evidence-id={c.id}>
                  <title>{`${labels.get(c.id) ?? c.label} · ${c.id} · Source evidence · ${c.members.length} local nodes`}</title>
                </g>)}
              </g>
              <g className="graph-provenance-rays" aria-label="Evidence lineage" display={settings.show_provenance_rays && !view.compact ? undefined : 'none'} aria-hidden={!settings.show_provenance_rays}>
                {layout.clusters.flatMap(c => {
                  const anchor = positions.get(c.id);
                  if (!anchor || !visibleIds.has(c.id)) return [];
                  return (graph?.nodes ?? []).filter(m => m.id !== c.id && m.evidence_ids.includes(c.id) && visibleIds.has(m.id)).map(m => {
                    const p = positions.get(m.id);
                    if (!p) return null;
                    return <line key={`ray-${c.id}-${m.id}`}
                      className="graph-provenance-ray"
                      data-from={c.id} data-to={m.id}
                      x1={anchor.x} y1={anchor.y}
                      x2={p.x} y2={p.y} />;
                  }).filter(Boolean);
                })}
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
                const relationshipLabel = e.label || e.kind;
                const labelWidth = Math.max(125, relationshipLabel.length * 6 + 51);
                return <g key={e.id} className="graph-edge" data-kind={e.kind}
                  data-edge-id={e.id} data-from={e.from_id} data-to={e.to_id} data-lane={t} role="button" tabIndex={0}
                  data-cross-source={e.evidence_ids.length > 1 || new Set([...nodeById.get(e.from_id)!.evidence_ids, ...nodeById.get(e.to_id)!.evidence_ids]).size > 1}
                  aria-label={`Inspect relationship ${e.kind} ${e.id}`} aria-pressed={edge?.id === e.id}
                  onClick={() => { void select({ kind: 'edge', id: e.id }); }}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void select({ kind: 'edge', id: e.id }); } }}>
                  <line className="graph-edge-hit" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} markerEnd={`url(#${arrowId})`} strokeDasharray={e.kind === 'shared_identifier' ? '8 4' : e.kind === 'supported_by' ? undefined : '2 4'} />
                  <g className="graph-edge-caption" transform={`translate(${label.x} ${label.y})`}>
                    <rect className="graph-edge-label" x={-labelWidth / 2} y="-11" width={labelWidth} height="22" rx="11" />
                    <text x={-labelWidth / 2 + 9} y="4" textAnchor="start">{relationshipLabel}</text>
                    <rect className="graph-confidence-badge" x={labelWidth / 2 - 36} y="-8" width="32" height="16" rx="8" />
                    <text className="graph-confidence" x={labelWidth / 2 - 20} y="4" textAnchor="middle">{e.confidence.toFixed(2)}</text>
                  </g>
                </g>;
              })}
              {visibleNodes.map(n => {
                const { x, y } = positions.get(n.id)!;
                const label = labels.get(n.id)!;
                const appearance = graphAppearance(n.kind, n.entity_type);
                return <g key={n.id} role="button" tabIndex={0} aria-label={`Inspect node ${nodeCategory(n)}: ${label}`} aria-pressed={node?.id === n.id}
                  style={{ '--particle': appearance.color } as CSSProperties} data-entity-type={n.entity_type || n.kind}
                  data-node-id={n.id} data-evidence-ids={n.evidence_ids.join(' ')} data-cross-source={n.evidence_ids.length > 1}
                  data-search-match={query ? matches(n) : undefined}
                  onClick={() => { void select({ kind: 'node', id: n.id }); }}
                  onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void select({ kind: 'node', id: n.id }); } }} className={`graph-node graph-node-${nodeShape(n.kind)}`}>
                  {nodeShape(n.kind) === 'entity' ? <ellipse cx={x} cy={y} rx="12" ry="12" /> : nodeShape(n.kind) === 'event' ?
                    <polygon points={`${x},${y - 12} ${x + 12},${y} ${x},${y + 12} ${x - 12},${y}`} /> :
                    <rect x={x - 14} y={y - 14} width="28" height="28" rx="6" />}
                  <path className="graph-node-icon" d={appearance.path} transform={`translate(${x - 8} ${y - 8}) scale(.667)`} />
                  <circle className="graph-node-hit" cx={x} cy={y} r="22" />
                  <text x={x + 18} y={y + 4} textAnchor="start"><title>{label}</title>{shortLabel(label, 27)}</text>
                  <text className="graph-node-kind" x={x + 18} y={y + 20} textAnchor="start">{shortLabel(nodeCategory(n), 22)}{n.evidence_ids.length > 1 ? ` · ${n.evidence_ids.length} sources` : ''}</text>
                  {n.evidence_ids.length > 1 && <text className="graph-shared-label" x={x + 18} y={y + 35} textAnchor="start">Cross-source correlation</text>}
                </g>;
              })}
              </g>
              <GraphMotion graph={graph} selection={selection} view={view} onViewChange={onViewChange} />
            </svg>
          </div>
          <ul className="graph-legend" aria-label="Graph legend">
            {forensicTypes.map(type => <li key={type}><span style={{ background: graphAppearance(type).color }} aria-hidden="true" />{type === 'camera' ? 'video / camera' : type}</li>)}
            <li><span className="graph-legend-evidence" aria-hidden="true" />Evidence (Rect)</li>
            <li><span className="graph-legend-entity" aria-hidden="true" />Entity (Ellipse)</li>
            <li><span className="graph-legend-event" aria-hidden="true" />Event (Diamond)</li>
            <li><span className="graph-legend-edge" aria-hidden="true" />Candidate Relationship</li>
          </ul>
          <details className="context-help"><summary>Graph controls</summary><p>Select a node or line to inspect sources. Drag to rearrange or pan; scroll to zoom. Tab and Enter inspect records. Lines run from → to.</p></details>
          <details className="graph-record-browser"><summary>Browse graph records</summary><div className="graph-records">
            <div><h3>Nodes</h3>{visibleNodes.map(n => <button key={n.id} type="button" aria-pressed={node?.id === n.id}
              onClick={() => { void select({ kind: 'node', id: n.id }); }}>{n.kind}: {labels.get(n.id)}</button>)}</div>
            <div><h3>Candidate relationships</h3>{visibleEdges.map(e => <button key={e.id} type="button" aria-pressed={edge?.id === e.id}
              onClick={() => { void select({ kind: 'edge', id: e.id }); }}>{labels.get(e.from_id)} → {e.kind} → {labels.get(e.to_id)} · confidence {e.confidence.toFixed(2)}</button>)}</div>
          </div></details>
        </>}
      </div><aside className="graph-inspector" aria-label="Graph record details" aria-live="polite" onKeyDown={event => { if (event.key === 'Escape') dismiss?.(); }}>
        {!record ? <><h3>Record inspector</h3><p>Select a node or relationship to inspect sources.</p></> : <>
          <button className="graph-drawer-close" type="button" onClick={dismiss} aria-label="Close graph details">✕</button>
          <h3>{node ? 'Node details' : 'Candidate relationship details'}</h3>
          {node && !visibleIds.has(node.id) && <p>Selected node is hidden by the current filter.</p>}
          {edge && !visibleEdges.some(e => e.id === edge.id) && <p>Selected relationship is hidden by the current filter.</p>}
          {node && Array.isArray(node.properties?.source_node_ids) && node.properties.source_node_ids.length > 1 && <p>Grouped view of {node.properties.source_node_ids.length} source candidates. Each source record is retained; grouping is not identity verification.</p>}
          {node && isVisualCandidate(node) && <p className="scope-note">Unverified classifier candidate. A matching image region does not establish an object type, identity or real-world event. Detector scores are uncalibrated.</p>}
          <dl><dt>ID</dt><dd className="identifier">{record.id}</dd><dt>Kind</dt><dd>{node ? nodeCategory(node) : record.kind}</dd>
            {node && <><dt>Label</dt><dd>{labels.get(node.id)}</dd><dt>Entity type</dt><dd>{node.properties?.filename && ['image', 'video'].includes(String(node.properties.kind)) ? `${node.properties.kind} file` : node.entity_type || node.kind}</dd></>}
            {edge && <><dt>From → to</dt><dd className="identifier">{edge.from_id} → {edge.to_id}</dd><dt>Relationship confidence</dt><dd>{edge.confidence.toFixed(2)}</dd></>}
          </dl>
          {node?.properties && <dl>{Object.entries(node.properties).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl>}
          <h4>Source evidence IDs</h4><ul>{record.evidence_ids.map(id => <li key={id}>{source(id)}</li>)}</ul>
          {edge && <><h4>Observation citations</h4><ul>{edge.observation_ids.map(id => <li key={id} className="identifier">{id}</li>)}</ul>
            {state.citationStatus === 'loading' && <p role="status">Resolving historical source locators...</p>}
            {state.citationMessage && <p role="alert">{state.citationMessage}</p>}
            {state.citationStatus === 'error' && <button type="button" onClick={() => { void select({ kind: 'edge', id: edge.id }); }}>Retry citations</button>}
            {state.citations.map(item => <div key={item.id}><p className="identifier">Observation {item.id} · processing run {item.processing_run_id}</p>
              {source(item.evidence_id, item.source_locator, { source_locator: item.source_locator, observation_id: item.id, processing_run_id: item.processing_run_id })}</div>)}
            <details className="technical-details"><summary>Source references</summary><p>Locators refer to this analysis snapshot. File details and downloads use the current evidence record.</p></details>
          </>}
        </>}
      </aside></div>
      <button type="button" onClick={() => { void load(); }}>Refresh selected graph</button>
    </>}
  </section>;
}
