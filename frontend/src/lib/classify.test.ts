import { describe, expect, it } from "vitest";
import type { Entity } from "./api";
import { classifyPort, classifyService, classifyUser } from "./classify";
import { shownError, ApiError } from "./api";
import { metricMeta } from "./i18n";

function user(payload: Record<string, unknown>, key = "deploy"): Entity {
  return { kind: "user", key, payload: { name: key, ...payload } };
}

describe("classifyUser", () => {
  it("keeps login users with uid >= 1000 as working", () => {
    expect(classifyUser(user({ uid: 1000, shell: "/bin/bash", home: "/home/deploy" }))).toBe(
      "working",
    );
  });

  it("hides nologin service accounts as system", () => {
    expect(
      classifyUser(user({ uid: 999, shell: "/usr/sbin/nologin", home: "/var/lib/atlas" }, "atlas")),
    ).toBe("system");
  });

  it("marks root as privileged", () => {
    expect(classifyUser(user({ uid: 0, shell: "/bin/bash", home: "/root" }, "root"))).toBe(
      "privileged",
    );
  });
});

describe("classifyService and ports", () => {
  it("treats systemd internals as system", () => {
    expect(classifyService({ kind: "service", key: "systemd-journald.service", payload: {} })).toBe(
      "system",
    );
    expect(classifyService({ kind: "service", key: "shop.service", payload: {} })).toBe("working");
  });

  it("puts local ports under system", () => {
    expect(classifyPort({ kind: "port", key: "p", payload: { exposed: false } })).toBe("system");
    expect(classifyPort({ kind: "port", key: "p", payload: { exposed: true } })).toBe("working");
  });
});

describe("shownError", () => {
  it("maps codes to Russian without leaking English detail", () => {
    const error = new ApiError(404, "record.missing", "That record is not in the latest scan.");
    expect(shownError(error, "ru")).toContain("скане");
    expect(shownError(error, "ru")).not.toContain("That record");
  });
});

describe("metricMeta", () => {
  it("labels host memory in Russian", () => {
    const meta = metricMeta("ru", "host.memory.available_bytes");
    expect(meta.title).toContain("память");
    expect(meta.group).toBe("host");
  });
});
