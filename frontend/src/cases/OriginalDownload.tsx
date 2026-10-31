import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createOriginalDownload } from './originalDownload';
import type { Evidence } from './evidenceStore';
export function OriginalDownload({ item }: { item: Evidence }) {
  const client = useApiClient();
  const download = useMemo(() => createOriginalDownload(client, item), [client, item]);
  const state = useSyncExternalStore(download.subscribe, download.getSnapshot, download.getSnapshot);
  useEffect(() => { download.start(); return () => download.dispose(); }, [download]);
  return <div aria-busy={state.status === 'loading'}>
    <button type="button" disabled={state.status === 'loading'} onClick={() => { void download.download(); }}>
      {state.status === 'loading' ? 'Retrieving original...' : 'Download original'}
    </button>
    {state.message && <p role={state.status === 'error' ? 'alert' : 'status'}>{state.message}</p>}
  </div>;
}
