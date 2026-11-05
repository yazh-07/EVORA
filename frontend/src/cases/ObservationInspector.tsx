import type { SourceFocus } from './mediaLocators';
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createObservationController } from './observationController';
import type { ObservationState } from './observationController';
import { ReliabilityInspector } from './ReliabilityInspector';

export function ObservationInspector({ caseId, evidenceId, processingRunId, refreshKey, focus }: {
  caseId: string; evidenceId: string; processingRunId?: string; refreshKey?: string; focus?: SourceFocus;
}) {
  const client = useApiClient();
  const controller = useMemo(() => createObservationController(client, caseId, evidenceId, processingRunId, focus),
    [client, caseId, evidenceId, processingRunId, refreshKey, focus]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <ObservationPanel state={state} load={controller.load} processingRunId={focus ? state.page?.items[0]?.processing_run_id : processingRunId} evidenceId={evidenceId} focus={focus} />;
}

export function ObservationPanel({ state, load, processingRunId, evidenceId, focus }: {
  state: ObservationState; load: (offset?: number) => Promise<void>; processingRunId?: string;
  evidenceId?: string; focus?: SourceFocus;
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
      {evidenceId && <ReliabilityInspector evidenceId={evidenceId} observations={page.items}
        observationScope={`Extraction scores cover ${page.items.length} of ${page.total} observations on the current observations page. Corroboration findings are available through Findings & Citations.`} />}
      {page.total === 0 ? <p>No completed observations for this evidence. Start processing to extract observations.</p> : <>
        {page.items.length === 0 && <p>No observations on this page. Return to the previous page or refresh.</p>}
        <div role="region" aria-label="Observation table" tabIndex={0} style={{ overflowX: 'auto' }}>
          <table><caption>Extracted source values</caption><thead><tr>
            {['Kind', 'Source locator', 'Raw value', 'Normalized value', 'Observed time (raw)', 'Observed time (UTC)', 'Extraction confidence', 'Processing run'].map(label => <th key={label} scope="col">{label}</th>)}
          </tr></thead><tbody>{page.items.map(item => <tr key={item.id} className={focus && (focus.observation_id === item.id || focus.source_locator === item.source_locator) ? 'source-highlight' : undefined}>
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
