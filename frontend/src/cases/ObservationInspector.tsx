import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createObservationController } from './observationController';
import type { ObservationState } from './observationController';

export function ObservationInspector({ caseId, evidenceId, processingRunId, refreshKey }: {
  caseId: string; evidenceId: string; processingRunId?: string; refreshKey?: string;
}) {
  const client = useApiClient();
  const controller = useMemo(() => createObservationController(client, caseId, evidenceId, processingRunId),
    [client, caseId, evidenceId, processingRunId, refreshKey]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <ObservationPanel state={state} load={controller.load} processingRunId={processingRunId} />;
}

export function ObservationPanel({ state, load, processingRunId }: {
  state: ObservationState; load: (offset?: number) => Promise<void>; processingRunId?: string;
}) {
  const page = state.page;
  return <section aria-label="Extracted observations" aria-busy={state.status === 'loading'}>
    <h3>Extracted observations</h3>
    <p>Source observations are unverified. Extraction confidence is not source reliability or proof of a conclusion.</p>
    <p>{processingRunId ? `Completed processing run: ${processingRunId}` : 'Latest completed observations for this evidence.'}</p>
    {state.status === 'loading' && <p role="status">Loading observations...</p>}
    {state.message && <><p role="alert">{state.message}</p><button type="button" onClick={() => { void load(); }}>Retry observations</button></>}
    {state.status === 'ready' && page && <>
      <p role="status">{page.total} observations. Showing {page.items.length} on this page.</p>
      {page.total === 0 ? <p>No completed observations for this evidence. Start processing to extract observations.</p> : <>
        {page.items.length === 0 && <p>No observations on this page. Return to the previous page or refresh.</p>}
        <div role="region" aria-label="Observation table" tabIndex={0} style={{ overflowX: 'auto' }}>
          <table><caption>Extracted source values</caption><thead><tr>
            {['Kind', 'Source locator', 'Raw value', 'Normalized value', 'Observed time (raw)', 'Observed time (UTC)', 'Extraction confidence', 'Processing run'].map(label => <th key={label} scope="col">{label}</th>)}
          </tr></thead><tbody>{page.items.map(item => <tr key={item.id}>
            <td>{item.kind}</td><td className="identifier">{item.source_locator}</td>
            <td style={{ whiteSpace: 'pre-wrap' }}>{item.raw_value}</td><td style={{ whiteSpace: 'pre-wrap' }}>{item.normalized_value}</td>
            <td>{item.observed_at_raw ?? 'Not provided'}</td><td>{item.observed_at_utc ?? 'Not provided'}</td>
            <td>{item.extraction_confidence}</td><td className="identifier">{item.processing_run_id}</td>
          </tr>)}</tbody></table>
        </div>
      </>}
      <nav className="pagination" aria-label="Observation pages">
        <button type="button" disabled={page.offset === 0} onClick={() => { void load(Math.max(0, page.offset - page.limit)); }}>Previous</button>
        <button type="button" disabled={page.offset + page.limit >= page.total} onClick={() => { void load(page.offset + page.limit); }}>Next</button>
      </nav>
      <button type="button" onClick={() => { void load(0); }}>Refresh observations</button>
    </>}
  </section>;
}
