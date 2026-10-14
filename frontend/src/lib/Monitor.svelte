<script lang="ts">
  import { onMount } from "svelte";
  import uPlot from "uplot";
  import "uplot/dist/uPlot.min.css";
  import { api } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let holder = $state<HTMLDivElement | null>(null);
  let message = $state("");
  let range = $state(3600);
  let chart: uPlot | null = null;
  const presets = [
    [300, "5m"],
    [3600, "1h"],
    [86400, "24h"],
    [604800, "7d"],
    [2592000, "30d"],
  ] as const;

  function draw(seconds: number): void {
    const end = Math.floor(Date.now() / 1000);
    const start = end - seconds;
    const step = seconds <= 3600 ? 10 : seconds <= 86400 ? 60 : 300;
    void api<{ points: Array<{ ts: number; value: number }> }>(
      `/api/v1/metrics/query?series=host.load.1&start=${start}&end=${end}&step=${step}`,
    )
      .then((payload) => {
        chart?.destroy();
        chart = null;
        if (!holder) return;
        if (payload.points.length === 0) {
          message = copy(lang, "empty");
          return;
        }
        message = "";
        chart = new uPlot(
          {
            width: holder.clientWidth || 640,
            height: 240,
            series: [{}, { stroke: "#02b8cc", width: 1 }],
            axes: [{ stroke: "#8a8f98" }, { stroke: "#8a8f98" }],
            cursor: { drag: { x: true, y: false } },
          },
          [payload.points.map((point) => point.ts), payload.points.map((point) => point.value)],
          holder,
        );
      })
      .catch((error: unknown) => {
        message = error instanceof Error ? error.message : copy(lang, "error");
      });
  }

  onMount(() => {
    draw(range);
    return () => chart?.destroy();
  });
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "monitoring")}</h1>
  <div class="mb-3 flex gap-2">
    {#each presets as [seconds, label] (seconds)}
      <button
        type="button"
        class="rounded-md px-2 py-1 text-sm {range === seconds ? 'text-accent' : 'text-fog'}"
        onclick={() => {
          range = seconds;
          draw(seconds);
        }}
      >
        {label}
      </button>
    {/each}
  </div>
  <p class="mb-3 text-sm text-fog">host.load.1</p>
  {#if message}
    <p class="text-sm text-fog" role="status">{message}</p>
  {/if}
  <div class="rounded-xl border border-graphite bg-carbon p-3" bind:this={holder}></div>
</section>
