import { useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { Evidence } from './evidenceStore';

export function OriginalTextPreview({ item }: { item: Evidence }) {
  const client = useApiClient();
  const [state, setState] = useState<{ text?: string; message?: string; loading?: boolean }>({});
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  const preview = async () => {
    if (state.loading) return;
    const request = new AbortController(); pending.current = request;
    const session = client.getSessionVersion();
    const current = () => !request.signal.aborted && session === client.getSessionVersion() && client.hasToken();
    setState({ loading: true });
    try {
      const blob = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', { path: { caseId: item.case_id, evidenceId: item.id }, responseType: 'blob', signal: request.signal });
      const bytes = await blob.arrayBuffer();
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('');
      if (!current()) return;
      if (hash !== item.sha256 || bytes.byteLength !== item.size_bytes) throw Error();
      const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      if (text.includes('\0')) throw Error();
      setState({ text, message: 'Original bytes verified against the recorded SHA-256. Displayed as plain text.' });
    } catch { if (current()) setState({ message: 'Preview unavailable: the original could not be verified or is not UTF-8 text. Use Download original to inspect it with an appropriate tool.' }); }
  };
  if (['image', 'video', 'audio'].includes(item.kind)) return null;
  return <section className="original-text-preview" aria-label="Original source text">
    <h3>Original source</h3>
    {item.size_bytes > 2 * 1024 * 1024 ? <p>Use Download original for this file. Inline text preview is limited to 2 MB.</p> : <button type="button" disabled={state.loading} onClick={() => { void preview(); }}>{state.loading ? 'Verifying original…' : 'Preview original text'}</button>}
    {state.message && <p role="status">{state.message}</p>}
    {state.text !== undefined && <pre tabIndex={0}>{state.text.slice(0, 100000)}</pre>}
    {state.text && state.text.length > 100000 && <p>Preview shows the first 100,000 characters. Download the original for the complete source.</p>}
  </section>;
}
