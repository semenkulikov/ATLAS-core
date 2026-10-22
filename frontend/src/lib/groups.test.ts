import { describe, expect, it } from "vitest";
import { serviceGroup } from "./groups";

describe("system unit groups", () => {
  it("sorts well-known units and leaves an application name in the rest", () => {
    expect(serviceGroup("ssh.service")).toBe("groupNetwork");
    expect(serviceGroup("apt-daily.service")).toBe("groupPackages");
    expect(serviceGroup("ledger.service")).toBe("groupOther");
  });

  it("keeps the panel units together and a user instance with sessions", () => {
    expect(serviceGroup("atlas-scan.service")).toBe("groupPanel");
    expect(serviceGroup("atlas.service")).toBe("groupPanel");
    expect(serviceGroup("user@1000.service")).toBe("groupSessions");
  });
});
