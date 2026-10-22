/** Compare an external listener with a parsed firewall snapshot. */

import type { Entity } from "./api";

export type FirewallView = {
  policy: "accept" | "drop" | "unknown";
  ports: { protocol: string; port: number }[];
};

const toolOrder = ["nft ", "iptables", "ufw ", "firewall-cmd"];

export function chooseFirewall(entities: Entity[]): FirewallView | null {
  const ranked = [...entities].sort((left, right) => rank(left.key) - rank(right.key));
  for (const row of ranked) {
    const policy = textPolicy(row.payload.policy);
    const ports = portList(row.payload.ports);
    if (policy === "drop" && ports.length === 0) continue;
    if (policy === "accept" || policy === "drop") return { policy, ports };
  }
  return null;
}

export function portFirewall(
  exposure: string,
  protocol: string,
  port: number,
  policy: FirewallView | null,
): "allowed" | "missing" | "unknown" {
  if (exposure !== "external" || !policy) return "unknown";
  if (policy.policy === "accept") return "allowed";
  const hit = policy.ports.some((item) => item.protocol === protocol && item.port === port);
  return hit ? "allowed" : "missing";
}

function rank(key: string): number {
  const index = toolOrder.findIndex((prefix) => key.startsWith(prefix.trim()) || key.includes(prefix.trim()));
  return index === -1 ? toolOrder.length : index;
}

function textPolicy(value: unknown): FirewallView["policy"] {
  if (value === "accept" || value === "drop") return value;
  return "unknown";
}

function portList(value: unknown): FirewallView["ports"] {
  if (!Array.isArray(value)) return [];
  const ports: FirewallView["ports"] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const protocol = (item as { protocol?: unknown }).protocol;
    const port = (item as { port?: unknown }).port;
    if ((protocol === "tcp" || protocol === "udp") && typeof port === "number") {
      ports.push({ protocol, port });
    }
  }
  return ports;
}
