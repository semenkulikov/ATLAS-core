<script lang="ts">
  import { api, ApiError, errorDetail, shownError, type Entity } from "./api";
  import { copy, fieldLabel, type Lang } from "./i18n";
  import Accordion from "./ui/Accordion.svelte";
  import ErrorModal from "./ui/ErrorModal.svelte";

  let { lang, canScan = false }: { lang: Lang; canScan?: boolean } = $props();
  let host = $state<Entity[]>([]);
  let sources = $state<Array<Record<string, string>>>([]);
  let projects = $state<Entity[]>([]);
  let message = $state("");
  let missing = $state(false);
  let busy = $state(false);
  let errorMessage = $state("");
  let errorExtra = $state("");
  let sourcesOpen = $state(false);

  const primaryKeys = [
    "hostname",
    "os.pretty_name",
    "pretty_name",
    "kernel.release",
    "arch",
    "uptime_seconds",
    "virt",
  ];

  async function load(): Promise<void> {
    message = "";
    missing = false;
    try {
      const [passport, listed] = await Promise.all([
        api<{ entities: Entity[]; sources: Array<Record<string, string>> }>("/api/v1/host"),
        api<{ items: Entity[] }>("/api/v1/projects"),
      ]);
      host = passport.entities;
      sources = passport.sources;
      projects = listed.items;
    } catch (error: unknown) {
      host = [];
      sources = [];
      projects = [];
      missing = error instanceof ApiError && error.code === "scan.missing";
      if (missing) {
        message = shownError(error, lang);
      } else {
        errorMessage = shownError(error, lang);
        errorExtra = errorDetail(error);
      }
    }
  }

  async function runScan(): Promise<void> {
    busy = true;
    message = "";
    try {
      await api("/api/v1/scans", { method: "POST", body: "{}" });
      message = copy(lang, "scanDone");
      await load();
    } catch (error: unknown) {
      errorMessage = shownError(error, lang);
      errorExtra = errorDetail(error);
    } finally {
      busy = false;
    }
  }

  $effect(() => {
    void load();
  });

  const identity = $derived(host.find((item) => item.key === "host")?.payload ?? {});
  const primaryEntries = $derived(
    Object.entries(identity).filter(([key]) => primaryKeys.includes(key)),
  );
  const otherEntries = $derived(
    Object.entries(identity).filter(([key]) => !primaryKeys.includes(key)),
  );
</script>

<section class="atlas-fade-in">
  <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-2xl text-paper">{copy(lang, "overview")}</h1>
    {#if canScan}
      <button
        type="button"
        class="rounded-md bg-accent px-3 py-1.5 text-sm text-void disabled:opacity-50"
        disabled={busy}
        onclick={() => void runScan()}
      >
        {busy ? copy(lang, "scanning") : copy(lang, "runScan")}
      </button>
    {/if}
  </div>

  {#if message}
    <p class="mb-4 text-sm text-fog" role="status">{message}</p>
  {/if}

  {#if missing}
    <div class="mb-6 rounded-xl border border-graphite bg-carbon p-5">
      <p class="text-paper">{copy(lang, "noScan")}</p>
      <p class="mt-2 text-sm text-fog">{copy(lang, "noScanHint")}</p>
      {#if canScan}
        <button
          type="button"
          class="mt-4 rounded-md bg-accent px-3 py-2 text-sm text-void disabled:opacity-50"
          disabled={busy}
          onclick={() => void runScan()}
        >
          {busy ? copy(lang, "scanning") : copy(lang, "runScan")}
        </button>
      {/if}
    </div>
  {:else}
    <h2 class="mb-2 text-sm text-mist">{copy(lang, "hostIdentity")}</h2>
    <div class="mb-4 grid gap-3 md:grid-cols-3">
      {#each primaryEntries as [key, value] (key)}
        <article class="rounded-xl border border-graphite bg-carbon p-4">
          <p class="text-xs text-ash">{fieldLabel(lang, key)}</p>
          <p class="mt-2 text-paper">{value}</p>
        </article>
      {/each}
    </div>
    {#if otherEntries.length > 0}
      <Accordion title={copy(lang, "technical")} count={otherEntries.length}>
        <div class="grid gap-2 p-2 md:grid-cols-2">
          {#each otherEntries as [key, value] (key)}
            <p class="text-xs">
              <span class="font-mono text-ash">{key}</span>
              <span class="ml-1 text-mist">{value}</span>
            </p>
          {/each}
        </div>
      </Accordion>
    {/if}
    <h2 class="mb-2 mt-6 text-paper">{copy(lang, "projects")}</h2>
    <ul class="mb-6 divide-y divide-graphite rounded-xl border border-graphite">
      {#each projects as project (project.key)}
        <li class="px-4 py-3">
          <a class="text-paper" href="#/projects">{project.payload.name ?? project.key}</a>
          <p class="font-mono text-xs text-fog">{project.payload.root_path}</p>
        </li>
      {:else}
        <li class="px-4 py-3 text-fog">{copy(lang, "empty")}</li>
      {/each}
    </ul>
    <Accordion title={copy(lang, "sources")} count={sources.length} bind:open={sourcesOpen}>
      <ul class="px-2 text-sm text-fog">
        {#each sources as source (`${source.collector}:${source.target}`)}
          <li class="flex justify-between border-t border-graphite py-1.5">
            <span class="font-mono text-xs">{source.target}</span>
            <span class={source.status === "ok" ? "text-ok" : "text-warn"}>{source.status}</span>
          </li>
        {/each}
      </ul>
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
