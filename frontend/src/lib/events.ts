/** Human titles for inventory changes. The name comes from JSON, never from the key. */

import type { Entity } from "./api";
import type { Lang } from "./i18n";

export type ChangeRow = {
  entity_kind: string;
  entity_key: string;
  change_kind: string;
  before_json: string | null;
  after_json: string | null;
};

export type FieldChange = { key: string; before: string; after: string };

const sentences: Record<Lang, Record<string, Record<string, string>>> = {
  ru: {
    container: { added: "Появился контейнер", modified: "Изменился контейнер", removed: "Удалён контейнер" },
    service: { added: "Появилась служба", modified: "Изменилась служба", removed: "Удалена служба" },
    port: { added: "Появился порт", modified: "Изменился порт", removed: "Удалён порт" },
  },
  en: {
    container: { added: "Container appeared", modified: "Container changed", removed: "Container removed" },
    service: { added: "Service appeared", modified: "Service changed", removed: "Service removed" },
    port: { added: "Port appeared", modified: "Port changed", removed: "Port removed" },
  },
};

const fallback: Record<Lang, Record<string, string>> = {
  ru: { added: "Появилось", modified: "Изменилось", removed: "Удалено" },
  en: { added: "Appeared", modified: "Changed", removed: "Removed" },
};

function readObject(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  try {
    const value = JSON.parse(raw) as unknown;
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return value as Record<string, unknown>;
  } catch {
    return {};
  }
}

function objectName(raw: string | null): string {
  const name = readObject(raw).name;
  return typeof name === "string" ? name.trim() : "";
}

function brief(value: unknown): string {
  if (typeof value === "string") return value.length > 80 ? `${value.slice(0, 12)}…` : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

export function eventTitle(lang: Lang, row: ChangeRow): { title: string; idLine: string } {
  const kind = row.change_kind === "changed" ? "modified" : row.change_kind;
  const name = objectName(row.after_json) || objectName(row.before_json);
  const specific = sentences[lang][row.entity_kind]?.[kind];
  const lead = specific ?? fallback[lang][kind] ?? fallback[lang].modified;
  if (!name) return { title: lead, idLine: row.entity_key };
  return { title: `${lead} ${name}`, idLine: "" };
}

export function changedFields(row: ChangeRow): FieldChange[] {
  const before = readObject(row.before_json);
  const after = readObject(row.after_json);
  const skip = new Set(["id", "Id", "name"]);
  const found: FieldChange[] = [];
  for (const key of [...new Set([...Object.keys(before), ...Object.keys(after)])]) {
    if (skip.has(key)) continue;
    const left = brief(before[key]);
    const right = brief(after[key]);
    if (!left && !right) continue;
    if (left === right) continue;
    found.push({ key, before: left, after: right });
    if (found.length === 6) break;
  }
  return found;
}

export function eventMatchesApp(
  row: ChangeRow,
  app: { containers: Entity[]; services: Entity[]; ports: Entity[] },
): boolean {
  const keys = new Set<string>();
  for (const item of [...app.containers, ...app.services, ...app.ports]) {
    keys.add(item.key);
    const id = item.payload.id;
    if (typeof id === "string" && id) keys.add(id);
  }
  return keys.has(row.entity_key);
}
