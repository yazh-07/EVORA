import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createQuestionController } from './questionController';
import type { QuestionState } from './questionController';
import './QuestionAnswer.css';

export function QuestionAnswer({ caseId, inspectEvidence }: { caseId: string; inspectEvidence: (id: string) => void }) {
  const client = useApiClient();
  const controller = useMemo(() => createQuestionController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <QuestionAnswerPanel state={state} setQuestion={controller.setQuestion} submit={controller.submit} inspectEvidence={inspectEvidence} />;
}

export function QuestionAnswerPanel({ state, setQuestion, submit, inspectEvidence }: {
  state: QuestionState; setQuestion: (question: string) => void; submit: () => Promise<void>;
  inspectEvidence: (id: string) => void;
}) {
  const busy = state.status === 'submitting';
  const answer = state.answer;
  return <section className="panel question-answer" aria-label="Case questions and answers" aria-busy={busy}>
    <h2>Questions &amp; Answers</h2>
    <p>Ask about recorded entities or events. Answers depend on available case evidence; missing evidence does not establish that an event did not occur.</p>
    <form noValidate aria-busy={busy} onSubmit={event => { event.preventDefault(); void submit(); }}>
      <label htmlFor="case-question">Inquire about case evidence</label>
      <textarea id="case-question" name="question" maxLength={2000} rows={4} required
        placeholder="Ask a question about extracted entities or events..." value={state.question} disabled={busy}
        aria-invalid={state.status === 'error'} aria-describedby={state.message ? 'case-question-message' : undefined}
        onChange={event => setQuestion(event.currentTarget.value)} />
      <button type="submit" disabled={busy}>Ask question</button>
    </form>
    {busy && <p role="status">Searching case evidence...</p>}
    {state.message && <p id="case-question-message" role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void submit(); }}>Retry question</button>}
    {state.status === 'ready' && answer && <div className="question-result">
      <p role="status"><strong className={`question-badge ${answer.supported ? 'question-supported' : 'question-unsupported'}`}>
        {answer.supported ? 'Supported by Evidence' : 'Insufficient Evidence'}
      </strong></p>
      <h3>Question</h3><p className="question-text">{answer.question}</p>
      <h3>Answer</h3><p className="question-text">{answer.answer}</p>
      <h3>Citations</h3>
      {answer.supported ? <ol className="question-citations">{answer.citations.map((citation, index) => <li key={index}>
        <p className="question-text">{citation.claim}</p>
        <p className="question-text">Source locator: {citation.source_locator}</p>
        {citation.observation_id && <p className="identifier">Observation: {citation.observation_id}</p>}
        <button type="button" aria-label={`Inspect source evidence ${citation.evidence_id}`}
          onClick={() => inspectEvidence(citation.evidence_id)}>Inspect source evidence {citation.evidence_id}</button>
      </li>)}</ol> : <p>No factual claims or citations were made. The available evidence is insufficient to answer this question.</p>}
      <p className="identifier">Retrieval version: {answer.retrieval_version}</p>
      {answer.provenance_id && <p className="identifier">Provenance: {answer.provenance_id}</p>}
      {answer.model_version && <p className="identifier">Model: {answer.model_version}</p>}
    </div>}
  </section>;
}
