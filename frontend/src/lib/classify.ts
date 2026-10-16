/** Split inventory rows into working vs system for the panel lists. */

import type { Entity } from "./api";

const SYSTEM_SHELLS = new Set([
  "/usr/sbin/nologin",
  "/sbin/nologin",
  "/bin/false",
  "/usr/bin/false",
  "/bin/sync",
  "/sbin/shutdown",
  "/sbin/halt",
]);

const SYSTEM_UNIT_RE =
  /^(systemd-|dbus|getty@|user@|user-|udev|polkit|snapd|apparmor|kmod|modprobe|plymouth|sys-|dev-|proc-|run-|tmp-|var-|-.+\.mount$)/i;

export type Bucket = "working" | "system" | "privileged";

export function isSystemShell(shell: unknown): boolean {
  return typeof shell === "string" && SYSTEM_SHELLS.has(shell);
}

export function classifyUser(item: Entity): Bucket {
  const uid = typeof item.payload.uid === "number" ? item.payload.uid : Number(item.payload.uid);
  const shell = item.payload.shell;
  const home = typeof item.payload.home === "string" ? item.payload.home : "";
  const sudo = item.payload.sudo;
  const hasSudo = Array.isArray(sudo) ? sudo.length > 0 && sudo[0] !== "not listed" : false;
  const homeLooksHuman = home.startsWith("/home/") || home === `/home/${item.key}`;

  if (uid === 0 || item.key === "root") return "privileged";
  if (isSystemShell(shell)) return "system";
  if (
    Number.isFinite(uid) &&
    uid < 1000 &&
    !hasSudo &&
    !homeLooksHuman &&
    (home.startsWith("/var/") || home === "/nonexistent" || home.startsWith("/run/"))
  ) {
    return "system";
  }
  if (Number.isFinite(uid) && uid >= 1000) return "working";
  if (hasSudo || homeLooksHuman) return "working";
  if (Number.isFinite(uid) && uid < 1000) return "system";
  return "working";
}

export function classifyService(item: Entity): Bucket {
  const key = item.key;
  if (key.endsWith(".slice") || key.endsWith(".scope")) return "system";
  if (SYSTEM_UNIT_RE.test(key)) return "system";
  if (key.includes("@") && /^(getty|serial-getty|user|systemd)/.test(key)) return "system";
  return "working";
}

export function classifyPort(item: Entity): Bucket {
  return item.payload.exposed === true ? "working" : "system";
}

export function classifySchedule(item: Entity): Bucket {
  const user = item.payload.user;
  if (typeof user === "string" && user && user !== "root") return "working";
  const key = item.key.toLowerCase();
  if (key.includes("cron.") || key.startsWith("system") || key.includes("timer")) {
    if (typeof user === "string" && user === "root") return "system";
  }
  const path = typeof item.payload.path === "string" ? item.payload.path : "";
  if (path.startsWith("/etc/cron") || path.includes("/systemd/")) return "system";
  return "working";
}

export function classifyEntity(kind: string, item: Entity): Bucket {
  if (kind === "user") return classifyUser(item);
  if (kind === "service") return classifyService(item);
  if (kind === "port") return classifyPort(item);
  if (kind === "schedule") return classifySchedule(item);
  return "working";
}

export function kindFromPath(path: string): string {
  if (path.endsWith("/users")) return "user";
  if (path.endsWith("/services")) return "service";
  if (path.endsWith("/ports")) return "port";
  if (path.endsWith("/schedules")) return "schedule";
  if (path.endsWith("/containers")) return "container";
  return "entity";
}
