<script lang="ts">
  import { onDestroy } from "svelte";
  import { api, shownError } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let source = $state("journal:atlas");
  let query = $state("");
  let pattern = $state("");
  let lines = $state<string[]>([]);
  let message = $state("");
  let follow = $state(false);
  let paused = $state(false);
  let timer: ReturnType<typeof setInterval> | undefined;

  async function load(): Promise<void> {
    message = "";
    try {
      const params = new URLSearchParams({ source, q: query, pattern });
      const payload = await api<{ lines: string[] }>(`/api/v1/logs?${params.toString()}`);
      lines = payload.lines;
    } catch (error) {
      lines = [];
      message = shownError(error, lang);
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
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "logs")}</h1>
  <form class="mb-4 flex flex-wrap gap-2" onsubmit={submit}>
    <label class="min-w-48 flex-1 text-sm text-fog">
      {copy(lang, "source")}
      <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" bind:value={source} />
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
    <button class="self-end rounded-md border border-graphite px-3 py-2 text-sm text-fog" type="button" onclick={() => (follow = !follow)}>
      {copy(lang, "follow")}
    </button>
    <button class="self-end rounded-md border border-graphite px-3 py-2 text-sm text-fog" type="button" onclick={() => (paused = !paused)} disabled={!follow}>
      {copy(lang, "pause")}
    </button>
  </form>
  {#if message}
    <p class="mb-3 text-sm text-warn" role="alert">{message}</p>
  {/if}
  <pre class="overflow-auto rounded-xl border border-graphite bg-carbon p-3 font-mono text-xs text-mist">{lines.join("\n")}</pre>
</section>
