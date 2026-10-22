import type { components, paths } from './schema';

type Method = 'get' | 'post';
type Route<M extends Method> = {
  [P in keyof paths]: NonNullable<paths[P][M]> extends never ? never : P;
}[keyof paths];
type Operation<M extends Method, P extends Route<M>> = NonNullable<paths[P][M]>;
type ParametersOf<O> = O extends { parameters: infer P } ? P : never;
type Parameter<P, K extends PropertyKey> = K extends keyof P ? P[K] : never;
type Option<K extends PropertyKey, T> = [NonNullable<T>] extends [never]
  ? { [F in K]?: never }
  : undefined extends T ? { [F in K]?: T } : { [F in K]: T };
type ContentOf<R> = R extends { content: infer C } ? C : never;
type SuccessContent<O> = O extends { responses: infer R } ? {
  [S in keyof R]: S extends number ? `${S}` extends `2${string}` ? ContentOf<R[S]> : never : never;
}[keyof R] : never;
type Data<O> = SuccessContent<O> extends { 'application/json': infer J } ? J : Blob;
type Body<O> = O extends { requestBody: { content: infer C } }
  ? C extends { 'application/json': infer J } ? { body: J } : { body: FormData }
  : { body?: never };
type RequestOptions<O> =
  Option<'path', Parameter<ParametersOf<O>, 'path'>> &
  Option<'query', Parameter<ParametersOf<O>, 'query'>> &
  Option<'header', Parameter<ParametersOf<O>, 'header'>> & Body<O> &
  (SuccessContent<O> extends { 'application/octet-stream': unknown }
    ? { responseType: 'blob' } : { responseType?: never }) & { signal?: AbortSignal };

type ClientErrorKind = 'configuration' | 'request' | 'authentication' | 'session' | 'network' | 'protocol';

/** Local transport failure; never contains a token, request body or raw server body. */
export class ApiClientError extends Error {
  constructor(readonly kind: ClientErrorKind, message: string) {
    super(message);
    this.name = 'ApiClientError';
  }
}

export class ApiHttpError extends Error {
  constructor(readonly status: number, readonly apiError?: components['schemas']['ApiError']) {
    super('API request failed.');
    this.name = 'ApiHttpError';
  }
}

export function apiOrigin(value: string): string {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.pathname !== '/' || url.search || url.hash || value !== value.trim() || /[\r\n\t]/.test(value)) {
      throw new Error();
    }
    return url.origin;
  } catch {
    throw new ApiClientError('configuration', 'Configure an HTTP(S) API origin without credentials, path, query or fragment.');
  }
}

type RuntimeOptions = {
  path?: Record<string, string>;
  query?: Record<string, string | number | boolean | undefined>;
  header?: Record<string, string>;
  body?: unknown;
  responseType?: 'blob';
  signal?: AbortSignal;
};

