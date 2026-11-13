import { AnswerMarkdown } from './AnswerMarkdown';
import type { SourceFocus } from './mediaLocators';
import { useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createQuestionController } from './questionController';
import type { QuestionState } from './questionController';
import './QuestionAnswer.css';

export function QuestionAnswer({ caseId, inspectEvidence }: { caseId: string; inspectEvidence: (id: string, focus?: SourceFocus) => void }) {
  const client = useApiClient();
  const container = useRef<HTMLDivElement>(null);
  const controller = useMemo(() => createQuestionController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  useEffect(() => {
    const stream = container.current?.querySelector('.conversation-stream');
    if (stream) stream.scrollTop = stream.scrollHeight;
  }, [state.history?.length]);
  return <div ref={container}><QuestionAnswerPanel state={state} setQuestion={controller.setQuestion} submit={controller.submit} inspectEvidence={inspectEvidence} /></div>;
}

export function QuestionAnswerPanel({ state, setQuestion, submit, inspectEvidence }: {
  state: QuestionState; setQuestion: (question: string) => void; submit: () => Promise<void>;
  inspectEvidence: (id: string, focus?: SourceFocus) => void;
}) {
  const busy = state.status === 'submitting';
  const answers = state.history?.length ? state.history : state.answer ? [state.answer] : [];
  const prompts = ['Summarize recorded devices and vehicles', 'Identify temporal or location conflicts', 'Trace financial transactions', 'Show high-priority forensic leads'];
  return <section className="panel question-answer" aria-label="Case questions and answers" aria-busy={busy}>
    <h2>Ask about the evidence</h2>
    <details className="context-help"><summary>About answers</summary><p>Answers are AI-generated from available case evidence. Missing evidence does not establish that an event did not occur.</p></details>
    <details className="question-examples"><summary>Example questions</summary><div className="quick-prompts" aria-label="Suggested investigative questions">{prompts.map(prompt => <button key={prompt} type="button" disabled={busy} onClick={() => setQuestion(prompt)}>{prompt}<span aria-hidden="true"> ↗</span></button>)}</div></details>
    <form noValidate aria-busy={busy} onSubmit={event => { event.preventDefault(); void submit(); }}>
      <label htmlFor="case-question">Question about the evidence</label>
      <textarea id="case-question" name="question" maxLength={2000} rows={4} required
        placeholder="e.g. Which records mention this device?" value={state.question} disabled={busy}
        aria-invalid={state.status === 'error'} aria-describedby={state.message ? 'case-question-message' : undefined}
        onChange={event => setQuestion(event.currentTarget.value)} />
      <button type="submit" disabled={busy}>Ask question</button>
    </form>
    {busy && <p role="status">Searching case evidence...</p>}
    {state.message && <p id="case-question-message" role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void submit(); }}>Retry question</button>}
    <div className="conversation-stream" role="log" aria-label="Investigation conversation" aria-live="polite">{answers.map((answer, turn) => <article className="question-result" key={turn}>
      <div className="chat-question"><h3>Question</h3><p className="question-text">{answer.question}</p></div><div className="chat-answer"><span className="section-label">AI-generated answer</span>
      <p role="status"><strong className={`question-badge ${answer.supported ? 'question-supported' : 'question-unsupported'}`}>
        {answer.supported ? 'Supported by Evidence' : 'Insufficient Evidence'}
      </strong></p>
      <AnswerMarkdown text={answer.answer} citationIds={answer.citations.map((_, index) => `citation-${answer.case_id}-${turn}-${index + 1}`)} />
      <h3>Citations</h3>
      {answer.supported ? <ol className="question-citations">{answer.citations.map((citation, index) => <li key={index} id={`citation-${answer.case_id}-${turn}-${index + 1}`} tabIndex={-1}>
        <span className="section-label">SOURCE {index + 1}</span>
        <p className="question-text">{citation.claim}</p>
        <p className="question-text">Source locator: {citation.source_locator}</p>
        {citation.observation_id && <details className="technical-details"><summary>Observation reference</summary><p className="identifier">{citation.observation_id}</p></details>}
        <button type="button" aria-label={`Inspect source evidence ${citation.evidence_id}`}
          onClick={() => inspectEvidence(citation.evidence_id, { source_locator: citation.source_locator, observation_id: citation.observation_id })}>Open source {index + 1}</button>
      </li>)}</ol> : <p>No factual claims or citations were made. The available evidence is insufficient to answer this question.</p>}
      <details className="technical-details"><summary>Answer details</summary><p className="identifier">Retrieval version: {answer.retrieval_version}</p>
      {answer.provenance_id && <p className="identifier">Provenance: {answer.provenance_id}</p>}
      {answer.model_version && <p className="identifier">Model: {answer.model_version}</p>}</details>
    </div></article>)}</div>
  </section>;
}
