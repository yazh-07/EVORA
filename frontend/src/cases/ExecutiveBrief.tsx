import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';
import { createFindingController } from './findingController';
import { useAnalysisWorkspace } from './StartAnalysis';

type Finding = components['schemas']['Finding'];
type BriefState = { status: 'idle' | 'loading' | 'ready' | 'error'; findings: Finding[]; message: string };

/** Walk validated, pinned pages: a brief may appear after hundreds of ordinary findings. */
export function createExecutiveBriefController(client: ApiClient, caseId: string, runId: string) {
  const source = createFindingController(client, caseId, runId, undefined, 100);
  let state: BriefState = { status: 'idle', findings: [], message: '' };
  let collected: Finding[] = [];
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: BriefState) => { state = next; listeners.forEach(listener => listener()); };
  const load = () => { collected = []; return source.load(0); };
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    load,
    start() {
      if (unsubscribe) return;
      unsubscribe = source.subscribe(() => {
        const next = source.getSnapshot();
        if (next.status !== 'ready' || !next.page) {
          if (next.status === 'error') collected = [];
          publish({ status: next.status, findings: [], message: next.message });
          return;
        }
        collected.push(...next.page.items.filter(finding => finding.kind === 'hypothesis'));
        const offset = next.page.offset + next.page.items.length;
        if (offset < next.page.total) void source.load(offset);
        else publish({ status: 'ready', findings: collected, message: '' });
      });
      source.start();
    },
    dispose() { unsubscribe?.(); unsubscribe = undefined; source.dispose(); collected = []; listeners.clear(); },
  };
}

export function ExecutiveBrief() {
  const { caseId, analysis_run_id } = useAnalysisWorkspace();
  return analysis_run_id ? <PinnedExecutiveBrief key={`${caseId}:${analysis_run_id}`} caseId={caseId} runId={analysis_run_id} /> : null;
}

function PinnedExecutiveBrief({ caseId, runId }: { caseId: string; runId: string }) {
  const client = useApiClient();
  const controller = useMemo(() => createExecutiveBriefController(client, caseId, runId), [client, caseId, runId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  if (state.status === 'error') return <section className="panel" aria-label="Executive brief">
    <p role="alert">{state.message}</p><button type="button" onClick={() => { void controller.load(); }}>Retry executive brief</button>
  </section>;
  if (state.status !== 'ready') return <p role="status">Loading executive brief...</p>;
  return <ExecutiveBriefPanel findings={state.findings} />;
}

export function ExecutiveBriefPanel({ findings }: { findings: Finding[] }) {
  const hypotheses = findings.filter(finding => finding.kind === 'hypothesis');
  const generated = hypotheses.filter(finding => finding.details?.ai_generated);
  const visible = generated.length ? generated : hypotheses;
  if (!visible.length) return null;
  return <section className="panel executive-brief" aria-labelledby="executive-brief-heading">
    <span className="section-label">INVESTIGATIVE HYPOTHESIS</span>
    <h2 id="executive-brief-heading">AI Forensic Executive Brief</h2>
    <p>{generated.length ? 'AI-generated hypothesis. Verify the narrative against the source evidence.' :
      'Deterministic hypotheses from the selected analysis. These explanations require verification.'}</p>
    {visible.map(finding => <article key={finding.id}>
      <h3>{finding.summary.replace(/^AI Forensic Executive Brief:\s*/, '')}</h3>
      {finding.details?.hypothesis && <p className="executive-hypothesis">{finding.details.hypothesis}</p>}
      {finding.details?.ai_generated && <p className="filter-scope">Model: {finding.details.model}</p>}
    </article>)}
  </section>;
}
