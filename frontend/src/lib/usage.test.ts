import { describe, expect, it } from "vitest";
import { appUsage } from "./usage";

describe("application resource totals", () => {
  const app = {
    services: [{ key: "ledger.service" }],
    containers: [{ payload: { name: "ledger-web", id: "abcdef1234567890" } }],
  };

  it("sums only the units that belong to the application", () => {
    const totals = appUsage(
      app,
      [
        { name: "ledger", memory_bytes: 100, kind: "service" },
        { name: "other", memory_bytes: 9000, kind: "service" },
        { name: "abcdef123456", memory_bytes: 50, kind: "container" },
      ],
      { "service:ledger": 4, "container:abcdef123456": 1.5 },
    );
    expect(totals).toEqual({ memory: 150, cpu: 5.5 });
  });

  it("stays empty when the latest sample has none of the application", () => {
    expect(appUsage(app, [{ name: "other", memory_bytes: 1, kind: "service" }], {})).toEqual({
      memory: null,
      cpu: null,
    });
  });
});