function requestUrl(origin: string, template: string, parameters: RuntimeOptions): URL {
  if (!/^\/api\/v1\/[a-zA-Z0-9/{}-]+$/.test(template)) {
    throw new ApiClientError('request', 'Use a generated API path template.');
  }
  const pathname = template.replace(/\{([^{}]+)\}/g, (_match, key: string) => {
    const value = parameters.path?.[key];
    if (typeof value !== 'string' || !value || value === '.' || value === '..') {
      throw new ApiClientError('request', 'A required API path parameter is invalid.');
    }
    return encodeURIComponent(value);
  });
  const url = new URL(origin + pathname);
  for (const [key, value] of Object.entries(parameters.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  return url;
}

function isApiError(value: unknown): value is components['schemas']['ApiError'] {
  if (typeof value !== 'object' || value === null) return false;
  const fields = value as Record<string, unknown>;
  return Object.keys(fields).length === 2 && typeof fields.code === 'string' && typeof fields.message === 'string';
}

/** One fixed server origin per instance. Tokens and in-flight data stay in memory. */
export function createApiClient(config: { baseUrl: string; fetch?: typeof globalThis.fetch }) {
  const origin = apiOrigin(config.baseUrl);
  const transport = config.fetch ?? globalThis.fetch.bind(globalThis);
  let token: string | null = null;
  let sessionVersion = 0;
  const pending = new Set<AbortController>();
  const listeners = new Set<() => void>();

  function changeToken(next: string | null) {
    if (next === token) return;
    token = next;
    sessionVersion += 1;
    for (const controller of pending) controller.abort();
    for (const listener of listeners) listener();
  }

  return {
    setToken(value: string) {
      if (typeof value !== 'string' || !/^[a-zA-Z0-9\-._~+/]+=*$/.test(value)) {
        throw new ApiClientError('authentication', 'A valid bearer token is required.');
      }
      changeToken(value);
    },
    clearToken() { changeToken(null); },
    hasToken: () => token !== null,
    getSessionVersion: () => sessionVersion,
    subscribeSession(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    async request<M extends Method, P extends Route<NoInfer<M>>>(
      method: M, path: P, options: RequestOptions<Operation<M, P>>,
    ): Promise<Data<Operation<M, P>>> {
      if (token === null) throw new ApiClientError('authentication', 'Authentication is required before an API request.');
      const parameters = options as RuntimeOptions;
      const url = requestUrl(origin, path, parameters);
      const headers = new Headers({ Authorization: `Bearer ${token}` });
      for (const [key, value] of Object.entries(parameters.header ?? {})) {
        if (key !== 'Idempotency-Key') throw new ApiClientError('request', 'Use only generated request headers.');
        try { headers.set(key, value); }
        catch { throw new ApiClientError('request', 'An API request header is invalid.'); }
      }
      const binary = parameters.responseType === 'blob';
      headers.set('Accept', binary ? 'application/octet-stream' : 'application/json');
      let body: BodyInit | undefined;
      if (parameters.body !== undefined) {
        if (method !== 'post') throw new ApiClientError('request', 'This API read does not accept a body.');
        if (parameters.body instanceof FormData) body = parameters.body;
        else {
          headers.set('Content-Type', 'application/json');
          try { body = JSON.stringify(parameters.body); }
          catch { throw new ApiClientError('request', 'The API request body cannot be serialized as JSON.'); }
        }
      }
      const version = sessionVersion;
      const controller = new AbortController();
      const signal = parameters.signal ? AbortSignal.any([controller.signal, parameters.signal]) : controller.signal;
      const checkSession = () => {
        if (version !== sessionVersion) throw new ApiClientError('session', 'The API session changed; discard this response.');
      };
      pending.add(controller);
      try {
        signal.throwIfAborted();
        const response = await transport(url, {
          method: method.toUpperCase(), headers, body, signal,
          credentials: 'omit', cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
        });
        checkSession();
        signal.throwIfAborted();
        if (response.status === 401) {
          changeToken(null);
          throw new ApiHttpError(401, { code: 'UNAUTHORIZED', message: 'Authentication required.' });
        }
        if (response.status === 404) {
          throw new ApiHttpError(404, { code: 'NOT_FOUND', message: 'Resource not found.' });
        }
        if (response.redirected || response.type === 'opaqueredirect') {
          throw new ApiClientError('protocol', 'API redirects are not accepted.');
        }
        if (!response.ok) {
          let error: unknown;
          if (response.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase() === 'application/json') {
            try { error = await response.json(); } catch { /* Never expose raw error bodies. */ }
          }
          checkSession();
          signal.throwIfAborted();
          throw new ApiHttpError(response.status, isApiError(error) ? { code: error.code, message: error.message } : undefined);
        }
        let data: unknown;
        if (binary) {
          if (response.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase() !== 'application/octet-stream') {
            throw new ApiClientError('protocol', 'The API did not return original bytes.');
          }
          data = await response.blob();
        }
        else {
          if (response.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase() !== 'application/json') {
            throw new ApiClientError('protocol', 'The API did not return JSON.');
          }
          try { data = await response.json(); }
          catch {
            checkSession();
            signal.throwIfAborted();
            throw new ApiClientError('protocol', 'The API returned invalid JSON.');
          }
        }
        checkSession();
        signal.throwIfAborted();
        return data as Data<Operation<M, P>>;
      } catch (error) {
        if (error instanceof ApiClientError || error instanceof ApiHttpError) throw error;
        if (signal.aborted) throw new DOMException('API request cancelled.', 'AbortError');
        throw new ApiClientError('network', 'The API request could not be completed.');
      } finally {
        pending.delete(controller);
      }
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
