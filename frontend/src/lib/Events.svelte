<script lang="ts">
  import { onMount } from "svelte";
  import { api, shownError } from "./api";
  import { formatWhen } from "./format";
  import { copy, type Lang } from "./i18n";
  import { changedFields, eventMatchesApp, eventTitle, type ChangeRow } from "./events";
  import { loadPanel } from "./inventory";
  import { selectedApp } from "./selection";
  import type { AppModel } from "./apps";

  type Audit = { id: number; ts: string; actor: string; action: string; result: string };

  let { lang }: { lang: Lang } = $props();
  let changes = $state<ChangeRow[]>([]);
  let apps = $state<AppModel[]>([]);
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
    const server = changes.map((row) => {
      const titled = eventTitle(lang, row);
      return {
        id: `${row.entity_kind}:${row.entity_key}:${row.change_kind}`,
        origin: "server" as const,
        text: titled.title,
        idLine: titled.idLine,
        fields: changedFields(row),
        when: since ?? "",
        app: row,
      };
    });
    const panel = audit.map((row) => ({
      id: String(row.id),
      origin: "panel" as const,
      text: `${row.actor} · ${row.action}`,
      idLine: "",
      fields: [] as { key: string; before: string; after: string }[],
      when: row.ts,
      app: null,
    }));
    const chosen = apps.find((item) => item.id === appFilter);
    return [...server, ...panel].filter((row) => {
      if (mode === "server" && row.origin !== "server") return false;
      if (mode === "panel" && row.origin !== "panel") return false;
      if (appFilter && row.origin === "server" && row.app && !eventMatchesApp(row.app, chosen ?? { containers: [], services: [], ports: [] })) return false;
      return true;
    });
  });

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
        apps = body.apps;
      })
      .catch(() => undefined);
    void api<{ changes: ChangeRow[] }>("/api/v1/changes")
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
            <span>
              <span class="text-paper">{row.text}</span>
              {#if row.idLine}<span class="mono block text-fog">{row.idLine}</span>{/if}
            </span>
            <span class="kicker">{row.origin === "server" ? copy(lang, "onHost") : copy(lang, "inPanel")} · {formatWhen(row.when, lang) || copy(lang, "detectedAt")}</span>
          </button>
          {#if open === row.id}
            {#if row.fields.length > 0}
              <ul class="mb-3 space-y-1">
                {#each row.fields as field (`${field.key}`)}
                  <li class="text-sm text-fog">{field.key}: {field.before || "—"} → {field.after || "—"}</li>
                {/each}
              </ul>
            {:else}
              <p class="kicker mb-3">{copy(lang, "wasBecame")}</p>
            {/if}
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>
