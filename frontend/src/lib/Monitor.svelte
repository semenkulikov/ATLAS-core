<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import "uplot/dist/uPlot.min.css";
  import Chart from "./Chart.svelte";
  import { api, shownError } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let message = $state("");
  let range = $state(3600);
  let names = $state<string[]>([]);
  let live = $state<{
    loadavg: [number, number, number] | null;
    memory_available: number | null;
    cpu_idle: number | null;
    units: { name: string; memory_bytes: number | null }[];
  } | null>(null);
  let socket: WebSocket | null = null;
  const presets = [
    [300, "5m"],
    [3600, "1h"],
    [86400, "24h"],
    [604800, "7d"],
    [2592000, "30d"],
  ] as const;

  onMount(() => {
    void api<{ series: string[] }>("/api/v1/metrics/series")
      .then((payload) => {
        names = payload.series;
        if (names.length === 0) message = copy(lang, "empty");
      })
      .catch((error: unknown) => {
        message = shownError(error, lang);
      });
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/api/v1/stream`);
    socket.addEventListener("open", () => {
      socket?.send(JSON.stringify({ subscribe: "metrics.live" }));
    });
    socket.addEventListener("message", (event) => {
      try {
        const body = JSON.parse(String(event.data)) as {
          channel?: string;
          loadavg?: [number, number, number] | null;
          memory_available?: number | null;
          cpu_idle?: number | null;
          units?: { name: string; memory_bytes: number | null }[];
        };
        if (body.channel !== "metrics.live") return;
        live = {
          loadavg: body.loadavg ?? null,
          memory_available: body.memory_available ?? null,
          cpu_idle: body.cpu_idle ?? null,
          units: body.units ?? [],
        };
      } catch {
        return;
      }
    });
  });

  onDestroy(() => {
    socket?.close();
    socket = null;
  });
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "monitoring")}</h1>
  {#if live}
    <div class="mb-4 grid gap-2 rounded-xl border border-graphite bg-carbon p-3 text-sm text-mist md:grid-cols-3">
      <p>
        load
        <span class="font-mono text-paper">
          {live.loadavg ? live.loadavg.map((value) => value.toFixed(2)).join(" ") : "—"}
        </span>
      </p>
      <p>
        mem avail
        <span class="font-mono text-paper">
          {live.memory_available === null ? "—" : `${Math.round(live.memory_available / 1048576)} MiB`}
        </span>
      </p>
      <p>
        cpu idle
        <span class="font-mono text-paper">{live.cpu_idle === null ? "—" : live.cpu_idle.toFixed(0)}</span>
      </p>
      {#each live.units as unit (unit.name)}
        <p class="font-mono text-xs text-fog">
          {unit.name}
          {unit.memory_bytes === null ? "" : `${Math.round(unit.memory_bytes / 1048576)} MiB`}
        </p>
      {/each}
    </div>
  {/if}
  <div class="mb-3 flex gap-2">
    {#each presets as [seconds, label] (seconds)}
      <button
        type="button"
        class="rounded-md px-2 py-1 text-sm {range === seconds ? 'text-accent' : 'text-fog'}"
        onclick={() => (range = seconds)}
      >
        {label}
      </button>
    {/each}
  </div>
  {#if message}
    <p class="text-sm text-fog" role="status">{message}</p>
  {/if}
  {#each names as name (name)}
    <Chart {lang} {name} seconds={range} />
  {/each}
</section>
