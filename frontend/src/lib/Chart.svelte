<script lang="ts">
  import { onMount } from "svelte";
  import uPlot from "uplot";
  import { api, shownError } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang, name, seconds }: { lang: Lang; name: string; seconds: number } = $props();
  let holder = $state<HTMLDivElement | null>(null);
  let message = $state("");
  let chart: uPlot | null = null;

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
        chart = new uPlot(
          {
            width: holder.clientWidth || 640,
            height: 160,
            series: [{}, { label: name, stroke: "#02b8cc", width: 1 }],
            axes: [{ stroke: "#8a8f98" }, { stroke: "#8a8f98" }],
            cursor: { sync: { key: "atlas-host" }, drag: { x: true, y: false } },
          },
          [payload.points.map((point) => point.ts), payload.points.map((point) => point.value)],
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

<p class="mb-2 text-sm text-fog">{name}</p>
{#if message}
  <p class="mb-2 text-sm text-fog">{message}</p>
{/if}
<div class="mb-4 rounded-xl border border-graphite bg-carbon p-3" bind:this={holder}></div>
