<script lang="ts">
  import { onMount } from "svelte";
  import uPlot from "uplot";
  import { api, shownError } from "./api";
  import { copy, metricMeta, type Lang } from "./i18n";

  let {
    lang,
    name,
    seconds,
    title = "",
    mode = "raw",
    baseline = "",
  }: {
    lang: Lang;
    name: string;
    seconds: number;
    title?: string;
    mode?: "raw" | "busy" | "rate" | "used";
    baseline?: string;
  } = $props();
  let holder = $state<HTMLDivElement | null>(null);
  let message = $state("");
  let chart: uPlot | null = null;
  const meta = $derived(metricMeta(lang, name));
  const hint = $derived(mode === "busy" ? copy(lang, "chartBusyHint") : meta.hint);
  const unitLabel = $derived(mode === "busy" ? "%" : mode === "used" ? "MiB" : meta.unit);

  function scaleValues(points: Array<{ ts: number; value: number }>): number[] {
    if (meta.unit === "MiB") return points.map((point) => point.value / 1048576);
    if (name.includes("cpu.idle") || name.includes("cpu.iowait") || name.includes("cpu.steal")) {
      return points.map((point) => point.value);
    }
    return points.map((point) => point.value);
  }

  function draw(range: number): void {
    const end = Math.floor(Date.now() / 1000);
    const start = end - range;
    const step = range <= 3600 ? 10 : range <= 86400 ? 60 : 300;
    const query = (series: string) =>
      api<{ points: Array<{ ts: number; value: number }> }>(
        `/api/v1/metrics/query?series=${encodeURIComponent(series)}&start=${start}&end=${end}&step=${step}`,
      );
    void Promise.all([query(name), baseline ? query(baseline) : Promise.resolve({ points: [] })]).then(
      ([payload, base]) => {
        chart?.destroy();
        chart = null;
        if (!holder) return;
        holder.replaceChildren();
        if (payload.points.length === 0) {
          message = copy(lang, "empty");
          return;
        }
        message = "";
        const raw = scaleValues(payload.points);
        const totals = new Map(base.points.map((point) => [point.ts, point.value]));
        const values =
          mode === "used"
            ? payload.points.map((point) => {
                const total = totals.get(point.ts);
                if (total === undefined) return 0;
                return Math.max(0, (total - point.value) / 1048576);
              })
            : mode === "busy"
            ? raw.map((value) => Math.max(0, Math.min(100, 100 - value)))
            : mode === "rate"
              ? raw.map((value, index) => {
                  if (index === 0) return 0;
                  const dt = payload.points[index].ts - payload.points[index - 1].ts;
                  if (dt <= 0) return 0;
                  return Math.max(0, (value - raw[index - 1]) / dt);
                })
              : raw;
        const unit = mode === "busy" ? "%" : mode === "rate" ? "" : mode === "used" ? "MiB" : meta.unit;
        const clock = (ts: number) =>
          new Date(ts * 1000).toLocaleTimeString(lang === "ru" ? "ru-RU" : "en-US", {
            hour: "2-digit",
            minute: "2-digit",
          });
        chart = new uPlot(
          {
            width: holder.clientWidth || 640,
            height: 180,
            series: [
              { label: copy(lang, "chartTime"), value: (_self, ts) => clock(ts) },
              { label: title || meta.title, stroke: "#02b8cc", width: 1.5 },
            ],
            axes: [
              {
                stroke: "#8a8f98",
                grid: { stroke: "#23252a" },
                values: (_self, splits) => splits.map((ts) => clock(ts)),
              },
              {
                stroke: "#8a8f98",
                grid: { stroke: "#23252a" },
                size: 56,
                values: (_u, splits) =>
                  splits.map((value) => (unit === "%" ? `${Math.round(value)}%` : String(Math.round(value)))),
              },
            ],
            cursor: { sync: { key: "atlas-host" }, drag: { x: true, y: false } },
          },
          [payload.points.map((point) => point.ts), values],
          holder,
        );
      },
    ).catch((error: unknown) => {
      message = shownError(error, lang);
    });
  }

  $effect(() => {
    draw(seconds);
  });

  onMount(() => () => chart?.destroy());
</script>

<div class="atlas-fade-in mb-4">
  <div class="mb-1 flex flex-wrap items-baseline justify-between gap-2">
    <p class="text-sm text-paper">{title || meta.title}</p>
    {#if unitLabel}
      <p class="text-xs text-ash">{unitLabel}</p>
    {/if}
  </div>
  {#if hint}
    <p class="mb-2 text-xs text-fog">{hint}</p>
  {/if}
  {#if message}
    <p class="mb-2 text-sm text-fog">{message}</p>
  {/if}
  <div class="rounded-xl border border-graphite bg-carbon p-3" bind:this={holder}></div>
</div>
