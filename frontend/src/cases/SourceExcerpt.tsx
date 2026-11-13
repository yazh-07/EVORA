import { useEffect, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { components } from '../api/schema';
import type { Evidence } from './evidenceStore';

/** Show physical source lines only when the locator explicitly supplies them. */
export function SourceExcerpt({ item, observation }: { item: Evidence; observation: components['schemas']['Observation'] }) {
  const client = useApiClient();
  const [state, setState] = useState<{ text?: string; error?: string }>({});
  const match = observation.source_locator.match(/^(?:rows?|lines?)[= ](\d+)(?:-(\d+))?(?:,|;|$)/);
  const start = match ? Number(match[1]) : undefined, end = match ? Number(match[2] ?? match[1]) : undefined;
  useEffect(() => {
    setState({});
    if (!start || !end || !Number.isSafeInteger(start) || !Number.isSafeInteger(end) || end < start || item.size_bytes > 2 * 1024 * 1024) return;
    const request = new AbortController();
    void client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
      path: { caseId: item.case_id, evidenceId: item.id }, responseType: 'blob', signal: request.signal,
    }).then(async blob => {
      const bytes = await blob.arrayBuffer();
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
      if (hash !== item.sha256 || bytes.byteLength !== item.size_bytes) throw Error();
      const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      if (text.includes('\0')) throw Error();
      const lines = text.split(/\r\n|\n|\r/);
      if (start > lines.length || end > lines.length) throw Error();
      if (!request.signal.aborted) setState({ text: lines.slice(start - 1, end).join('\n') });
    }).catch(() => { if (!request.signal.aborted) setState({ error: 'Original excerpt could not be verified. Use Download original.' }); });
    return () => request.abort();
  }, [client, item.id, item.case_id, item.sha256, item.size_bytes, start, end]);
  return <aside className="selected-record" aria-label="Selected source record"><h4>Source record</h4><p>{observation.source_locator}</p>
    {!start || !end || item.size_bytes > 2 * 1024 * 1024 ? <><pre>{observation.raw_value}</pre><p className="scope-note">Extracted value. Download the original to inspect its full context.</p></> : state.error ? <p role="alert">{state.error}</p> : state.text !== undefined ? <><pre>{state.text}</pre><p className="scope-note">Original source lines · size and SHA-256 verified.</p></> : <p role="status">Verifying source excerpt…</p>}
  </aside>;
}
