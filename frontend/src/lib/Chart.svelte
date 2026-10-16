<script lang="ts">
  import { onMount } from "svelte";
  import uPlot from "uplot";
  import { api, shownError } from "./api";
  import { copy, metricMeta, type Lang } from "./i18n";

  let { lang, name, seconds }: { lang: Lang; name: string; seconds: number } = $props();
  let holder = $state<HTMLDivElement | null>(null);
  let message = $state("");
  let chart: uPlot | null = null;
  const meta = $derived(metricMeta(lang, name));

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
    void api<{ points: Array<{ ts: number; value: number }> }>(
      `/api/v1/metrics/query?series=${encodeURIComponent(name)}&start=${start}&end=${end}&step=${step}`,
    )
      .then((payload) => {
        chart?.destroy();
        chart = null;
        if (!holder) return;
        holder.replaceChildren();
        if (payload.points.length === 0) {
          message = copy(lang, "empty");
          return;
        }
        message = "";
        const values = scaleValues(payload.points);
        chart = new uPlot(
          {
            width: holder.clientWidth || 640,
            height: 160,
            series: [{}, { label: meta.title, stroke: "#02b8cc", width: 1.5 }],
            axes: [
              { stroke: "#8a8f98", grid: { stroke: "#23252a" } },
              {
                stroke: "#8a8f98",
                grid: { stroke: "#23252a" },
                values: (_u, splits) =>
                  splits.map((value) =>
                    meta.unit ? `${Math.round(value)}${meta.unit === "%" ? "%" : ""}` : String(value),
                  ),
              },
            ],
            cursor: { sync: { key: "atlas-host" }, drag: { x: true, y: false } },
          },
          [payload.points.map((point) => point.ts), values],
          holder,
        );
      })
      .catch((error: unknown) => {
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
    <p class="text-sm text-paper">{meta.title}</p>
    {#if meta.unit}
      <p class="text-xs text-ash">{meta.unit}</p>
    {/if}
  </div>
  {#if meta.hint}
    <p class="mb-2 text-xs text-fog">{meta.hint}</p>
  {/if}
  {#if message}
    <p class="mb-2 text-sm text-fog">{message}</p>
  {/if}
  <div class="rounded-xl border border-graphite bg-carbon p-3" bind:this={holder}></div>
</div>
