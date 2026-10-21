<script lang="ts">
  import { onMount } from "svelte";
  import ActionDialog from "./ActionDialog.svelte";
  import { portList, requestChains, statusLabel, statusTone, type AppModel } from "./apps";
  import { api, shownError, type Fact } from "./api";
  import { changedFields, eventMatchesApp, eventTitle, type ChangeRow } from "./events";
  import { formatCount, readmeLead, textOf } from "./format";
  import { renderMarkdown } from "./markdown";
  import { copy, type Lang } from "./i18n";
  import { loadPanel, readManual, writeManual, type PanelData } from "./inventory";
  import { selectedApp } from "./selection";
  import CopyButton from "./ui/CopyButton.svelte";
  import Mark from "./ui/Mark.svelte";
  import MiniBar from "./ui/MiniBar.svelte";
  import StatusDot from "./ui/StatusDot.svelte";

  let { lang, appId = "", tab = "summary", role = "viewer" }: { lang: Lang; appId?: string; tab?: string; role?: string } = $props();
  let data = $state<PanelData | null>(null);
  let technical = $state(false);
  let errorMessage = $state("");
  let query = $state("");
  let status = $state("all");
  let stack = $state("all");
  let view = $state(localStorage.getItem("atlas.apps.view") === "table" ? "table" : "cards");
  let docs = $state<Array<Record<string, unknown>>>([]);
  let facts = $state<Fact[]>([]);
  let openMenu = $state("");
  let changes = $state<ChangeRow[]>([]);
  let pending = $state<{ op: string; name: string; risk: "medium" | "high" | "critical" } | null>(null);
  let rename = $state("");

  const app = $derived(data?.apps.find((item) => item.id === appId) ?? null);
  const recent = $derived.by(() => {
    if (!app) return [];
    return changes
      .filter((row) => eventMatchesApp(row, app))
      .slice(0, 5)
      .map((row) => ({ row, title: eventTitle(lang, row), fields: changedFields(row).slice(0, 3) }));
  });
  const stacks = $derived([...(data ? new Set(data.apps.flatMap((item) => item.stack)) : [])]);
  const visible = $derived(
    (data?.apps ?? []).filter((item) => {
      if (query && !item.name.toLowerCase().includes(query.toLowerCase())) return false;
      if (status === "running" && item.status !== "running") return false;
      if (status === "problems" && item.status === "running") return false;
      if (stack !== "all" && !item.stack.includes(stack)) return false;
      return true;
    }),
  );

  const tabs = ["summary", "running", "network", "docs", "deps", "sources"] as const;
  const tabKey = {
    summary: "tabSummary",
    running: "tabRunning",
    network: "tabNetwork",
    docs: "tabDocs",
    deps: "tabDeps",
    sources: "tabSources",
  } as const;

  async function load(): Promise<void> {
    try {
      const [panel, history] = await Promise.all([
        loadPanel(),
        api<{ changes: ChangeRow[] }>("/api/v1/changes").catch(() => ({ changes: [] as ChangeRow[] })),
      ]);
      data = panel;
      changes = history.changes;
      errorMessage = "";
    } catch (error) {
      errorMessage = shownError(error, lang);
    }
  }

  onMount(() => {
    technical = localStorage.getItem("atlas.raw") === "1";
    void load();
  });

  $effect(() => {
    if (!openMenu) return;
    const onPointer = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest("[data-row-menu]")) return;
      openMenu = "";
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") openMenu = "";
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  });

  function openLogs(): void {
    if (app) selectedApp.set(app.id);
    location.hash = "#/logs";
  }

  $effect(() => {
    const current = app;
    if (!current) {
      docs = [];
      facts = [];
      return;
    }
    rename = current.name;
    const first = current.dirs[0];
    if (!first) return;
    void api<{ docs: Array<Record<string, unknown>> }>(`/api/v1/projects/${first.id}/docs`).then((body) => {
      docs = body.docs;
    }).catch(() => {
      docs = [];
    });
    void api<{ facts: Fact[] }>(`/api/v1/projects/${first.id}`).then((body) => {
      facts = body.facts;
    }).catch(() => {
      facts = [];
    });
  });

  function setView(next: "cards" | "table"): void {
    view = next;
    localStorage.setItem("atlas.apps.view", next);
  }

  function saveName(item: AppModel): void {
    const manual = readManual();
    manual.renames[item.id] = rename.trim() || item.name;
    writeManual(manual);
    void load();
  }

  function toggleAlone(dirId: string): void {
    const manual = readManual();
    manual.alone = manual.alone.includes(dirId) ? manual.alone.filter((id) => id !== dirId) : [...manual.alone, dirId];
    writeManual(manual);
    void load();
  }

  const readme = $derived(docs.find((doc) => String(doc.path).toLowerCase().includes("readme")));
  const readmeText = $derived(typeof readme?.body === "string" ? readmeLead(readme.body) : "");
  const sourceFacts = $derived(
    facts.filter(
      (fact) =>
        technical ||
        (!fact.predicate.startsWith("dependency.") && !fact.predicate.startsWith("stack.")),
    ),
  );
  const chains = $derived(app && data ? requestChains(app, data.sites) : []);
  const runtimeFacts = $derived(facts.filter((fact) => /python|node|django|redis|postgres|version|framework/i.test(`${fact.predicate} ${fact.value}`)));
  const canAct = $derived(role !== "viewer");
