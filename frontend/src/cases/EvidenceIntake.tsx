import { useEffect, useRef, useState } from 'react';
import { evidenceKinds } from './evidenceStore';
import type { Evidence } from './evidenceStore';
import { detectEvidenceKind } from './evidenceDetection';

type IntakeItem = { id: number; file: File; kind: Evidence['kind']; label: string; detecting: boolean; status: 'ready' | 'uploading' | 'uploaded' | 'failed' };
export function formatSupport(filename: string, kind: string): string {
  const extension = filename.split('.').at(-1)?.toLowerCase();
  if (kind === 'audio') return 'Original storage supported. Automatic audio extraction is not available; existing transcripts can be reviewed.';
  if (kind === 'document' && ['pdf', 'docx', 'doc', 'pcap', 'pcapng', 'bin', 'raw', 'dump'].includes(extension ?? '')) return 'Original storage only. This format has no document extractor yet; processing supports UTF-8 text.';
  if (['gps', 'network_log', 'mobile_log', 'transaction', 'message'].includes(kind)) return 'Extraction requires the supported CSV header and layout. The selected kind will be validated during processing.';
  if (kind === 'image' || kind === 'video') return 'Decodable media can be processed for visual candidates. Codec support is checked during processing.';
  return 'Document extraction supports UTF-8 plain text. The original is retained separately.';
}
export function EvidenceIntake({ upload, submitting }: { upload: (file: File | null, kind: string, label: string, acquired: string) => Promise<boolean>; submitting: boolean }) {
  const [items, setItems] = useState<IntakeItem[]>([]);
  const [busy, setBusy] = useState(false), [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState(''), [acquired, setAcquired] = useState('');
  const sequence = useRef(0), alive = useRef(true), running = useRef(false);
  const readers = useRef(new Map<number, () => void>());
  useEffect(() => { alive.current = true; return () => { alive.current = false; readers.current.forEach(cancel => cancel()); readers.current.clear(); }; }, []);
  const patch = (id: number, values: Partial<IntakeItem>) => { if (alive.current) setItems(current => current.map(item => item.id === id ? { ...item, ...values } : item)); };
  const add = (files: File[]) => {
    if (running.current || submitting) return;
    setMessage('');
    const added: IntakeItem[] = files.map(file => ({ id: ++sequence.current, file, label: file.name.slice(0, 200), kind: 'document', detecting: true, status: 'ready' }));
    setItems(current => [...current, ...added]);
    for (const item of added) readers.current.set(item.id, detectEvidenceKind(item.file, kind => patch(item.id, { kind }), () => patch(item.id, { detecting: false })));
  };
  const pending = items.filter(item => item.status !== 'uploaded');
  const start = async () => {
    if (running.current || submitting || !pending.length || items.some(item => item.detecting)) return;
    if (pending.some(item => !item.label.trim())) { setMessage('Give each source a label before uploading.'); return; }
    running.current = true; setBusy(true); setMessage('');
    let uploaded = 0;
    try {
      for (const item of pending) {
        if (!alive.current) return;
        patch(item.id, { status: 'uploading' });
        const ok = await upload(item.file, item.kind, item.label, acquired);
        if (!alive.current) return;
        patch(item.id, { status: ok ? 'uploaded' : 'failed' });
        if (!ok) { setMessage('Upload stopped on this source. Check the error below and retry the remaining files. Confirmed uploads will not be repeated.'); return; }
        uploaded++;
      }
      setMessage(`${uploaded} ${uploaded === 1 ? 'source uploaded' : 'sources uploaded'}. Select a source in the library to inspect it and start extraction.`);
    } finally { running.current = false; if (alive.current) setBusy(false); }
  };
  return <div className="batch-intake" aria-busy={busy}>
    <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); add(Array.from(event.dataTransfer.files)); }}>
      <span className="drop-icon" aria-hidden="true">＋</span><h3>Add original files</h3><p>Drop original files here, or choose files from your device.</p>
      <label className="file-picker">Choose files<input id="batch-evidence-files" type="file" multiple disabled={busy || submitting} onChange={event => { add(Array.from(event.target.files ?? [])); event.target.value = ''; }} /></label>
      <small>Original bytes and SHA-256 are recorded on intake. Extraction is a separate step.</small>
    </div>
    {!!items.length && <>
      <ol className="intake-queue">{items.map(item => <li key={item.id}><div><strong>{item.file.name}</strong><small>{(item.file.size / 1024).toFixed(1)} KB · {item.detecting ? 'Checking file type…' : item.status}</small></div>
        <label>Source label<input maxLength={200} value={item.label} disabled={busy || item.status === 'uploaded'} onChange={event => patch(item.id, { label: event.target.value })} /></label>
        <label>Evidence kind<select value={item.kind} disabled={busy || item.status === 'uploaded'} onChange={event => { readers.current.get(item.id)?.(); patch(item.id, { kind: event.target.value as Evidence['kind'], detecting: false }); }}>{evidenceKinds.map(kind => <option key={kind} value={kind}>{kind.replaceAll('_', ' ')}</option>)}</select></label>
        <button type="button" disabled={busy} aria-label={`Remove ${item.file.name} from upload queue`} onClick={() => { readers.current.get(item.id)?.(); readers.current.delete(item.id); setItems(current => current.filter(row => row.id !== item.id)); }}>Remove</button>
        <p className="format-support">{formatSupport(item.file.name, item.kind)}</p>
      </li>)}</ol>
      <label className="acquisition-field">Acquired at (optional, UTC)<input type="datetime-local" value={acquired} disabled={busy} onChange={event => setAcquired(event.target.value)} /><small>Applies to remaining uploads. Leave blank if unknown.</small></label>
      <button className="button-primary" type="button" disabled={busy || submitting || !pending.length || items.some(item => item.detecting)} onClick={() => { void start(); }}>{busy ? 'Uploading originals…' : `Upload ${pending.length} ${pending.length === 1 ? 'source' : 'sources'}`}</button>
    </>}
    {message && <p role="status">{message}</p>}
  </div>;
}
