import { describe, expect, it } from "vitest";
import { copy, routeFromHash, routes, type CopyKey } from "./i18n";

describe("panel copy", () => {
  it("uses the same keys in English and Russian", () => {
    const keys = Object.keys({
      product: "",
      overview: "",
      projects: "",
      services: "",
      schedules: "",
      containers: "",
      network: "",
      users: "",
      monitoring: "",
      logs: "",
      changes: "",
      audit: "",
      settings: "",
      search: "",
      palette: "",
      signIn: "",
      signOut: "",
      username: "",
      password: "",
      code: "",
      enroll: "",
      enrollToken: "",
      continue: "",
      confirm: "",
      language: "",
      empty: "",
      loading: "",
      error: "",
      evidence: "",
      close: "",
      unknown: "",
      readOnly: "",
      noScan: "",
      loadMore: "",
      source: "",
      show: "",
      exposed: "",
      local: "",
      role: "",
      controlOn: "",
      risks: "",
      intact: "",
      broken: "",
      when: "",
      actor: "",
      action: "",
      result: "",
      restart: "",
      typeToConfirm: "",
      saved: "",
      channelsOff: "",
      filter: "",
      pattern: "",
      scanCode: "",
      rejected: "",
      forbidden: "",
      csrf: "",
      follow: "",
      pause: "",
    }) as CopyKey[];
    for (const key of keys) {
      expect(copy("en", key).length).toBeGreaterThan(0);
      expect(copy("ru", key).length).toBeGreaterThan(0);
    }
  });

  it("falls back to the overview for an unknown hash", () => {
    expect(routeFromHash("")).toBe("overview");
    expect(routeFromHash("#/projects")).toBe("projects");
    expect(routeFromHash("#/missing")).toBe("overview");
    expect(routes).toContain("settings");
  });
});
