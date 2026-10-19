<script lang="ts">
  import { onMount } from "svelte";
  import { api, shownError } from "./api";
  import { formatWhen } from "./format";
  import { copy, type CopyKey, type Lang } from "./i18n";
  import { loadPanel } from "./inventory";
  import { selectedApp } from "./selection";

  type Change = {
    entity_kind: string;
    entity_key: string;
    change_kind: string;
    before_json: string | null;
    after_json: string | null;
  };
  type Audit = { id: number; ts: string; actor: string; action: string; result: string };

  let { lang }: { lang: Lang } = $props();
  let changes = $state<Change[]>([]);
  let audit = $state<Audit[]>([]);
  let intact = $state(true);
  let since = $state<string | null>(null);
  let errorMessage = $state("");
  let mode = $state<"all" | "server" | "panel">("all");
  let open = $state("");
  let appFilter = $state("");

  selectedApp.subscribe((id) => {
    appFilter = id;
  });

  const rows = $derived.by(() => {
    const server = changes.map((row) => ({
      id: `${row.entity_kind}:${row.entity_key}:${row.change_kind}`,
      origin: "server" as const,
      text: `${label(row.change_kind)} · ${row.entity_key}`,
      when: since ?? "",
      before: row.before_json,
      after: row.after_json,
      app: row.entity_key,
    }));
    const panel = audit.map((row) => ({
      id: String(row.id),
      origin: "panel" as const,
      text: `${row.actor} · ${row.action}`,
      when: row.ts,
      before: null as string | null,
      after: row.result,
      app: "",
    }));
    return [...server, ...panel].filter((row) => {
      if (mode === "server" && row.origin !== "server") return false;
      if (mode === "panel" && row.origin !== "panel") return false;
      if (appFilter && row.origin === "server" && !row.app.includes(appFilter)) return false;
      return true;
    });
  });

  function label(kind: string): string {
    const map: Record<string, CopyKey> = {
      added: "changeAddedPhrase",
      removed: "changeRemovedPhrase",
      changed: "changeChangedPhrase",
      modified: "changeChangedPhrase",
    };
    const key = map[kind];
    return key ? copy(lang, key) : kind;
  }

  function download(): void {
    const header = "origin,text,when\n";
    const body = rows.map((row) => `${row.origin},"${row.text.replaceAll('"', "'")}",${row.when}`).join("\n");
    const blob = new Blob([header + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "atlas-events.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  onMount(() => {
    void loadPanel()
      .then((body) => {
        since = body.collectedAt;
      })
      .catch(() => undefined);
    void api<{ changes: Change[] }>("/api/v1/changes")
      .then((body) => {
        changes = body.changes;
      })
      .catch((error: unknown) => {
        errorMessage = shownError(error, lang);
      });
    void api<{ items: Audit[]; intact: boolean }>("/api/v1/audit")
      .then((body) => {
        audit = body.items;
        intact = body.intact;
      })
      .catch(() => undefined);
  });
</script>

<section class="atlas-fade-in">
  <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
    <h1 class="screen-title">{copy(lang, "events")}</h1>
    <button type="button" class="btn btn-secondary" onclick={download}>{copy(lang, "exportCsv")}</button>
  </div>
  {#if !intact}
    <p class="card mb-4 text-crit" role="alert">{copy(lang, "journalBad")}</p>
  {:else}
    <p class="kicker mb-4">{copy(lang, "journalOk")} ✓</p>
  {/if}
  <div class="seg mb-4">
    <button type="button" class="btn btn-ghost" aria-pressed={mode === "all"} onclick={() => (mode = "all")}>{copy(lang, "allEvents")}</button>
    <button type="button" class="btn btn-ghost" aria-pressed={mode === "server"} onclick={() => (mode = "server")}>{copy(lang, "onHost")}</button>
    <button type="button" class="btn btn-ghost" aria-pressed={mode === "panel"} onclick={() => (mode = "panel")}>{copy(lang, "inPanel")}</button>
  </div>
  {#if errorMessage}
    <p class="text-sm text-fog">{errorMessage}</p>
  {:else if rows.length === 0}
    <div class="card max-w-xl">
      <p class="text-paper">{copy(lang, "eventsEmpty")}</p>
      {#if since}<p class="mt-2 text-sm text-fog">{copy(lang, "eventsSince")} {formatWhen(since, lang)}</p>{/if}
    </div>
  {:else}
    <ul class="card divide-y divide-smoke">
      {#each rows as row (row.id)}
        <li>
          <button type="button" class="flex w-full flex-wrap items-baseline justify-between gap-2 py-3 text-left" onclick={() => (open = open === row.id ? "" : row.id)}>
            <span class="text-paper">{row.text}</span>
            <span class="kicker">{row.origin === "server" ? copy(lang, "onHost") : copy(lang, "inPanel")} · {formatWhen(row.when, lang) || copy(lang, "detectedAt")}</span>
          </button>
          {#if open === row.id}
            <p class="kicker mb-3">{copy(lang, "wasBecame")}</p>
            <pre class="mono mb-3 whitespace-pre-wrap text-fog">{row.before ?? "—"} → {row.after ?? "—"}</pre>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>
