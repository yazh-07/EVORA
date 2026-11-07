import type { ApiClient } from '../api/client';
import { createBulkProcessingController } from './bulkProcessingController';
import type { BulkState } from './bulkProcessingController';

export type ActivityEntry = { caseId: string; title: string; state: BulkState };
/** App/session lifetime, deliberately independent of the selected tab or case. */
export function createActivityStore(client: ApiClient) {
  const batches = new Map<string, { title: string; controller: ReturnType<typeof createBulkProcessingController>; unsubscribe?: () => void }>();
  const listeners = new Set<() => void>();
  let snapshot: ActivityEntry[] = [], started = false;
  function refresh() {
    snapshot = [...batches].filter(([, entry]) => entry.controller.getSnapshot().status !== 'idle')
      .map(([caseId, entry]) => ({ caseId, title: entry.title, state: entry.controller.getSnapshot() }));
    listeners.forEach(listener => listener());
  }
  function attach(entry: { controller: ReturnType<typeof createBulkProcessingController>; unsubscribe?: () => void }) {
    entry.controller.start(); entry.unsubscribe?.(); entry.unsubscribe = entry.controller.subscribe(refresh);
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    getBatch(caseId: string, title = 'Evidence batch') {
      let entry = batches.get(caseId);
      if (!entry) {
        entry = { title, controller: createBulkProcessingController(client, caseId) }; batches.set(caseId, entry);
        if (started) attach(entry);
      }
      return entry.controller;
    },
    start() { started = true; for (const entry of batches.values()) attach(entry); refresh(); },
    stop(caseId: string) { batches.get(caseId)?.controller.stop(); },
    dispose() {
      started = false;
      for (const entry of batches.values()) { entry.unsubscribe?.(); entry.controller.dispose(); }
      snapshot = []; listeners.clear();
    },
  };
}
