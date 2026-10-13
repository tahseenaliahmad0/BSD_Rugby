/** Small fetch wrapper: same-origin cookies, JSON bodies, CSRF header, typed errors. */

export const CSRF_COOKIE = 'rugby_csrf';
export const CSRF_HEADER = 'X-CSRF-Token';

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  /** The parsed JSON body, when the server sent one (a 409 carries the current tag). */
  readonly body: unknown;
  /** Set by callers that know which tag a failed request was about. */
  conflictTagId?: string;

  constructor(status: number, detail: string, body?: unknown) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.body = body;
  }
}

export function readCookie(name: string): string {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) return decodeURIComponent(trimmed.slice(prefix.length));
  }
  return '';
}

export function csrfToken(): string {
  return readCookie(CSRF_COOKIE);
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
}

async function detailFrom(response: Response): Promise<[string, unknown]> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === 'string') return [data.detail, data];
    if (Array.isArray(data.detail)) {
      // FastAPI validation errors: make them readable.
      return [
        data.detail
          .map((d: { loc?: unknown[]; msg?: string }) => {
            const field = Array.isArray(d.loc) ? d.loc.slice(1).join('.') : '';
            const msg = (d.msg ?? 'invalid').replace(/^Value error, /, '');
            return field ? `${field}: ${msg}` : msg;
          })
          .join('; '),
        data,
      ];
    }
  } catch {
    /* fall through */
  }
  return [response.statusText || `Request failed (${response.status})`, undefined];
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') headers[CSRF_HEADER] = csrfToken();
  const response = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  if (!response.ok) {
    const [detail, body] = await detailFrom(response);
    throw new ApiError(response.status, detail, body);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function queryString(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : '';
}
