<script lang="ts">
  import { onMount } from "svelte";
  import uPlot from "uplot";
  import "uplot/dist/uPlot.min.css";
  import { api } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let holder = $state<HTMLDivElement | null>(null);
  let message = $state("");
  let chart: uPlot | null = null;

  onMount(() => {
    const end = Math.floor(Date.now() / 1000);
    const start = end - 3600;
    void api<{ points: Array<{ ts: number; value: number }> }>(
      `/api/v1/metrics/query?series=host.load.1&start=${start}&end=${end}&step=10`,
    )
      .then((payload) => {
        if (!holder) return;
        if (payload.points.length === 0) {
          message = copy(lang, "empty");
          return;
        }
        chart = new uPlot(
          {
            width: holder.clientWidth || 640,
            height: 240,
            series: [{}, { stroke: "#02b8cc", width: 1 }],
            axes: [
              { stroke: "#8a8f98" },
              { stroke: "#8a8f98" },
            ],
            cursor: { drag: { x: true, y: false } },
          },
          [payload.points.map((point) => point.ts), payload.points.map((point) => point.value)],
          holder,
        );
      })
      .catch((error: unknown) => {
        message = error instanceof Error ? error.message : copy(lang, "error");
      });
    return () => chart?.destroy();
  });
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "monitoring")}</h1>
  <p class="mb-3 text-sm text-fog">host.load.1</p>
  {#if message}
    <p class="text-sm text-fog" role="status">{message}</p>
  {/if}
  <div class="rounded-xl border border-graphite bg-carbon p-3" bind:this={holder}></div>
</section>
