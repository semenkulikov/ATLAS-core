import { describe, expect, it } from "vitest";
import type { Entity } from "./api";
import { chooseFirewall, portFirewall } from "./firewall";

function row(key: string, policy: string, ports: { protocol: string; port: number }[]): Entity {
  return { kind: "firewall", key, payload: { policy, ports } };
}

describe("firewall marks", () => {
  it("allows every external port when the input policy accepts", () => {
    const policy = chooseFirewall([row("nft list ruleset", "accept", [])]);
    expect(portFirewall("external", "tcp", 22, policy)).toBe("allowed");
    expect(portFirewall("local", "tcp", 22, policy)).toBe("unknown");
  });

  it("marks a drop policy by the named ports", () => {
    const policy = chooseFirewall([
      row("ufw status verbose", "drop", [{ protocol: "tcp", port: 22 }]),
      row("nft list ruleset", "drop", [
        { protocol: "tcp", port: 22 },
        { protocol: "tcp", port: 443 },
      ]),
    ]);
    expect(portFirewall("external", "tcp", 443, policy)).toBe("allowed");
    expect(portFirewall("external", "tcp", 8080, policy)).toBe("missing");
  });

  it("does not call a port closed when the rules could not be read", () => {
    expect(portFirewall("external", "tcp", 22, null)).toBe("unknown");
    expect(chooseFirewall([row("nft list ruleset", "unknown", [])])).toBeNull();
    expect(chooseFirewall([row("nft list ruleset", "drop", [])])).toBeNull();
  });
});
