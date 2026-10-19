import { describe, expect, it } from "vitest";
import type { Entity } from "./api";
import { groupProjects, linkInventory } from "./apps";

function project(name: string, path: string): Entity {
  return { kind: "project", key: name, payload: { name, root_path: path, stack: ["Python"] } };
}

describe("application grouping", () => {
  it("joins environment suffixes and leaves an unrelated directory alone", () => {
    const apps = groupProjects([
      project("guard-vpn-bot", "/opt/guard-vpn-bot"),
      project("guard-vpn-bot-main", "/opt/guard-vpn-bot-main"),
      project("guard-vpn-bot-staging", "/opt/guard-vpn-bot-staging"),
      project("remnawave", "/opt/remnawave"),
    ]);
    expect(apps.map((app) => app.name).sort()).toEqual(["guard-vpn-bot", "remnawave"]);
    const guard = apps.find((app) => app.name === "guard-vpn-bot");
    expect(guard?.envs.sort()).toEqual(["main", "staging"]);
    expect(guard?.reason).toBe("prefix");
    expect(guard?.dirs).toHaveLength(3);
  });

  it("keeps a directory split by hand out of the automatic group", () => {
    const apps = groupProjects(
      [project("shop", "/opt/shop"), project("shop-staging", "/opt/shop-staging")],
      { renames: {}, alone: ["shop-staging"] },
    );
    expect(apps).toHaveLength(2);
  });

  it("sends unrelated units to the system bag", () => {
    const grouped = groupProjects([project("shop", "/opt/shop")]);
    const linked = linkInventory(grouped, {
      services: [
        { kind: "service", key: "shop.service", payload: { working_directory: "/opt/shop", "unit.active": "active" } },
        { kind: "service", key: "ssh.service", payload: { "unit.active": "active" } },
      ],
      containers: [],
      ports: [],
      schedules: [],
    });
    expect(linked.apps[0]?.services.map((row) => row.key)).toEqual(["shop.service"]);
    expect(linked.apps[0]?.status).toBe("running");
    expect(linked.system.services.map((row) => row.key)).toEqual(["ssh.service"]);
  });
});
