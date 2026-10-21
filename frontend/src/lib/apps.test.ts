import { describe, expect, it } from "vitest";
import type { Entity } from "./api";
import { groupProjects, isSystemUser, linkInventory } from "./apps";

function project(name: string, path: string): Entity {
  return { kind: "project", key: name, payload: { name, root_path: path, stack: ["Python"] } };
}

describe("accounts", () => {
  it("keeps a login shell out of the system-user pile", () => {
    const postgres: Entity = {
      kind: "account",
      key: "postgres",
      payload: { uid: 110, shell: "/bin/bash", home: "/var/lib/postgresql" },
    };
    const nobody: Entity = {
      kind: "account",
      key: "nobody",
      payload: { uid: 65534, shell: "/usr/sbin/nologin", home: "/nonexistent" },
    };
    expect(isSystemUser(postgres)).toBe(false);
    expect(isSystemUser(nobody)).toBe(true);
  });
});

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

  it("links a service by an ExecStart path when the unit has no working directory", () => {
    const grouped = groupProjects([project("ledger", "/opt/ledger")]);
    const linked = linkInventory(grouped, {
      services: [
        {
          kind: "service",
          key: "queue.service",
          payload: { working_directory: "", exec_start: "/usr/bin/python3 /opt/ledger/app.py" },
        },
      ],
      containers: [],
      ports: [],
      schedules: [],
    });
    expect(linked.apps[0]?.services.map((row) => row.key)).toEqual(["queue.service"]);
  });

  it("links a listener whose port is published by the application's container", () => {
    const grouped = groupProjects([project("ledger", "/opt/ledger")]);
    const linked = linkInventory(grouped, {
      services: [],
      containers: [
        { kind: "container", key: "box", payload: { name: "ledger", ports: [{ PublicPort: 9000 }] } },
      ],
      ports: [
        { kind: "port", key: "tcp:9000", payload: { port: 9000, process: { comm: "docker-proxy" } } },
        { kind: "port", key: "tcp:80", payload: { port: 80, process: { comm: "nginx" } } },
      ],
      schedules: [],
    });
    expect(linked.apps[0]?.ports.map((row) => row.key)).toEqual(["tcp:9000"]);
    expect(linked.system.ports.map((row) => row.key)).toEqual(["tcp:80"]);
  });

  it("links a proxy listener only when the site points at the project", () => {
    const grouped = groupProjects([project("ledger", "/opt/ledger")]);
    const linked = linkInventory(
      grouped,
      {
        services: [],
        containers: [],
        ports: [{ kind: "port", key: "tcp:443", payload: { port: 443, process: { comm: "nginx" } } }],
        schedules: [],
      },
      [{ kind: "site", key: "ledger", payload: { roots: ["/opt/ledger/public"], listens: ["443 ssl"], proxies: [] } }],
    );
    expect(linked.apps[0]?.ports.map((row) => row.key)).toEqual(["tcp:443"]);
  });
});
