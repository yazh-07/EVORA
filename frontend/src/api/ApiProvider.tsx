import { createContext, Fragment, useContext, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import type { ApiClient } from './client';

const ApiContext = createContext<ApiClient | null>(null);

export function ApiProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  const session = useSyncExternalStore(client.subscribeSession, client.getSessionVersion, client.getSessionVersion);
  // Remount case-scoped UI on logout/token replacement/401, discarding prior actor state.
  return <ApiContext.Provider value={client}><Fragment key={session}>{children}</Fragment></ApiContext.Provider>;
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiContext);
  if (!client) throw new Error('API consumers require ApiProvider.');
  return client;
}
