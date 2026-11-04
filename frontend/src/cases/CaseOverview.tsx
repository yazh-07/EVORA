import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createCaseOverviewController, evidenceKinds, overviewStatuses } from './caseOverviewController';
import type { CaseOverviewState } from './caseOverviewController';

export function CaseOverview({ caseId }: { caseId: string }) {
  const client = useApiClient();
  const controller = useMemo(() => createCaseOverviewController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <CaseOverviewPanel state={state} load={controller.load} />;
}

export function CaseOverviewPanel({ state, load }: { state: CaseOverviewState; load: () => Promise<void> }) {
  const summary = state.summary;
  return <section className="panel case-overview" aria-label="Case evidence overview" aria-busy={state.status === 'loading'}>
    <h2>Case evidence overview</h2>
    <p>Latest processing attempt per evidence item. Live counts at refresh; processing completion does not verify evidence or conclusions.</p>
    {state.status === 'loading' && <p role="status">Loading complete case overview...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'ready' && summary && <>
      <p className="overview-total" role="status">Total evidence items: <strong>{summary.total}</strong></p>
      {summary.total === 0 && <p>No evidence uploaded yet.</p>}
      <div className="overview-breakdowns">
        {([
          ['Evidence kind', evidenceKinds, summary.kinds],
          ['Processing status', overviewStatuses, summary.statuses],
        ] as const).map(([label, keys, counts]) => <div key={label}>
          <h3>{label}</h3>
          <dl>
            {keys.map(key => <div key={key}>
              <dt>{key.replaceAll('_', ' ')}</dt><dd>{counts[key as keyof typeof counts]}</dd>
            </div>)}
          </dl>
        </div>)}
      </div>
    </>}
    <button type="button" disabled={state.status === 'loading'} onClick={() => { void load(); }}>Refresh overview</button>
  </section>;
}
