<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import "uplot/dist/uPlot.min.css";
  import Chart from "./Chart.svelte";
  import { api, errorDetail, shownError } from "./api";
  import { formatBytes } from "./format";
  import { copy, type Lang } from "./i18n";
  import { loadPanel, type PanelData } from "./inventory";
  import { selectedApp } from "./selection";
  import ErrorModal from "./ui/ErrorModal.svelte";
  import LiveBadge from "./ui/LiveBadge.svelte";

  let { lang }: { lang: Lang } = $props();
  let range = $state(3600);
  let names = $state<string[]>([]);
  let live = $state(false);
  let data = $state<PanelData | null>(null);
  let errorMessage = $state("");
  let errorExtra = $state("");
  let socket: WebSocket | null = null;
  let units = $state<{ name: string; memory_bytes: number | null }[]>([]);

  const presets = [
    [900, "period15"],
    [3600, "periodHour"],
    [86400, "periodDay"],
    [604800, "periodWeek"],
  ] as const;

  const diskName = $derived(names.find((name) => name.includes(".read_bytes")) ?? "");
  const netName = $derived(names.find((name) => name.includes(".rx_bytes")) ?? "");
  const filteredUnits = $derived.by(() => {
    const id = $selectedApp;
    if (!id || !data) return units;
    const app = data.apps.find((item) => item.id === id);
    if (!app) return units;
    const keys = new Set([...app.services.map((row) => row.key), ...app.containers.map((row) => String(row.payload.name))]);
    return units.filter((unit) => keys.has(unit.name));
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
    void loadPanel()
      .then((body) => {
        data = body;
      })
      .catch(() => undefined);
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}/api/v1/stream`);
    socket.addEventListener("open", () => {
      live = true;
      socket?.send(JSON.stringify({ subscribe: "metrics.live" }));
    });
    socket.addEventListener("close", () => {
      live = false;
    });
    socket.addEventListener("message", (event) => {
      try {
        const body = JSON.parse(String(event.data)) as {
          channel?: string;
          units?: { name: string; memory_bytes: number | null }[];
        };
        if (body.channel !== "metrics.live") return;
        units = body.units ?? [];
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

<section class="atlas-fade-in">
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <h1 class="screen-title">{copy(lang, "monitoring")}</h1>
    <LiveBadge {lang} on={live} />
  </div>
  {#if $selectedApp}
    <p class="chip mb-4">
      {copy(lang, "appFilter")}: {data?.apps.find((item) => item.id === $selectedApp)?.name}
      <button type="button" class="ml-2" onclick={() => selectedApp.set("")}>{copy(lang, "clearApp")}</button>
    </p>
  {/if}
  <div class="seg mb-4">
    {#each presets as [seconds, key] (seconds)}
      <button type="button" class="btn btn-ghost" aria-pressed={range === seconds} onclick={() => (range = seconds)}>
        {copy(lang, key)}
      </button>
    {/each}
  </div>
  <div class="grid gap-4 lg:grid-cols-2">
    {#if names.includes("host.cpu.idle")}
      <div class="card"><Chart {lang} name="host.cpu.idle" seconds={range} title={copy(lang, "chartCpu")} mode="busy" /></div>
    {/if}
    {#if names.includes("host.memory.available_bytes")}
      <div class="card"><Chart {lang} name="host.memory.available_bytes" baseline={names.includes("host.memory.total_bytes") ? "host.memory.total_bytes" : ""} seconds={range} title={copy(lang, "chartMem")} mode="used" /></div>
    {/if}
    {#if diskName}
      <div class="card"><Chart {lang} name={diskName} seconds={range} title={copy(lang, "chartDisk")} mode="rate" /></div>
    {/if}
    {#if netName}
      <div class="card"><Chart {lang} name={netName} seconds={range} title={copy(lang, "chartNet")} mode="rate" /></div>
    {/if}
    {#if names.includes("host.load.1")}
      <div class="card"><Chart {lang} name="host.load.1" seconds={range} title={copy(lang, "chartLoad")} /></div>
    {/if}
  </div>
  <h2 class="block-title mb-3 mt-6">{copy(lang, "whoUses")}</h2>
  <div class="card overflow-auto p-0">
    <table class="data-table">
      <thead>
        <tr>
          <th>{copy(lang, "apps")}</th>
          <th>{copy(lang, "cpu")}</th>
          <th>{copy(lang, "memory")}</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredUnits as unit (unit.name)}
          <tr>
            <td class="mono">{unit.name}</td>
            <td>— <span class="kicker">{copy(lang, "cpuUnknown")}</span></td>
            <td>{unit.memory_bytes === null ? "—" : formatBytes(unit.memory_bytes, lang)}</td>
          </tr>
        {:else}
          <tr><td colspan="3" class="text-fog">{copy(lang, "empty")}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

{#if errorMessage}
  <ErrorModal {lang} message={errorMessage} detail={errorExtra} onclose={() => (errorMessage = "")} />
{/if}
