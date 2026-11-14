import { AnswerMarkdown } from './AnswerMarkdown';
import type { SourceFocus } from './mediaLocators';
import { useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createQuestionController } from './questionController';
import type { QuestionState } from './questionController';
import './QuestionAnswer.css';

export function QuestionAnswer({ caseId, inspectEvidence, activeView = true }: { caseId: string; activeView?: boolean; inspectEvidence: (id: string, focus?: SourceFocus) => void }) {
  const client = useApiClient();
  const container = useRef<HTMLDivElement>(null);
  const controller = useMemo(() => createQuestionController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  useEffect(() => {
    if (!activeView) return;
    const stream = container.current?.querySelector('.conversation-stream');
    if (stream) stream.scrollTop = stream.scrollHeight;
  }, [state.history?.length, state.status, activeView]);
  useEffect(() => {
    if (activeView && state.status === 'ready') container.current?.querySelector<HTMLTextAreaElement>('textarea')?.focus({ preventScroll: true });
  }, [state.status, activeView]);
  const focusComposer = () => requestAnimationFrame(() => container.current?.querySelector<HTMLTextAreaElement>('textarea')?.focus({ preventScroll: true }));
  return <div className="case-chat" ref={container}><QuestionAnswerPanel state={state} setQuestion={controller.setQuestion} submit={controller.submit} cancel={() => { controller.cancel(); focusComposer(); }} clear={() => { controller.clear(); focusComposer(); }} inspectEvidence={inspectEvidence} /></div>;
}

export function QuestionAnswerPanel({ state, setQuestion, submit, cancel, clear, inspectEvidence }: {
  state: QuestionState; setQuestion: (question: string) => void; submit: () => Promise<void>;
  cancel?: () => void; clear?: () => void;
  inspectEvidence: (id: string, focus?: SourceFocus) => void;
}) {
  const busy = state.status === 'submitting';
  const answers = state.history?.length ? state.history : state.answer ? [state.answer] : [];
  const prompts = ['Summarize the evidence', 'Show recorded locations'];
  return <section className="panel question-answer" aria-label="Case conversation">
    <header className="chat-heading"><h2>Ask</h2>{!!answers.length && <button type="button" className="quiet-button" onClick={clear}>New chat</button>}</header>
    <div className="conversation-stream" role="log" aria-label="Investigation conversation" aria-live="polite" aria-busy={busy}>
      {!answers.length && !busy && <div className="chat-empty"><h3>Ask about this case</h3><div className="quick-prompts" aria-label="Suggested questions">{prompts.map(prompt => <button key={prompt} type="button" onClick={() => setQuestion(prompt)}>{prompt}</button>)}</div></div>}
      {answers.map((answer, turn) => {
        const references = answer.references?.filter(reference => !answer.supported || reference.usage === 'cited') ?? [];
        return <article className="question-result" key={turn}>
        <div className="chat-question"><span className="sr-only">You</span><p className="question-text">{answer.question}</p></div>
        <div className="chat-answer"><span className="chat-sender">EVORA</span>
          {answer.answer_status === 'unavailable' ? <span className="question-badge question-unsupported">Reply unavailable</span>
            : answer.answer_status === 'source_records' ? <span className="question-badge">Source records</span>
            : !answer.supported && answer.answer_status !== 'conversation' && <span className="question-badge question-unsupported">{answer.answer_status === 'no_evidence' ? 'Evidence needed' : 'No matching evidence'}</span>}
          <AnswerMarkdown text={answer.answer} citationIds={answer.citations.map((_, index) => `citation-${answer.case_id}-${turn}-${index + 1}`)} />
          <section className="chat-references" aria-label="References"><h4>References</h4>
            {!!references.length && <p className="references-scope">{references.some(reference => reference.usage === 'cited') ? 'Used in this reply' : 'Reviewed records · no verified answer'}{answer.references_total && answer.references_total > references.length ? ` · ${answer.references_total} records searched` : ''}</p>}
            {references.length ? <ul>{references.slice(0, 3).map(reference => <li key={reference.observation_id}>
              <button type="button" className="text-action" onClick={() => inspectEvidence(reference.evidence_id, { observation_id: reference.observation_id, source_locator: reference.source_locator })}>{reference.filename}</button>
              <span className="source-locator">{reference.source_locator} · {reference.usage === 'cited' ? 'Used' : 'Reviewed'}</span>
              <blockquote>{reference.excerpt.length > 240 ? reference.excerpt.slice(0, 240) + '…' : reference.excerpt}</blockquote>
            </li>)}</ul> : <p>{answer.answer_status === 'conversation' ? 'No evidence needed for this reply.' : answer.citations.length ? `${answer.citations.length} cited records · open Sources below.` : 'No matching references used.'}</p>}
            {(references.length ?? 0) > 3 && <details><summary>More references ({references.length - 3})</summary><ul>{references.slice(3).map(reference => <li key={reference.observation_id}><button type="button" className="text-action" onClick={() => inspectEvidence(reference.evidence_id, { observation_id: reference.observation_id, source_locator: reference.source_locator })}>{reference.filename}</button><span className="source-locator">{reference.source_locator} · {reference.usage === 'cited' ? 'Used' : 'Reviewed'}</span><blockquote>{reference.excerpt}</blockquote></li>)}</ul></details>}
          </section>
          {answer.supported && <details className="chat-sources"><summary>Sources ({answer.citations.length})</summary><ol className="question-citations">{answer.citations.map((citation, index) => <li key={index} data-observation-id={citation.observation_id} id={`citation-${answer.case_id}-${turn}-${index + 1}`} tabIndex={-1}>
            <p>{citation.claim}</p><p className="source-locator">{citation.source_locator}</p>
            <button type="button" aria-label={`Open source ${index + 1}`} onClick={() => inspectEvidence(citation.evidence_id, { source_locator: citation.source_locator, observation_id: citation.observation_id })}>Open source {index + 1}</button>
          </li>)}</ol></details>}
          <details className="answer-information"><summary>Response information</summary><dl><dt>Retrieval</dt><dd>{answer.retrieval_version}</dd>{answer.model_version && <><dt>Model</dt><dd>{answer.model_version}</dd></>}{answer.provenance_id && <><dt>Reference</dt><dd>{answer.provenance_id}</dd></>}</dl></details>
        </div>
      </article>; })}
      {busy && <article className="question-result"><div className="chat-question"><p className="question-text">{state.question.trim()}</p></div><div className="chat-answer"><span className="chat-sender">EVORA</span><p className="chat-thinking" role="status">Searching evidence<span aria-hidden="true">…</span></p></div></article>}
    </div>
    {state.message && <p id="case-question-message" role="alert">{state.message}{state.status === 'error' && <button type="button" className="text-action" onClick={() => { void submit(); }}>Retry</button>}</p>}
    <form className="chat-composer" noValidate onSubmit={event => { event.preventDefault(); void submit(); }}>
      <label className="sr-only" htmlFor="case-question">Message about this case</label>
      <textarea id="case-question" name="question" maxLength={2000} rows={2} required placeholder="Ask a question or follow up…" value={state.question} disabled={busy}
        aria-invalid={state.status === 'error'} aria-describedby={state.message ? 'case-question-message' : undefined}
        onChange={event => setQuestion(event.currentTarget.value)} onKeyDown={event => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!busy && state.question.trim()) void submit(); }
        }} />
      {busy ? <button key="stop" type="button" className="chat-send" onClick={event => { event.preventDefault(); cancel?.(); }} aria-label="Stop response">Stop</button> : <button key="send" type="submit" className="chat-send" disabled={!state.question.trim()} aria-label="Send message">Send <span aria-hidden="true">↑</span></button>}
    </form>
  </section>;
}
