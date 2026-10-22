/** One read of the latest scan, shaped for the application-first screens. */

import { writable } from "svelte/store";
import { groupProjects, linkInventory, type AppModel, type ManualMap, type SystemBag } from "./apps";
import { api, loadAll, type Entity } from "./api";
import { textOf } from "./format";

export const refreshedAt = writable<number | null>(null);

export type PanelData = {
  hostname: string;
  os: string;
  kernel: string;
  arch: string;
  virt: string;
  uptimeRaw: string;
  timezone: string;
  cpuCount: number | null;
  memTotal: number | null;
  memAvail: number | null;
  diskTotal: number | null;
  diskFree: number | null;
  ip: string;
  sshd: Record<string, string>;
  sessions: string;
  firewall: Entity[];
  sites: Entity[];
  sourceCount: number;
  collectedAt: string | null;
  apps: AppModel[];
  system: SystemBag;
  users: Entity[];
  keys: Entity[];
};

const MANUAL_KEY = "atlas.manual";

export function readManual(): ManualMap {
  try {
    const raw = localStorage.getItem(MANUAL_KEY);
    if (!raw) return { renames: {}, alone: [] };
    const parsed = JSON.parse(raw) as ManualMap;
    return {
      renames: parsed.renames && typeof parsed.renames === "object" ? parsed.renames : {},
      alone: Array.isArray(parsed.alone) ? parsed.alone.map(String) : [],
    };
  } catch {
    return { renames: {}, alone: [] };
  }
}

export function writeManual(manual: ManualMap): void {
  localStorage.setItem(MANUAL_KEY, JSON.stringify(manual));
}

function payloadOf(rows: Entity[] | undefined): Record<string, unknown> {
  return rows?.[0]?.payload ?? {};
}

function numberOrNull(value: unknown): number | null {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function primaryAddress(network: Record<string, unknown>): string {
  const interfaces = network.interfaces;
  if (!Array.isArray(interfaces)) return "";
  for (const row of interfaces) {
    if (!row || typeof row !== "object") continue;
    const addresses = (row as { addresses?: unknown }).addresses;
    if (!Array.isArray(addresses)) continue;
    for (const address of addresses) {
      const text = textOf(address).split("/")[0] ?? "";
      if (text && !text.startsWith("127.") && text !== "::1") return text;
    }
  }
  return "";
}

type HostBody = {
  collected_at: string | null;
  entities: Entity[];
  sources: unknown[];
  passport?: Record<string, Entity[]>;
};

export async function loadPanel(): Promise<PanelData> {
  const [host, projects, services, containers, ports, schedules, users, keys] = await Promise.all([
    api<HostBody>("/api/v1/host"),
    loadAll("/api/v1/projects"),
    loadAll("/api/v1/services"),
    loadAll("/api/v1/containers"),
    loadAll("/api/v1/ports"),
    loadAll("/api/v1/schedules"),
    loadAll("/api/v1/users"),
    loadAll("/api/v1/ssh-keys"),
  ]);
  const identity = host.entities.find((row) => row.key === "host")?.payload ?? {};
  const resources = payloadOf(host.passport?.resources);
  const network = payloadOf(host.passport?.network);
  const sshdRaw = payloadOf(host.passport?.sshd);
  const sshd: Record<string, string> = {};
  for (const [key, value] of Object.entries(sshdRaw)) sshd[key] = textOf(value);
  const filesystems = resources.filesystems;
  let diskTotal: number | null = null;
  let diskFree: number | null = null;
  if (Array.isArray(filesystems)) {
    const rows = filesystems.filter((row) => row && typeof row === "object") as Record<string, unknown>[];
    const root = rows.find((row) => row.mountpoint === "/") ?? rows[0];
    if (root) {
      diskTotal = numberOrNull(root.total_bytes);
      diskFree = numberOrNull(root.available_bytes);
    }
  }
  const sites = host.passport?.site ?? [];
  const linked = linkInventory(groupProjects(projects, readManual()), { services, containers, ports, schedules }, sites);
  refreshedAt.set(Date.now());
  return {
    hostname: textOf(identity.hostname),
    os: textOf(identity["os.pretty_name"]),
    kernel: textOf(identity["kernel.release"]),
    arch: textOf(identity.arch),
    virt: textOf(identity.virt),
    uptimeRaw: textOf(identity.uptime_seconds),
    timezone: textOf(identity.timezone),
    cpuCount: numberOrNull(resources.cpu_count),
    memTotal: numberOrNull(resources["memory.total_bytes"]),
    memAvail: numberOrNull(resources["memory.available_bytes"]),
    diskTotal,
    diskFree,
    ip: primaryAddress(network),
    sshd,
    sessions: textOf(payloadOf(host.passport?.sessions).text),
    firewall: host.passport?.firewall ?? [],
    sites,
    sourceCount: host.sources.length,
    collectedAt: host.collected_at,
    apps: linked.apps,
    system: linked.system,
    users,
    keys,
  };
}
