import { describe, expect, it } from "vitest";
import { changedFields, eventTitle } from "./events";

describe("event titles", () => {
  it("takes the name from JSON and leaves the id off the title", () => {
    const titled = eventTitle("ru", {
      entity_kind: "container",
      entity_key: "a".repeat(64),
      change_kind: "added",
      before_json: null,
      after_json: JSON.stringify({ name: "ledger", id: "a".repeat(64) }),
    });
    expect(titled.title).toBe("Появился контейнер ledger");
    expect(titled.idLine).toBe("");
  });

  it("reads the name from the object the API returns", () => {
    const titled = eventTitle("ru", {
      entity_kind: "container",
      entity_key: "b".repeat(64),
      change_kind: "modified",
      after: { name: "ledger", id: "b".repeat(64), state: "running" },
      before: { name: "ledger", id: "b".repeat(64), state: "exited" },
    });
    expect(titled.title).toBe("Изменился контейнер ledger");
    expect(titled.idLine).toBe("");
    expect(changedFields({
      entity_kind: "container",
      entity_key: "b".repeat(64),
      change_kind: "modified",
      after: { name: "ledger", state: "running" },
      before: { name: "ledger", state: "exited" },
    })).toEqual([{ key: "state", before: "exited", after: "running" }]);
  });

  it("keeps the id on a second line when the payload has no name", () => {
    const titled = eventTitle("ru", {
      entity_kind: "service",
      entity_key: "ledger.service",
      change_kind: "modified",
      before_json: JSON.stringify({ "unit.active": "active" }),
      after_json: JSON.stringify({ "unit.active": "failed" }),
    });
    expect(titled.title).toBe("Изменилась служба");
    expect(titled.idLine).toBe("ledger.service");
    expect(changedFields({
      entity_kind: "service",
      entity_key: "ledger.service",
      change_kind: "modified",
      before_json: JSON.stringify({ "unit.active": "active", id: "secret" }),
      after_json: JSON.stringify({ "unit.active": "failed", id: "other" }),
    })).toEqual([{ key: "unit.active", before: "active", after: "failed" }]);
  });
});
