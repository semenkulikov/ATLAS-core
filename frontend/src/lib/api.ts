/** Shared shapes returned by the inventory API. */

import { copy, type CopyKey, type Lang } from "./i18n";

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

export async function loadAll(path: string): Promise<Entity[]> {
  const items: Entity[] = [];
  let cursor = "";
  for (let page = 0; page < 30; page += 1) {
    const params = new URLSearchParams({ limit: "200" });
    if (cursor) params.set("cursor", cursor);
    const body = await api<{ items: Entity[]; next: string | null }>(`${path}?${params.toString()}`);
    items.push(...body.items);
    if (!body.next) break;
    cursor = body.next;
  }
  return items;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    headers.set("content-type", "application/json");
    const token = csrfToken();
    if (token) headers.set("x-csrf-token", token);
  }
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "network.error", "network");
  }
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

const CODE_KEYS: Record<string, CopyKey> = {
  "scan.missing": "noScan",
  "auth.rejected": "rejected",
  "auth.forbidden": "forbidden",
  "auth.csrf": "csrf",
  "record.missing": "errRecordMissing",
  "project.missing": "errProjectMissing",
  "control.off": "errControlOff",
  "control.disabled": "errControlOff",
  "action.failed": "errActionFailed",
  "action.confirm": "errActionConfirm",
  "action.denied": "forbidden",
  "scan.failed": "errScanFailed",
  "logs.source": "errLogsSource",
  "metrics.query": "errMetricsQuery",
  "http.limit": "errHttpLimit",
  "network.error": "errNetwork",
  "http.error": "errGeneric",
};

export function shownError(error: unknown, lang: Lang): string {
  if (error instanceof ApiError) {
    const key = CODE_KEYS[error.code];
    if (key) return copy(lang, key);
    if (error.code.startsWith("auth.")) return copy(lang, "forbidden");
    if (error.code.startsWith("action.")) return copy(lang, "errActionFailed");
    if (error.code.startsWith("control.")) return copy(lang, "errControlOff");
    return copy(lang, "errGeneric");
  }
  if (error instanceof TypeError) return copy(lang, "errNetwork");
  return copy(lang, "errGeneric");
}

/** Raw backend detail for optional “Technical details” in the error modal. */
export function errorDetail(error: unknown): string {
  if (error instanceof ApiError && error.message && error.message !== "network") {
    return `${error.code}: ${error.message}`;
  }
  return "";
}
