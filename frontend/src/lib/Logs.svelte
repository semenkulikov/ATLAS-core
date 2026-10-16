<script lang="ts">
  import { onDestroy } from "svelte";
  import { api, errorDetail, shownError } from "./api";
  import { copy, type Lang } from "./i18n";
  import ErrorModal from "./ui/ErrorModal.svelte";
  import LiveBadge from "./ui/LiveBadge.svelte";

  let { lang }: { lang: Lang } = $props();
  let source = $state("journal:atlas");
  let query = $state("");
  let pattern = $state("");
  let lines = $state<string[]>([]);
  let flashFrom = $state(-1);
  let follow = $state(true);
  let paused = $state(false);
  let errorMessage = $state("");
  let errorExtra = $state("");
  let timer: ReturnType<typeof setInterval> | undefined;

  const presets = [
    { value: "journal:atlas", labelKey: "logPresetAtlas" as const },
    { value: "journal:syslog", labelKey: "logPresetSyslog" as const },
  ];

  async function load(): Promise<void> {
    try {
      const params = new URLSearchParams({ source, q: query, pattern });
      const payload = await api<{ lines: string[] }>(`/api/v1/logs?${params.toString()}`);
      const previous = lines.length;
      const next = payload.lines;
      if (follow && next.length > previous) {
        flashFrom = previous;
      } else {
        flashFrom = -1;
      }
      lines = next;
    } catch (error) {
      lines = [];
      errorMessage = shownError(error, lang);
      errorExtra = errorDetail(error);
    }
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    void load();
  }

  $effect(() => {
    clearInterval(timer);
    if (follow && !paused) {
      void load();
      timer = setInterval(() => void load(), 2000);
    }
  });

  onDestroy(() => clearInterval(timer));
</script>

<section>
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <h1 class="text-2xl text-paper">{copy(lang, "logs")}</h1>
    <LiveBadge {lang} on={follow && !paused} />
  </div>
  <form class="mb-4 flex flex-wrap gap-2" onsubmit={submit}>
    <label class="min-w-48 flex-1 text-sm text-fog">
      {copy(lang, "source")}
      <select class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" bind:value={source}>
        {#each presets as preset (preset.value)}
          <option value={preset.value}>{copy(lang, preset.labelKey)}</option>
        {/each}
      </select>
    </label>
    <label class="w-40 text-sm text-fog">
      {copy(lang, "filter")}
      <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" bind:value={query} />
    </label>
    <label class="w-40 text-sm text-fog">
      {copy(lang, "pattern")}
      <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" bind:value={pattern} />
    </label>
    <button class="self-end rounded-md bg-accent px-3 py-2 text-void" type="submit">{copy(lang, "show")}</button>
    <button
      class="self-end rounded-md border border-graphite px-3 py-2 text-sm {follow ? 'text-accent' : 'text-fog'}"
      type="button"
      onclick={() => (follow = !follow)}
    >
      {copy(lang, "follow")}
    </button>
    <button
      class="self-end rounded-md border border-graphite px-3 py-2 text-sm text-fog"
      type="button"
      onclick={() => (paused = !paused)}
      disabled={!follow}
    >
      {copy(lang, "pause")}
    </button>
  </form>
  <div class="overflow-auto rounded-xl border border-graphite bg-carbon p-3 font-mono text-xs text-mist">
    {#each lines as line, index (index)}
      <div class={index >= flashFrom && flashFrom >= 0 ? "atlas-flash-row whitespace-pre-wrap" : "whitespace-pre-wrap"}>
        {line}
      </div>
    {:else}
      <p class="text-fog">{copy(lang, "empty")}</p>
    {/each}
  </div>
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
