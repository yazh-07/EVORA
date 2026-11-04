import { useEffect, useId, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { Evidence } from './evidenceStore';
import { createTranscriptController, transcriptOffsets, transcriptRoot } from './transcriptController';
import './TranscriptViewer.css';

type Controller = ReturnType<typeof createTranscriptController>;
type PanelProps = { state: ReturnType<Controller['getSnapshot']> } & Pick<Controller,
  'load' | 'loadHistory' | 'setQuery' | 'toggleHistory' | 'setDraft' | 'submit' | 'download'> & {
  mediaKind: 'audio' | 'video'; filename: string; idPrefix?: string;
};
export function TranscriptViewer({ item, refreshKey, onDerivedRun }: {
  item: Evidence; refreshKey?: string; onDerivedRun?: (runId: string) => void;
}) {
  const client = useApiClient();
  const idPrefix = useId();
  const controller = useMemo(() => createTranscriptController(client, item, { onDerivedRun }), [client, item, refreshKey, onDerivedRun]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <TranscriptPanel {...controller} state={state} mediaKind={item.kind === 'video' ? 'video' : 'audio'} filename={item.filename} idPrefix={idPrefix} />;
}
function timestamp(milliseconds: number) {
  const hours = Math.floor(milliseconds / 3600000);
  const minutes = Math.floor(milliseconds / 60000) % 60;
  const seconds = Math.floor(milliseconds / 1000) % 60;
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${(milliseconds % 1000).toString().padStart(3, '0')}`;
}
function highlighted(text: string, query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return text;
  const lower = text.toLowerCase();
  const parts = [];
  let position = 0, index: number;
  while ((index = lower.indexOf(needle, position)) !== -1) {
    parts.push(text.slice(position, index), <mark key={index}>{text.slice(index, index + needle.length)}</mark>);
    position = index + needle.length;
  }
  parts.push(text.slice(position));
  return parts;
}
export function TranscriptPanel({ state, load, loadHistory, setQuery, toggleHistory, setDraft, submit, download,
  mediaKind, filename, idPrefix = 'transcript' }: PanelProps) {
  const needle = state.query.trim().toLowerCase();
  const segments = state.segments.filter(segment => segment.normalized_value.toLowerCase().includes(needle));
  const writing = Object.values(state.histories).some(history => history.submission === 'submitting');
  const searchId = `${idPrefix}-search`;
  return <section className="transcript-viewer" aria-label="Source transcript" aria-busy={state.status === 'loading'}>
    <h3>Transcript</h3>
    <p>Latest completed transcript for this evidence. Verify text against the source. Extraction confidence is a model score, not source reliability.</p>
    <div className="transcript-source" aria-busy={state.media.status === 'loading'}>
      <button type="button" disabled={state.media.status === 'loading'} onClick={() => { void download(); }}>
        {state.media.status === 'loading' ? 'Loading source media...' : mediaKind === 'video' ? 'Watch / Download video' : 'Listen / Download audio'}
      </button>
      {state.media.status === 'error' && <p role="alert">{state.media.message}</p>}
      {state.media.status === 'loading' && <p role="status">Verifying original source bytes...</p>}
      {state.sourceUrl && <>
        {mediaKind === 'video' ? <video controls preload="metadata" src={state.sourceUrl} aria-label="Original source video" />
          : <audio controls preload="metadata" src={state.sourceUrl} aria-label="Original source audio" />}
        <a href={state.sourceUrl} download={filename.replace(/[\\/<>:"|?*\u0000-\u001f]/g, '_')}>Download original {mediaKind}</a>
        <p role="status">Original source verified against recorded size and SHA-256.</p>
      </>}
    </div>
    <label htmlFor={searchId}>Search transcript</label>
    <input id={searchId} type="search" value={state.query} onChange={event => setQuery(event.currentTarget.value)} placeholder="Filter transcript text..." />
    {state.status === 'loading' && <p role="status">Loading transcript...</p>}
    {state.message && <><p role="alert">{state.message}</p><button type="button" onClick={() => { void load(); }}>Retry transcript</button></>}
    {state.status === 'ready' && <>
      <p role="status">{segments.length} of {state.segments.length} transcript segments.</p>
      {state.segments.length === 0 ? <p>No transcript segments are available. Audio may be silent, unavailable, or awaiting transcription.</p>
        : segments.length === 0 && <p>No transcript segments match your search.</p>}
      <ol className="transcript-segments">{segments.map(segment => {
        const root = transcriptRoot(segment), history = state.histories[root];
        const offsets = transcriptOffsets(segment.source_locator);
        const textId = `${idPrefix}-${root}-text`, reasonId = `${idPrefix}-${root}-reason`, messageId = `${idPrefix}-${root}-message`;
        const invalid = history?.submission === 'error';
        return <li key={root}>
          <p className="transcript-offset"><strong>{offsets ? `${timestamp(offsets[0])} – ${timestamp(offsets[1])}` : segment.source_locator}</strong>
            {offsets && <span> ({offsets[0]}–{offsets[1]} ms from original media start)</span>}</p>
          <p className="transcript-text">{highlighted(segment.normalized_value, state.query)}</p>
          <p>Extraction confidence: {segment.extraction_confidence}{segment.transcript_revision_id && ' · Human corrected'}</p>
          <details open={history?.open ?? false} onToggle={event => toggleHistory(root, event.currentTarget.open)}>
            <summary>Correction &amp; History</summary>
            {history?.status === 'loading' && <p role="status">Loading revision history...</p>}
            {history?.status === 'error' && <><p role="alert">{history.message}</p>
              <button type="button" disabled={writing} onClick={() => { void loadHistory(root); }}>Retry revision history</button></>}
            {history?.status === 'ready' && <>
              <h4>Revision history (oldest first)</h4>
              <p className="transcript-text">Original machine text: {segment.raw_value}</p>
              {history.revisions.length === 0 ? <p>No corrections recorded for this segment.</p> : <ol className="transcript-revisions">
                {history.revisions.map(revision => <li key={revision.id}>
                  <p>Actor: {revision.actor_id} · <time dateTime={revision.created_at}>{revision.created_at}</time></p>
                  <p className="transcript-text">{revision.corrected_text}</p><p className="transcript-text">Reason: {revision.reason}</p>
                </li>)}
              </ol>}
              <form noValidate aria-label={`Correct segment at ${offsets ? timestamp(offsets[0]) : segment.source_locator}`}
                aria-busy={history.submission === 'submitting'} onSubmit={event => { event.preventDefault(); void submit(root); }}>
                <fieldset disabled={writing || history.submission === 'conflict'}>
                  <legend>Append a correction</legend>
                  <label htmlFor={textId}>Corrected text</label>
                  <textarea id={textId} value={history.correctedText} rows={4} required maxLength={20000} aria-invalid={invalid}
                    aria-describedby={history.message ? messageId : undefined} onChange={event => setDraft(root, 'correctedText', event.currentTarget.value)} />
                  <label htmlFor={reasonId}>Reason</label>
                  <input id={reasonId} type="text" value={history.reason} required maxLength={2000} aria-invalid={invalid}
                    aria-describedby={history.message ? messageId : undefined} onChange={event => setDraft(root, 'reason', event.currentTarget.value)} />
                  <button type="submit">{history.submission === 'submitting' ? 'Saving correction...' : 'Submit correction'}</button>
                </fieldset>
              </form>
              {history.message && <p id={messageId} role="alert">{history.message}</p>}
              {history.submission === 'conflict' && <button type="button" disabled={writing} onClick={() => { void load(); }}>Reload transcript and history</button>}
              {history.submission === 'success' && <p role="status">Correction saved in a new processing output. Start a new case analysis to include it.</p>}
            </>}
          </details>
        </li>;
      })}</ol>
      <button type="button" disabled={writing} onClick={() => { void load(); }}>Refresh transcript</button>
    </>}
  </section>;
}
