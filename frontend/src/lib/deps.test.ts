import { describe, expect, it } from "vitest";
import { dependencyParts } from "./deps";

describe("dependency labels", () => {
  it("uses the predicate as the package name", () => {
    expect(dependencyParts("dependency.aiogram", "3.13.1")).toEqual({
      name: "aiogram",
      unpinned: false,
      detail: "3.13.1",
    });
    expect(dependencyParts("dependency.flask", "dependency is not pinned").unpinned).toBe(true);
    expect(dependencyParts("dependency.flask", "dependency is not pinned").name).toBe("flask");
  });
});
