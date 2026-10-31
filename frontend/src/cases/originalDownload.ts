import type { ApiClient } from '../api/client';
import { ApiHttpError } from '../api/client';
import type { Evidence } from './evidenceStore';

export type DownloadState = { status: 'idle' | 'loading' | 'ready' | 'error'; message: string };
export function saveOriginal(blob: Blob, filename: string): () => void {
  const url = URL.createObjectURL(blob);
  let timer: ReturnType<typeof setTimeout>;
  const release = () => { clearTimeout(timer); URL.revokeObjectURL(url); };
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.replace(/[\\/<>:"|?*\u0000-\u001f]/g, '_');
  try {
    document.body.append(link); link.click();
    timer = setTimeout(release, 1000);
  } catch (error) { release(); throw error; }
  finally { link.remove(); }
  return release;
}
export function createOriginalDownload(client: ApiClient, item: Evidence, save = saveOriginal) {
  let state: DownloadState = { status: 'idle', message: '' };
  let disposed = false;
  let request: AbortController | undefined;
  let release: (() => void) | undefined;
  const session = client.getSessionVersion();
  const listeners = new Set<() => void>();
  const active = () => !disposed && session === client.getSessionVersion() && client.hasToken();
  const publish = (next: DownloadState) => { if (active()) { state = next; listeners.forEach(listener => listener()); } };
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() { disposed = false; },
    async download() {
      if (!active() || state.status === 'loading') return;
      request = new AbortController();
      release?.(); release = undefined;
      const pending = request;
      publish({ status: 'loading', message: 'Retrieving original bytes...' });
      try {
        const blob = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
          path: { caseId: item.case_id, evidenceId: item.id }, responseType: 'blob', signal: pending.signal,
        });
        if (!active() || pending.signal.aborted) return;
        const bytes = await blob.arrayBuffer();
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
        if (!active() || pending.signal.aborted) return;
        if (blob.size !== item.size_bytes || digest !== item.sha256) {
          publish({ status: 'error', message: 'Original bytes do not match the recorded size or SHA-256. Download stopped.' }); return;
        }
        release = save(blob, item.filename);
        publish({ status: 'ready', message: 'Original verified against recorded size and SHA-256; download requested. Check your browser downloads.' });
      } catch (error) {
        if (!active() || pending.signal.aborted) return;
        publish({ status: 'error', message: error instanceof ApiHttpError && error.status === 404
          ? 'Original unavailable or no longer accessible. Refresh evidence and try again.'
          : 'Could not download the original. Check your connection and try again.' });
      }
    },
    dispose() { disposed = true; request?.abort(); release?.(); release = undefined; listeners.clear(); state = { status: 'idle', message: '' }; },
  };
}
