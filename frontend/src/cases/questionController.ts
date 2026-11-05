import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

type CaseAnswer = components['schemas']['CaseAnswer'];
export type QuestionState = {
  status: 'idle' | 'submitting' | 'ready' | 'error';
  question: string;
  answer: CaseAnswer | null;
  message: string;
  history?: CaseAnswer[];
};
const initial = (): QuestionState => ({ status: 'idle', question: '', answer: null, message: '', history: [] });
const text = (value: unknown): value is string => typeof value === 'string' && !!value.trim();
const uuid = (value: unknown): value is string => typeof value === 'string' &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

function validAnswer(answer: CaseAnswer, caseId: string, question: string): boolean {
  return !!answer && answer.case_id === caseId && answer.question === question &&
    typeof answer.supported === 'boolean' && text(answer.answer) && text(answer.retrieval_version) &&
    Array.isArray(answer.citations) && (answer.supported ? answer.citations.length > 0 : answer.citations.length === 0) &&
    answer.citations.every(citation => !!citation && text(citation.claim) && uuid(citation.evidence_id) &&
      text(citation.source_locator) && (citation.observation_id === undefined || uuid(citation.observation_id)));
}

function questionError(error: unknown): string {
  if ((error instanceof ApiHttpError && error.status === 401) ||
      (error instanceof ApiClientError && error.kind === 'authentication')) {
    return 'Authentication required. Open a session again before retrying.';
  }
  if (error instanceof ApiHttpError && error.status === 400) return 'Question was not accepted. Check your question and retry.';
  if (error instanceof ApiHttpError && error.status === 404) return 'Case unavailable or no longer accessible.';
  return 'Could not answer the question. Retry the request.';
}

/** One case and session; no requests until the investigator submits a question. */
export function createQuestionController(client: ApiClient, caseId: string) {
  let state = initial();
  let enabled = false;
  let session = client.getSessionVersion();
  let pending: AbortController | undefined;
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: QuestionState) => { state = next; listeners.forEach(listener => listener()); };
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() {
      if (enabled) return;
      enabled = true; session = client.getSessionVersion();
      unsubscribe?.();
      unsubscribe = client.subscribeSession(() => {
        enabled = false; pending?.abort(); pending = undefined;
        publish({ ...initial(), status: 'error', message: client.hasToken()
          ? 'Session changed. Select the case again.' : 'Authentication required. Open a session again before retrying.' });
      });
    },
    setQuestion(question: string) {
      if (!enabled || state.status === 'submitting') return;
      publish({ ...initial(), question, history: state.history });
    },
    async submit() {
      if (!enabled || state.status === 'submitting' || session !== client.getSessionVersion()) return;
      const question = state.question.trim();
      if (!question || state.question.length > 2000) {
        publish({ ...state, status: 'error', answer: null, message: 'Enter a non-empty question of up to 2000 characters.' });
        return;
      }
      const request = pending = new AbortController();
      const current = () => enabled && pending === request && !request.signal.aborted && session === client.getSessionVersion();
      publish({ ...state, status: 'submitting', answer: null, message: '' });
      try {
        const answer = await client.request('post', '/api/v1/cases/{caseId}/questions', {
          path: { caseId }, body: { question }, signal: request.signal,
        });
        if (!current()) return;
        if (!validAnswer(answer, caseId, question)) throw Error('Invalid case answer.');
        publish({ ...state, status: 'ready', answer, history: [...(state.history ?? []), answer], message: '' });
      } catch (error) {
        if (!current()) return;
        publish({ ...state, status: 'error', answer: null, message: questionError(error) });
      } finally { if (pending === request) pending = undefined; }
    },
    dispose() {
      enabled = false; pending?.abort(); pending = undefined;
      unsubscribe?.(); unsubscribe = undefined; listeners.clear(); state = initial();
    },
  };
}
