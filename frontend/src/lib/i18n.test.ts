import { describe, expect, it } from "vitest";
import { copy, copyKeys, routeFromHash, routes } from "./i18n";

describe("panel copy", () => {
  it("keeps English and Russian dictionaries in lockstep", () => {
    for (const key of copyKeys) {
      expect(copy("en", key).length, key).toBeGreaterThan(0);
      expect(copy("ru", key).length, key).toBeGreaterThan(0);
    }
  });

  it("falls back to the overview for an unknown hash", () => {
    expect(routeFromHash("")).toBe("overview");
    expect(routeFromHash("#/projects")).toBe("apps");
    expect(routeFromHash("#/users")).toBe("access");
    expect(routeFromHash("#/audit")).toBe("events");
    expect(routeFromHash("#/missing")).toBe("overview");
    expect(routes).toContain("settings");
  });
});
