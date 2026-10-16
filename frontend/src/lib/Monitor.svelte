<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import "uplot/dist/uPlot.min.css";
  import Chart from "./Chart.svelte";
  import { api, errorDetail, shownError } from "./api";
  import { copy, groupLabel, metricMeta, type Lang } from "./i18n";
  import Accordion from "./ui/Accordion.svelte";
  import ErrorModal from "./ui/ErrorModal.svelte";
  import LiveBadge from "./ui/LiveBadge.svelte";

  let { lang }: { lang: Lang } = $props();
  let range = $state(3600);
  let names = $state<string[]>([]);
  let live = $state<{
    loadavg: [number, number, number] | null;
    memory_available: number | null;
    cpu_idle: number | null;
    units: { name: string; memory_bytes: number | null }[];
  } | null>(null);
  let liveKey = $state(0);
  let connected = $state(false);
  let moreOpen = $state(false);
  let errorMessage = $state("");
  let errorExtra = $state("");
  let socket: WebSocket | null = null;
  const presets = [
    [300, "5m"],
    [3600, "1h"],
    [86400, "24h"],
    [604800, "7d"],
    [2592000, "30d"],
  ] as const;

  const hostSeries = $derived(
    names.filter((name) => metricMeta(lang, name).group === "host"),
  );
  const extraSeries = $derived(
    names.filter((name) => metricMeta(lang, name).group !== "host"),
  );
  const extrasByGroup = $derived.by(() => {
    const groups = new Map<string, string[]>();
    for (const name of extraSeries) {
      const group = metricMeta(lang, name).group;
      const list = groups.get(group) ?? [];
      list.push(name);
      groups.set(group, list);
    }
    return [...groups.entries()];
  });

  onMount(() => {
    void api<{ series: string[] }>("/api/v1/metrics/series")
      .then((payload) => {
        names = payload.series;
      })
      .catch((error: unknown) => {
        errorMessage = shownError(error, lang);
        errorExtra = errorDetail(error);
      });
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/api/v1/stream`);
    socket.addEventListener("open", () => {
      connected = true;
      socket?.send(JSON.stringify({ subscribe: "metrics.live" }));
    });
    socket.addEventListener("close", () => {
      connected = false;
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
        liveKey += 1;
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
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <h1 class="text-2xl text-paper">{copy(lang, "monitoring")}</h1>
    <LiveBadge {lang} on={connected} />
  </div>

  {#if live}
    <div
      class="atlas-tick mb-4 grid gap-2 rounded-xl border border-graphite bg-carbon p-3 text-sm text-mist md:grid-cols-3"
      data-tick={liveKey}
    >
      <p>
        {copy(lang, "loadAvg")}
        <span class="mt-1 block font-mono text-paper">
          {live.loadavg ? live.loadavg.map((value) => value.toFixed(2)).join(" ") : "—"}
        </span>
      </p>
      <p>
        {copy(lang, "memAvailable")}
        <span class="mt-1 block font-mono text-paper">
          {live.memory_available === null ? "—" : `${Math.round(live.memory_available / 1048576)} MiB`}
        </span>
      </p>
      <p>
        {copy(lang, "cpuIdle")}
        <span class="mt-1 block font-mono text-paper">
          {live.cpu_idle === null ? "—" : `${live.cpu_idle.toFixed(0)}%`}
        </span>
      </p>
      {#each live.units as unit (unit.name)}
        <p class="text-xs text-fog">
          <span class="text-ash">{copy(lang, "unitMemory")}</span>
          <span class="mt-0.5 block font-mono">{unit.name}</span>
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

  {#if names.length === 0 && !errorMessage}
    <p class="text-sm text-fog">{copy(lang, "empty")}</p>
  {/if}

  {#each hostSeries as name (name)}
    <Chart {lang} {name} seconds={range} />
  {/each}

  {#if extrasByGroup.length > 0}
    <Accordion title={copy(lang, "chartsMore")} count={extraSeries.length} bind:open={moreOpen}>
      {#each extrasByGroup as [group, series] (group)}
        <h2 class="mb-2 mt-3 px-2 text-xs uppercase tracking-wide text-ash">{groupLabel(lang, group)}</h2>
        {#each series as name (name)}
          <Chart {lang} {name} seconds={range} />
        {/each}
      {/each}
    </Accordion>
  {/if}
</section>

{#if errorMessage}
  <ErrorModal
    {lang}
    message={errorMessage}
    detail={errorExtra}
    onclose={() => {
      errorMessage = "";
      errorExtra = "";
    }}
  />
{/if}
