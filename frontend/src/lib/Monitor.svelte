<script lang="ts">
  import { onMount } from "svelte";
  import "uplot/dist/uPlot.min.css";
  import Chart from "./Chart.svelte";
  import { api, shownError } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let message = $state("");
  let range = $state(3600);
  let names = $state<string[]>([]);
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
  });
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "monitoring")}</h1>
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
