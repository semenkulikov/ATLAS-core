/** Group project directories into applications. Names of real projects are not special-cased. */

import type { Entity } from "./api";
import { exposureOf, textOf } from "./format";
import { copy, type Lang } from "./i18n";

const ENV_SUFFIX = /-(main|staging|dev|prod|test|production|stage)$/i;

export type AppDir = {
  id: string;
  name: string;
  path: string;
  env: string | null;
  stack: string[];
  anchor: string;
};

export type AppStatus = "running" | "partial" | "down" | "unknown";

export type AppModel = {
  id: string;
  name: string;
  dirs: AppDir[];
  envs: string[];
  stack: string[];
  reason: "prefix" | "single";
  manual: boolean;
  services: Entity[];
  containers: Entity[];
  ports: Entity[];
  schedules: Entity[];
  status: AppStatus;
};

export type ManualMap = { renames: Record<string, string>; alone: string[] };

export type SystemBag = {
  services: Entity[];
  containers: Entity[];
  ports: Entity[];
  schedules: Entity[];
};

const emptyManual = (): ManualMap => ({ renames: {}, alone: [] });

function stackOf(payload: Record<string, unknown>): string[] {
  const raw = payload.stack;
  if (!Array.isArray(raw)) return [];
  const names = raw.map((item) => textOf(item)).filter(Boolean);
  return [...new Set(names)];
}

function splitName(name: string): { base: string; env: string | null } {
  const match = ENV_SUFFIX.exec(name);
  if (!match) return { base: name, env: null };
  return { base: name.slice(0, -match[0].length), env: match[1].toLowerCase() };
}

function slug(value: string): string {
  const clean = value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return clean || "app";
}

function statusOf(services: Entity[], containers: Entity[]): AppStatus {
  const flags: boolean[] = [];
  for (const row of services) {
    const active = textOf(row.payload["unit.active"] ?? row.payload.active);
    if (active === "active" || active === "activating") flags.push(true);
    else if (active === "failed" || active === "inactive") flags.push(false);
  }
  for (const row of containers) {
    const state = textOf(row.payload.state).toLowerCase();
    if (state === "running") flags.push(true);
    else if (state) flags.push(false);
  }
  if (flags.length === 0) return "unknown";
  const up = flags.filter(Boolean).length;
  if (up === flags.length) return "running";
  if (up === 0) return "down";
  return "partial";
}

export function groupProjects(items: Entity[], manual: ManualMap = emptyManual()): AppModel[] {
  const buckets = new Map<string, AppDir[]>();
  for (const item of items) {
    const name = textOf(item.payload.name) || item.key;
    const path = textOf(item.payload.root_path);
    const alone = manual.alone.includes(item.key);
    const split = alone ? { base: `${name}#${item.key}`, env: null as string | null } : splitName(name);
    const dir: AppDir = {
      id: item.key,
      name,
      path,
      env: split.env,
      stack: stackOf(item.payload),
      anchor: textOf(item.payload.anchor_kind),
    };
    const list = buckets.get(split.base) ?? [];
    list.push(dir);
    buckets.set(split.base, list);
  }
  const apps: AppModel[] = [];
  for (const [base, dirs] of buckets) {
    const hasEnv = dirs.some((dir) => dir.env);
    const reason = dirs.length > 1 || hasEnv ? "prefix" : "single";
    const id = slug(base.split("#")[0] || base);
    const uniqueId = apps.some((app) => app.id === id) ? `${id}-${dirs[0]?.id.slice(0, 4)}` : id;
    const stack = [...new Set(dirs.flatMap((dir) => dir.stack))].slice(0, 12);
    const envs = [...new Set(dirs.map((dir) => dir.env).filter((env): env is string => Boolean(env)))];
    const renamed = manual.renames[uniqueId];
    apps.push({
      id: uniqueId,
      name: renamed || base.split("#")[0] || base,
      dirs,
      envs,
      stack,
      reason,
      manual: Boolean(renamed) || dirs.some((dir) => manual.alone.includes(dir.id)),
      services: [],
      containers: [],
      ports: [],
      schedules: [],
      status: "unknown",
    });
  }
  return apps.sort((a, b) => a.name.localeCompare(b.name));
}

function roots(app: AppModel): string[] {
  return app.dirs.map((dir) => dir.path).filter(Boolean);
}

function matchesPath(path: string, app: AppModel): boolean {
  return roots(app).some((root) => path === root || path.startsWith(`${root}/`));
}

function bestApp(apps: AppModel[], hints: string[]): AppModel | null {
  let winner: { app: AppModel; length: number } | null = null;
  for (const hint of hints) {
    if (!hint) continue;
    for (const app of apps) {
      for (const root of roots(app)) {
        const hit = hint === root || hint.startsWith(`${root}/`) || hint.includes(`/${app.name}`);
        if (!hit) continue;
        if (!winner || root.length > winner.length) winner = { app, length: root.length };
      }
      const base = app.dirs.some((dir) => hint === dir.name || hint.startsWith(`${dir.name}-`) || hint.startsWith(`${dir.name}_`));
      if (base && !winner) winner = { app, length: 1 };
    }
  }
  return winner?.app ?? null;
}