</script>

<section class="atlas-fade-in">
  {#if errorMessage && !data}
    <div class="card">
      <p>{errorMessage}</p>
      <button type="button" class="btn btn-secondary mt-3" onclick={() => void load()}>{copy(lang, "retry")}</button>
    </div>
  {:else if !app}
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <h1 class="screen-title">{copy(lang, "apps")}</h1>
      <div class="seg">
        <button type="button" class="btn btn-ghost" aria-pressed={view === "cards"} onclick={() => setView("cards")}>{copy(lang, "cards")}</button>
        <button type="button" class="btn btn-ghost" aria-pressed={view === "table"} onclick={() => setView("table")}>{copy(lang, "tableView")}</button>
      </div>
    </div>
    <div class="mb-4 flex flex-wrap gap-2">
      <input class="h-8 rounded-md border border-smoke bg-void px-3 text-sm" placeholder={copy(lang, "searchName")} bind:value={query} />
      <select class="h-8 rounded-md border border-smoke bg-void px-2 text-sm" bind:value={status}>
        <option value="all">{copy(lang, "statusAll")}</option>
        <option value="running">{copy(lang, "worksFilter")}</option>
        <option value="problems">{copy(lang, "problems")}</option>
      </select>
      <select class="h-8 rounded-md border border-smoke bg-void px-2 text-sm" bind:value={stack}>
        <option value="all">{copy(lang, "allStacks")}</option>
        {#each stacks as name (name)}
          <option value={name}>{name}</option>
        {/each}
      </select>
    </div>
    {#if view === "cards"}
      <div class="grid gap-4 md:grid-cols-2">
        {#each visible as item (item.id)}
          <a class="card lift grid gap-3" href={`#/apps/${item.id}/summary`}>
            <div class="flex items-center justify-between">
              <p class="text-paper">{item.name}</p>
              <StatusDot kind={statusTone(item.status)} label={statusLabel(item.status, lang)} />
            </div>
            <div class="flex flex-wrap gap-2">
              {#each item.stack.slice(0, 4) as name (name)}<span class="chip">{name}</span>{/each}
              {#each item.envs as env (env)}<span class="chip">{env}</span>{/each}
            </div>
            <MiniBar label="CPU" text="—" percent={null} />
            <MiniBar label={copy(lang, "memory")} text="—" percent={null} />
            <p class="kicker">{formatCount(lang, item.containers.length, "container")} · {copy(lang, "portsWord")} {portList(item.ports).join(", ") || "—"}</p>
          </a>
        {:else}
          <p class="text-sm text-fog">{data ? copy(lang, "noMatch") : copy(lang, "skeleton")}</p>
        {/each}
      </div>
    {:else}
      <div class="card overflow-auto p-0">
        <table class="data-table">
          <thead>
            <tr>
              <th>{copy(lang, "apps")}</th>
              <th>{copy(lang, "statusDot")}</th>
              <th>{copy(lang, "stackFilter")}</th>
              <th>{copy(lang, "portsWord")}</th>
            </tr>
          </thead>
          <tbody>
            {#each visible as item (item.id)}
              <tr class="clickable" onclick={() => (location.hash = `#/apps/${item.id}/summary`)}>
                <td class="text-paper">{item.name}</td>
                <td>{statusLabel(item.status, lang)}</td>
                <td>{item.stack.slice(0, 3).join(", ")}</td>
                <td class="mono">{portList(item.ports).join(", ")}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
    {#if data}
      <p class="mt-6">
        <a class="text-sm text-info" href="#/system/services">{copy(lang, "notInAnyApp")} ({data.system.services.length + data.system.containers.length})</a>
      </p>
    {/if}
  {:else}
    <p class="kicker mb-2"><a href="#/apps">{copy(lang, "apps")}</a> · {app.name}</p>
    <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="screen-title">{app.name}</h1>
          <StatusDot kind={statusTone(app.status)} label={statusLabel(app.status, lang)} />
        </div>
        <div class="mt-2 flex flex-wrap gap-2">
          {#each app.stack.slice(0, 4) as name (name)}<span class="chip">{name}</span>{/each}
          {#each app.envs as env (env)}<span class="chip">{env}</span>{/each}
        </div>
        <p class="mt-2 flex flex-wrap items-center gap-2">
          <span class="kicker">{app.manual ? copy(lang, "configuredManually") : copy(lang, "groupedAuto")}</span>
          <Mark
            {lang}
            kind="derived"
            value={app.name}
            how={app.reason === "prefix" ? copy(lang, "prefixRule") : copy(lang, "singleRule")}
            at={data?.collectedAt ?? ""}
          />
        </p>
        {#if app.dirs[0]}
          <p class="mono mt-2 break-all text-fog">{app.dirs[0].path}</p>
          <CopyButton {lang} text={app.dirs[0].path} />
        {/if}
      </div>
      <div class="flex flex-wrap gap-2">
        <a class="btn btn-secondary" href="#/logs" onclick={openLogs}>{copy(lang, "logsLink")}</a>
        <button
          type="button"
          class="btn btn-danger"
          disabled={!canAct}
          title={canAct ? "" : copy(lang, "readOnlyHint")}
          onclick={() => (pending = { op: "service.restart", name: app.services[0]?.key ?? app.name, risk: "high" })}
        >
          {copy(lang, "restart")}
        </button>
      </div>
    </div>
    <div class="mb-4 flex gap-2 overflow-x-auto">
      {#each tabs as id (id)}
        <a class="chip whitespace-nowrap {tab === id ? 'text-paper' : ''}" href={`#/apps/${app.id}/${id}`} aria-current={tab === id ? "page" : undefined}>
          {copy(lang, tabKey[id])}
        </a>
      {/each}
    </div>

    {#if tab === "summary"}
      <div class="grid gap-4">
        <article class="card">
          <h2 class="block-title">{copy(lang, "whatIs")}</h2>
          {#if readmeText}
            <p class="mt-2 max-w-prose text-sm">{readmeText}</p>
            <p class="kicker mt-2">{copy(lang, "quoteReadme")} <Mark {lang} kind="fact" value={readmeText} how={String(readme?.path ?? "")} /></p>
          {:else}
            <p class="mt-2 text-sm text-fog">{copy(lang, "noReadme")} <Mark {lang} kind="unknown" value={copy(lang, "noReadme")} how={copy(lang, "noReadme")} /></p>
          {/if}
        </article>
        {#if chains.length > 0}
          <article class="card">
            <h2 class="block-title mb-3">{copy(lang, "chainTitle")}</h2>
            {#each chains as chain, index (`${index}`)}
              <div class="chain mb-3">
                {#each chain as hop, hopIndex (`${hop.kind}:${hop.label}`)}
                  {#if hopIndex > 0}<span class="text-fog">→</span>{/if}
                  <span class="chip">{hop.label}</span>
                {/each}
              </div>
            {/each}
          </article>
        {/if}
        <article class="card">
          <h2 class="block-title mb-3">{copy(lang, "recentEvents")}</h2>
          {#if recent.length === 0}
            <p class="text-sm text-fog">{copy(lang, "eventsEmpty")}</p>
          {:else}
            <ul>
              {#each recent as item (`${item.row.entity_kind}:${item.row.entity_key}:${item.row.change_kind}`)}
                <li class="py-2">
                  <p class="text-paper">{item.title.title}</p>
                  {#if item.title.idLine}<p class="mono text-fog">{item.title.idLine}</p>{/if}
                  {#each item.fields as field (`${field.key}`)}
                    <p class="text-sm text-fog">{field.key}: {field.before || "—"} → {field.after || "—"}</p>
                  {/each}
                </li>
              {/each}
            </ul>
          {/if}
          <a class="mt-2 inline-block text-sm text-info" href="#/events">{copy(lang, "events")}</a>
        </article>
        <article class="card">
          <h2 class="kicker">{copy(lang, "manualHint")}</h2>
          <form class="mt-3 flex flex-wrap gap-2" onsubmit={(event) => { event.preventDefault(); saveName(app); }}>
            <input class="h-8 rounded-md border border-smoke bg-void px-3" bind:value={rename} aria-label={copy(lang, "renameApp")} />
            <button class="btn btn-secondary" type="submit">{copy(lang, "renameApp")}</button>
          </form>
          <ul class="mt-3">
            {#each app.dirs as dir (dir.id)}
              <li class="flex flex-wrap items-center justify-between gap-2 py-1">
                <span class="mono text-fog">{dir.path}</span>
                <button type="button" class="btn btn-ghost" onclick={() => toggleAlone(dir.id)}>{copy(lang, "splitOff")}</button>
              </li>
            {/each}
          </ul>
        </article>
      </div>
    {:else if tab === "running"}
      {#each [{ title: "containersWord", rows: app.containers }, { title: "servicesWord", rows: app.services }, { title: "schedulesWord", rows: app.schedules }] as group (group.title)}
        <h2 class="block-title mb-2 mt-4">{copy(lang, group.title as "containersWord" | "servicesWord" | "schedulesWord")} ({group.rows.length})</h2>
        <div class="card overflow-auto p-0">
          <table class="data-table">
            <thead><tr><th>{copy(lang, "fieldName")}</th><th>{copy(lang, "doesWhat")}</th><th>{copy(lang, "stateLabel")}</th></tr></thead>
            <tbody>
              {#each group.rows as row (row.key)}
                <tr>
                  <td class="mono text-paper">{textOf(row.payload.name) || row.key}</td>
                  <td>{textOf(row.payload.description) || textOf(row.payload.image) || copy(lang, "noDescription")}</td>
                  <td>{textOf(row.payload.state) || textOf(row.payload["unit.active"]) || textOf(row.payload.command)}</td>
                  <td class="relative" data-row-menu>
                    <button type="button" class="btn btn-ghost" onclick={() => (openMenu = openMenu === row.key ? "" : row.key)}>{copy(lang, "rowMenu")}</button>
                    {#if openMenu === row.key}
                      <div class="menu">
                        <button type="button" class="btn btn-ghost w-full justify-start" onclick={openLogs}>{copy(lang, "logsOf")}</button>
                        {#if canAct && group.title !== "schedulesWord"}
                          <button type="button" class="btn btn-ghost w-full justify-start" onclick={() => (pending = { op: group.title === "containersWord" ? "container.restart" : "service.restart", name: textOf(row.payload.name) || row.key, risk: "high" })}>{copy(lang, "restartOne")}</button>
                        {/if}
                        <CopyButton {lang} text={textOf(row.payload.id) || row.key} label={copy(lang, "copyId")} />
                      </div>
                    {/if}
                  </td>
                </tr>
              {:else}
                <tr><td colspan="3" class="text-fog">{copy(lang, "empty")}</td></tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/each}
    {:else if tab === "network"}
      <div class="card overflow-auto p-0">
        <table class="data-table">
          <thead><tr><th>{copy(lang, "portWord")}</th><th>{copy(lang, "whoListens")}</th><th>{copy(lang, "whoConnects")}</th></tr></thead>
          <tbody>
            {#each app.ports as row (row.key)}
              <tr>
                <td class="mono">{row.payload.port}</td>
                <td>{textOf((row.payload.process as { comm?: string } | null)?.comm) || copy(lang, "ownerUnknown")}</td>
                <td>{copy(lang, textOf(row.payload.address).startsWith("127.") ? "onlyServer" : "fromInternet")}</td>
              </tr>
            {:else}
              <tr><td colspan="3" class="text-fog">{copy(lang, "empty")}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if tab === "docs"}
      {#each docs as doc (`${doc.path}`)}
        <article class="card mb-3">
          <p class="mono text-info">{doc.path}</p>
          <div class="doc mt-2 max-h-96 overflow-auto text-sm">{@html renderMarkdown(String(doc.body ?? ""))}</div>
        </article>
      {:else}
        <p class="text-sm text-fog">{copy(lang, "docsEmpty")}</p>
      {/each}
    {:else if tab === "deps"}
      <ul class="card divide-y divide-smoke">
        {#each (runtimeFacts.length ? runtimeFacts : facts).slice(0, runtimeFacts.length ? 12 : 8) as fact (fact.id)}
          <li class="flex items-center justify-between gap-3 py-2">
            <span>{fact.value.toLowerCase().includes("not pinned") ? copy(lang, "unpinned") : fact.value}</span>
            <Mark {lang} kind={fact.certainty === "unknown" ? "unknown" : fact.certainty === "derived" ? "derived" : "fact"} value={fact.value} how={fact.rule ?? fact.predicate} at={fact.collected_at} />
          </li>
        {:else}
          <li class="text-fog">{copy(lang, "depsEmpty")}</li>
        {/each}
      </ul>
      {#if facts.length > 8}
        <details class="card mt-3">
          <summary class="cursor-pointer">{copy(lang, "allDependencies")} ({facts.length})</summary>
          <ul class="mt-2">
            {#each facts as fact (fact.id)}
              <li class="py-1 text-sm">{fact.value}</li>
            {/each}
          </ul>
        </details>
      {/if}
    {:else}
      <ul class="card">
        {#each sourceFacts as fact (fact.id)}
          <li class="flex items-center justify-between gap-2 border-b border-smoke py-2">
            <span class="mono text-fog">{fact.predicate}</span>
            <Mark {lang} kind={fact.certainty === "unknown" ? "unknown" : fact.certainty === "derived" ? "derived" : "fact"} value={fact.value} how={fact.rule ?? fact.subject} at={fact.collected_at} />
          </li>
        {:else}
          <li class="text-fog">{copy(lang, "sourcesEmpty")}</li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

{#if pending}
  <ActionDialog {lang} op={pending.op} objectName={pending.name} risk={pending.risk} note={copy(lang, "appRestartHint")} onclose={() => (pending = null)} />
{/if}
