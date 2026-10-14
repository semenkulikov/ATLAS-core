<script lang="ts">
  import { onMount } from "svelte";
  import uPlot from "uplot";
  import "uplot/dist/uPlot.min.css";
  import { api } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let message = $state("");
  let range = $state(3600);
  let loadHolder = $state<HTMLDivElement | null>(null);
  let memoryHolder = $state<HTMLDivElement | null>(null);
  let cpuHolder = $state<HTMLDivElement | null>(null);
  const charts: uPlot[] = [];
  const presets = [
    [300, "5m"],
    [3600, "1h"],
    [86400, "24h"],
    [604800, "7d"],
    [2592000, "30d"],
  ] as const;
  const series = [
    ["host.load.1", () => loadHolder],
    ["host.memory.available_bytes", () => memoryHolder],
    ["host.cpu.idle", () => cpuHolder],
  ] as const;

  function draw(seconds: number): void {
    const end = Math.floor(Date.now() / 1000);
    const start = end - seconds;
    const step = seconds <= 3600 ? 10 : seconds <= 86400 ? 60 : 300;
    charts.forEach((chart) => chart.destroy());
    charts.length = 0;
    message = "";
    for (const [name, holderOf] of series) {
      void api<{ points: Array<{ ts: number; value: number }> }>(
        `/api/v1/metrics/query?series=${name}&start=${start}&end=${end}&step=${step}`,
      )
        .then((payload) => {
          const holder = holderOf();
          if (!holder) return;
          holder.replaceChildren();
          if (payload.points.length === 0) {
            message = copy(lang, "empty");
            return;
          }
          charts.push(
            new uPlot(
              {
                width: holder.clientWidth || 640,
                height: 180,
                series: [{}, { label: name, stroke: "#02b8cc", width: 1 }],
                axes: [{ stroke: "#8a8f98" }, { stroke: "#8a8f98" }],
                cursor: { sync: { key: "atlas-host" }, drag: { x: true, y: false } },
              },
              [payload.points.map((point) => point.ts), payload.points.map((point) => point.value)],
              holder,
            ),
          );
        })
        .catch((error: unknown) => {
          message = error instanceof Error ? error.message : copy(lang, "error");
        });
    }
  }

  onMount(() => {
    draw(range);
    return () => charts.forEach((chart) => chart.destroy());
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
  {#if message}
    <p class="text-sm text-fog" role="status">{message}</p>
  {/if}
  <p class="mb-2 text-sm text-fog">host.load.1</p>
  <div class="mb-4 rounded-xl border border-graphite bg-carbon p-3" bind:this={loadHolder}></div>
  <p class="mb-2 text-sm text-fog">host.memory.available_bytes</p>
  <div class="mb-4 rounded-xl border border-graphite bg-carbon p-3" bind:this={memoryHolder}></div>
  <p class="mb-2 text-sm text-fog">host.cpu.idle</p>
  <div class="rounded-xl border border-graphite bg-carbon p-3" bind:this={cpuHolder}></div>
</section>