function containerHints(row: Entity): string[] {
  const hints: string[] = [textOf(row.payload.name)];
  const labels = row.payload.labels;
  if (labels && typeof labels === "object") {
    const record = labels as Record<string, unknown>;
    hints.push(textOf(record["com.docker.compose.project.working_dir"]));
    hints.push(textOf(record["com.docker.compose.project"]));
  }
  const binds = row.payload.binds;
  if (Array.isArray(binds)) {
    for (const bind of binds) hints.push(textOf(bind).split(":")[0] ?? "");
  }
  const mounts = row.payload.mounts;
  if (Array.isArray(mounts)) {
    for (const mount of mounts) {
      if (mount && typeof mount === "object") {
        const record = mount as Record<string, unknown>;
        hints.push(textOf(record.Source ?? record.source));
      }
    }
  }
  return hints.filter(Boolean);
}

export function linkInventory(
  apps: AppModel[],
  bag: { services: Entity[]; containers: Entity[]; ports: Entity[]; schedules: Entity[] },
): { apps: AppModel[]; system: SystemBag } {
  const system: SystemBag = { services: [], containers: [], ports: [], schedules: [] };
  const fresh = apps.map((app) => ({ ...app, services: [] as Entity[], containers: [] as Entity[], ports: [] as Entity[], schedules: [] as Entity[] }));
  const take = (row: Entity, hints: string[], key: keyof SystemBag) => {
    const app = bestApp(fresh, hints);
    if (!app) {
      system[key].push(row);
      return;
    }
    app[key].push(row);
  };
  for (const row of bag.services) {
    take(row, [textOf(row.payload.working_directory), textOf(row.payload.description), row.key], "services");
  }
  for (const row of bag.containers) take(row, containerHints(row), "containers");
  for (const row of bag.schedules) {
    take(row, [textOf(row.payload.command), textOf(row.payload.path)], "schedules");
  }
  for (const row of bag.ports) {
    const process = row.payload.process;
    const cmdline = process && typeof process === "object" ? textOf((process as Record<string, unknown>).cmdline) : "";
    const comm = process && typeof process === "object" ? textOf((process as Record<string, unknown>).comm) : "";
    const owner = fresh.find((app) => app.containers.some((item) => textOf(item.payload.name) === comm));
    if (owner) owner.ports.push(row);
    else take(row, [cmdline, comm], "ports");
  }
  for (const app of fresh) app.status = statusOf(app.services, app.containers);
  return { apps: fresh, system };
}

export function isSystemUser(row: Entity): boolean {
  const shell = textOf(row.payload.shell);
  const uid = Number(row.payload.uid);
  const home = textOf(row.payload.home);
  if (["/usr/sbin/nologin", "/sbin/nologin", "/bin/false", "/usr/bin/false", "/bin/sync"].includes(shell)) {
    return true;
  }
  if (Number.isFinite(uid) && uid > 0 && uid < 1000 && !home.startsWith("/home/")) return true;
  return false;
}

export function statusTone(status: AppStatus): "ok" | "warn" | "bad" | "unknown" {
  if (status === "running") return "ok";
  if (status === "partial") return "warn";
  if (status === "down") return "bad";
  return "unknown";
}

export function statusLabel(status: AppStatus, lang: Lang): string {
  if (status === "running") return copy(lang, "running");
  if (status === "partial") return copy(lang, "partial");
  if (status === "down") return copy(lang, "down");
  return copy(lang, "unknownStatus");
}

export function portList(ports: Entity[]): number[] {
  const numbers = ports
    .map((row) => Number(row.payload.port))
    .filter((port) => Number.isFinite(port));
  return [...new Set(numbers)].sort((a, b) => a - b);
}

export function hasPublicPort(ports: Entity[]): boolean {
  return ports.some((row) => exposureOf(textOf(row.payload.address)) === "external");
}

export function matchesPathExport(path: string, app: AppModel): boolean {
  return matchesPath(path, app);
}

export type Hop = { label: string; kind: "domain" | "port" | "container" | "dir" };

export function requestChains(app: AppModel, sites: Entity[]): Hop[][] {
  const chains: Hop[][] = [];
  for (const site of sites) {
    const names = Array.isArray(site.payload.names) ? site.payload.names.map((item) => textOf(item)).filter(Boolean) : [];
    const roots = Array.isArray(site.payload.roots) ? site.payload.roots.map((item) => textOf(item)) : [];
    const proxies = Array.isArray(site.payload.proxies) ? site.payload.proxies.map((item) => textOf(item)) : [];
    const linked = roots.some((root) => matchesPath(root, app)) || proxies.some((proxy) => app.ports.some((port) => proxy.includes(String(port.payload.port))));
    if (!linked) continue;
    const dir = app.dirs.find((item) => roots.some((root) => root.startsWith(item.path))) ?? app.dirs[0];
    const port = app.ports[0];
    const container = app.containers[0];
    const hops: Hop[] = [];
    if (names[0]) hops.push({ kind: "domain", label: names[0] });
    if (port) hops.push({ kind: "port", label: String(port.payload.port) });
    if (container) hops.push({ kind: "container", label: textOf(container.payload.name) });
    if (dir) hops.push({ kind: "dir", label: dir.path });
    if (hops.length > 1) chains.push(hops);
  }
  if (chains.length === 0 && app.ports.length > 0 && app.dirs[0]) {
    const port = app.ports[0];
    const hops: Hop[] = [{ kind: "port", label: String(port.payload.port) }];
    if (app.containers[0]) hops.push({ kind: "container", label: textOf(app.containers[0].payload.name) });
    hops.push({ kind: "dir", label: app.dirs[0].path });
    chains.push(hops);
  }
  return chains.slice(0, 4);
}
