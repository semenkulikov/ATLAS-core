/** One metrics socket shared by the screens that show live usage. */

import { writable } from "svelte/store";
import type { UsageRow } from "./usage";

export type LiveRow = UsageRow & { cpu_usage_usec: number | null };

export const liveRows = writable<LiveRow[]>([]);
export const liveCpu = writable<Record<string, number>>({});
export const liveOn = writable(false);

let socket: WebSocket | null = null;
let users = 0;
let lastAt = 0;
const lastCpu = new Map<string, number>();

export function retainLive(): () => void {
  users += 1;
  if (!socket) connect();
  return () => {
    users -= 1;
    if (users > 0) return;
    users = 0;
    socket?.close();
    socket = null;
    liveOn.set(false);
  };
}

function connect(): void {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/api/v1/stream`);
  socket.addEventListener("open", () => {
    liveOn.set(true);
    socket?.send(JSON.stringify({ subscribe: "metrics.live" }));
  });
  socket.addEventListener("close", () => {
    liveOn.set(false);
    if (socket && users > 0) {
      socket = null;
      window.setTimeout(() => {
        if (users > 0 && !socket) connect();
      }, 2000);
    }
  });
  socket.addEventListener("message", (event) => {
    try {
      const body = JSON.parse(String(event.data)) as {
        channel?: string;
        collected_at?: number;
        units?: { name: string; memory_bytes: number | null; cpu_usage_usec: number | null }[];
        containers?: { name: string; memory_bytes: number | null; cpu_usage_usec: number | null }[];
      };
      if (body.channel !== "metrics.live") return;
      const incoming: LiveRow[] = [
        ...(body.units ?? []).map((row) => ({ ...row, kind: "service" as const })),
        ...(body.containers ?? []).map((row) => ({ ...row, kind: "container" as const })),
      ];
      const at = typeof body.collected_at === "number" ? body.collected_at : Date.now() / 1000;
      const shares: Record<string, number> = {};
      const elapsed = at - lastAt;
      if (lastAt > 0 && elapsed > 0) {
        for (const row of incoming) {
          const key = `${row.kind}:${row.name}`;
          const previous = lastCpu.get(key);
          if (previous !== undefined && row.cpu_usage_usec !== null && row.cpu_usage_usec >= previous) {
            shares[key] = ((row.cpu_usage_usec - previous) / 1_000_000 / elapsed) * 100;
          }
        }
      }
      lastAt = at;
      lastCpu.clear();
      for (const row of incoming) {
        if (row.cpu_usage_usec !== null) lastCpu.set(`${row.kind}:${row.name}`, row.cpu_usage_usec);
      }
      liveCpu.set(shares);
      liveRows.set(incoming);
    } catch {
      return;
    }
  });
}
