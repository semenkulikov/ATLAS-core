/** Shared shapes returned by the inventory API. */

export type Entity = {
  kind: string;
  key: string;
  payload: Record<string, unknown>;
};

export type Fact = {
  id: number;
  subject: string;
  predicate: string;
  value: string;
  certainty: "fact" | "derived" | "unknown" | string;
  rule: string | null;
  collected_at: string;
};

export type Evidence = {
  id: number;
  kind: string;
  ref: string;
  excerpt: string;
  file_sha256: string | null;
  collected_at: string;
};

export type Account = {
  username: string;
  role: string;
  via?: string;
};

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function csrfToken(): string {
  const row = document.cookie.split("; ").find((part) => part.startsWith("atlas_csrf="));
  return row ? decodeURIComponent(row.slice("atlas_csrf=".length)) : "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    headers.set("content-type", "application/json");
    const token = csrfToken();
    if (token) headers.set("x-csrf-token", token);
  }
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (response.status === 304) return undefined as T;
  const text = await response.text();
  const payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  if (!response.ok) {
    throw new ApiError(
      response.status,
      String(payload.code ?? "http.error"),
      String(payload.detail ?? payload.title ?? response.statusText),
    );
  }
  return payload as T;
}
