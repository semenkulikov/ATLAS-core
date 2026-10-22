/** Sum the live readings that belong to one application. */

import { textOf } from "./format";

export type UsageRow = {
  name: string;
  memory_bytes: number | null;
  kind: "service" | "container";
};

type UsageApp = {
  services: { key: string }[];
  containers: { payload: Record<string, unknown> }[];
};

export function appUsage(
  app: UsageApp,
  rows: UsageRow[],
  shares: Record<string, number>,
): { memory: number | null; cpu: number | null } {
  const matched = rows.filter((row) => belongs(row, app));
  if (matched.length === 0) return { memory: null, cpu: null };
  let memory = 0;
  let sawMemory = false;
  let cpu = 0;
  let sawCpu = false;
  for (const row of matched) {
    if (row.memory_bytes !== null) {
      memory += row.memory_bytes;
      sawMemory = true;
    }
    const share = shares[`${row.kind}:${row.name}`];
    if (share !== undefined) {
      cpu += share;
      sawCpu = true;
    }
  }
  return { memory: sawMemory ? memory : null, cpu: sawCpu ? cpu : null };
}

function belongs(row: UsageRow, app: UsageApp): boolean {
  if (row.kind === "service") {
    return app.services.some((item) => item.key === row.name || item.key === `${row.name}.service`);
  }
  return app.containers.some((item) => {
    const name = textOf(item.payload.name);
    const id = textOf(item.payload.id);
    return name === row.name || (id !== "" && id.startsWith(row.name));
  });
}
