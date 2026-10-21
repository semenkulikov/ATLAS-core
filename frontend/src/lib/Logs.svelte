<script lang="ts">
  import { onDestroy } from "svelte";
  import { api, errorDetail, shownError } from "./api";
  import { copy, type Lang } from "./i18n";
  import { selectedApp } from "./selection";
  import CopyButton from "./ui/CopyButton.svelte";
  import LiveBadge from "./ui/LiveBadge.svelte";

  let { lang }: { lang: Lang } = $props();
  let source = $state("journal:syslog");
  let query = $state("");
  let lines = $state<string[]>([]);
  let follow = $state(true);
  let paused = $state(false);
  let errorMessage = $state("");
  let detail = $state("");
  let level = $state("all");
  let timer: ReturnType<typeof setInterval> | undefined;

  const visible = $derived(
    lines.filter((line) => {
      if (level === "all") return true;
      const lower = line.toLowerCase();
      const error = lower.includes("error") || lower.includes("crit");
      const warn = error || lower.includes("warn");
      return level === "error" ? error : warn;
    }),
  );
  const errorCount = $derived(lines.filter((line) => /error|crit/i.test(line)).length);

  async function load(): Promise<void> {
    try {
      const params = new URLSearchParams({ source, q: query });
      const payload = await api<{ lines: string[] }>(`/api/v1/logs?${params.toString()}`);
      lines = payload.lines;
      errorMessage = "";
      detail = "";
    } catch (error) {
      lines = [];
      errorMessage = shownError(error, lang);
      detail = errorDetail(error);
    }
  }

  $effect(() => {
    clearInterval(timer);
    if (follow && !paused && document.visibilityState !== "hidden") {
      void load();
      timer = setInterval(() => {
        if (document.visibilityState === "visible") void load();
      }, 5000);
    }
  });

  onDestroy(() => clearInterval(timer));

  function download(): void {
    const blob = new Blob([visible.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "atlas-log.txt";
    link.click();
    URL.revokeObjectURL(url);
  }
</script>

<section class="atlas-fade-in">
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <h1 class="screen-title">{copy(lang, "logs")}</h1>
    <LiveBadge {lang} on={follow && !paused} />
  </div>
  {#if $selectedApp}
    <p class="chip mb-3">
      {copy(lang, "appFilter")}: {$selectedApp}
      <button type="button" class="ml-2" onclick={() => selectedApp.set("")}>{copy(lang, "clearApp")}</button>
    </p>
    <p class="kicker mb-3">{copy(lang, "journalNote")}</p>
  {/if}
  <form class="mb-4 flex flex-wrap gap-2" onsubmit={(event) => { event.preventDefault(); void load(); }}>
    <label class="text-sm text-fog">
      {copy(lang, "sourceLabel")}
      <select class="mt-1 block h-8 rounded-md border border-smoke bg-void px-2 font-mono text-sm text-paper" bind:value={source}>
        <option value="journal:syslog">{copy(lang, "syslogJournal")}</option>
        <option value="journal:atlas">{copy(lang, "atlasJournal")}</option>
      </select>
    </label>
    <label class="text-sm text-fog">
      {copy(lang, "levelLabel")}
      <select class="mt-1 block h-8 rounded-md border border-smoke bg-void px-2 text-sm" bind:value={level}>
        <option value="all">{copy(lang, "levelAll")}</option>
        <option value="warn">{copy(lang, "levelWarn")}</option>
        <option value="error">{copy(lang, "levelError")}</option>
      </select>
    </label>
    <label class="min-w-40 flex-1 text-sm text-fog">
      {copy(lang, "filterQuery")}
      <input class="mt-1 block h-8 w-full rounded-md border border-smoke bg-void px-3 text-sm" bind:value={query} />
    </label>
    <button class="btn btn-secondary self-end" type="submit">{copy(lang, "apply")}</button>
    <button class="btn btn-ghost self-end" type="button" onclick={() => (follow = !follow)}>{copy(lang, "followLive")}</button>
    <button class="btn btn-secondary self-end" type="button" onclick={download}>{copy(lang, "downloadTxt")}</button>
  </form>
  {#if errorMessage}
    <div class="card mb-4">
      <p class="text-paper">{copy(lang, "logsDenied")}</p>
      <p class="mono mt-3">{copy(lang, "commandToCopy")}</p>
      <CopyButton {lang} text={copy(lang, "commandToCopy")} label={copy(lang, "copyCommand")} />
      {#if detail && !detail.includes("logs.source")}<p class="kicker mt-3">{detail}</p>{/if}
    </div>
  {:else if lines.length === 0}
    <div class="card">
      <p>{copy(lang, "logsEmpty")}</p>
      <button type="button" class="btn btn-secondary mt-3" onclick={() => { query = ""; void load(); }}>{copy(lang, "showDay")}</button>
    </div>
  {:else}
    {#if errorCount > 0}
      <p class="mb-3 text-sm text-crit">{errorCount} {copy(lang, "errorsHour")}
        <button type="button" class="btn btn-ghost" onclick={() => (level = "error")}>{copy(lang, "showErrors")}</button>
      </p>
    {/if}
    <div class="card max-h-[60vh] overflow-auto p-3 font-mono text-xs">
      {#each visible as line, index (`${index}:${line.slice(0, 24)}`)}
        <p class="border-b border-smoke/40 py-1 break-words {/error|crit/i.test(line) ? 'text-crit' : /warn/i.test(line) ? 'text-warn' : ''}">
          <button type="button" class="mr-2 text-fog" onclick={() => void navigator.clipboard.writeText(line)}>{copy(lang, "copyPath")}</button>
          {line}
        </p>
      {/each}
    </div>
  {/if}
</section>
