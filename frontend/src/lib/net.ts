/** Pick the host uplink and turn two counter samples into bytes per second. */

const VIRTUAL_PREFIXES = [
  "docker",
  "br-",
  "veth",
  "virbr",
  "cni",
  "flannel",
  "cali",
  "dummy",
  "tun",
  "tap",
  "ifb",
];

export type CounterPoint = { ts: number; value: number };

export function uplinkInterface(series: string[], route: string): string {
  const seen = new Map<string, { rx: boolean; tx: boolean }>();
  const order: string[] = [];
  for (const name of series) {
    const rx = /^host\.net\.(.+)\.rx_bytes$/.exec(name);
    const tx = /^host\.net\.(.+)\.tx_bytes$/.exec(name);
    const iface = rx?.[1] ?? tx?.[1];
    if (!iface) continue;
    const row = seen.get(iface) ?? { rx: false, tx: false };
    if (!seen.has(iface)) order.push(iface);
    if (rx) row.rx = true;
    if (tx) row.tx = true;
    seen.set(iface, row);
  }
  const fromRoute = /\bdev\s+(\S+)/.exec(route)?.[1] ?? "";
  const routed = seen.get(fromRoute);
  if (fromRoute && routed?.rx && routed.tx) return fromRoute;
  for (const iface of order) {
    const row = seen.get(iface);
    if (!row?.rx || !row.tx) continue;
    if (VIRTUAL_PREFIXES.some((prefix) => iface.startsWith(prefix))) continue;
    return iface;
  }
  return "";
}

export function byteRate(points: CounterPoint[]): number | null {
  if (points.length < 2) return null;
  const last = points[points.length - 1];
  const previous = points[points.length - 2];
  if (!last || !previous) return null;
  const elapsed = last.ts - previous.ts;
  if (elapsed <= 0) return null;
  return Math.max(0, (last.value - previous.value) / elapsed);
}
