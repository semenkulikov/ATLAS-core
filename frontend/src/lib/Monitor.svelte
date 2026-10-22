<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import "uplot/dist/uPlot.min.css";
  import Chart from "./Chart.svelte";
  import { api, errorDetail, shownError } from "./api";
  import { formatBytes, textOf } from "./format";
  import { copy, type Lang } from "./i18n";
  import { loadPanel, type PanelData } from "./inventory";
  import { liveCpu, liveOn, liveRows, retainLive, type LiveRow } from "./live";
  import { uplinkInterface } from "./net";
  import { selectedApp } from "./selection";
  import ErrorModal from "./ui/ErrorModal.svelte";
  import LiveBadge from "./ui/LiveBadge.svelte";

  let { lang }: { lang: Lang } = $props();
  let range = $state(3600);
  let names = $state<string[]>([]);
  let data = $state<PanelData | null>(null);
  let errorMessage = $state("");
  let errorExtra = $state("");
  let releaseLive: (() => void) | undefined;

  const presets = [
    [900, "period15"],
    [3600, "periodHour"],
    [86400, "periodDay"],
    [604800, "periodWeek"],
  ] as const;

  const diskName = $derived(names.find((name) => name.includes(".read_bytes")) ?? "");
  const netName = $derived.by(() => {
    const iface = uplinkInterface(names, data?.defaultRoute ?? "");
    return iface ? `host.net.${iface}.rx_bytes` : "";
  });
  const filteredRows = $derived.by(() => {
    const id = $selectedApp;
    const app = id && data ? data.apps.find((item) => item.id === id) : undefined;
    const chosen = app ? $liveRows.filter((row) => belongsTo(row, app)) : $liveRows;
    return [...chosen].sort((a, b) => (b.memory_bytes ?? -1) - (a.memory_bytes ?? -1)).slice(0, 8);
  });

  function belongsTo(row: LiveRow, app: PanelData["apps"][number] | undefined): boolean {
    if (!app) return false;
    if (row.kind === "service") {
      return app.services.some((item) => item.key === row.name || item.key === `${row.name}.service`);
    }
    return app.containers.some((item) => textOf(item.payload.name) === row.name || textOf(item.payload.id).startsWith(row.name));
  }

  function rowLabel(row: LiveRow): string {
    if (row.kind === "container" && data) {
      const known = [...data.apps.flatMap((app) => app.containers), ...data.system.containers];
      const match = known.find((item) => textOf(item.payload.id).startsWith(row.name));
      const name = match ? textOf(match.payload.name) : "";
      if (name) return name;
    }
    return row.kind === "service" ? `${row.name}.service` : row.name;
  }

  function rowKey(row: LiveRow): string {
    return `${row.kind}:${row.name}`;
  }

  onMount(() => {
    releaseLive = retainLive();
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
  });

  onDestroy(() => releaseLive?.());
</script>

<section class="atlas-fade-in">
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <h1 class="screen-title">{copy(lang, "monitoring")}</h1>
    <LiveBadge {lang} on={$liveOn} />
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
        {#each filteredRows as row (rowKey(row))}
          <tr>
            <td class="mono">{rowLabel(row)}</td>
            <td>{$liveCpu[rowKey(row)] === undefined ? "—" : `${Math.round($liveCpu[rowKey(row)])}%`}</td>
            <td>{row.memory_bytes === null ? "—" : formatBytes(row.memory_bytes, lang)}</td>
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
