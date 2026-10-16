<script lang="ts">
  import ActionDialog from "./ActionDialog.svelte";
  import Facts from "./Facts.svelte";
  import { api, errorDetail, shownError, type Entity, type Fact } from "./api";
  import { classifyEntity, kindFromPath } from "./classify";
  import { copy, fieldLabel, type Lang } from "./i18n";
  import Accordion from "./ui/Accordion.svelte";
  import ErrorModal from "./ui/ErrorModal.svelte";

  let {
    lang,
    path,
    detail,
    onopen,
    canAct = false,
  }: {
    lang: Lang;
    path: string;
    detail: string | null;
    onopen: (id: number) => void;
    canAct?: boolean;
  } = $props();
  let items = $state<Entity[]>([]);
  let next = $state<string | null>(null);
  let selected = $state<Entity | null>(null);
  let facts = $state<Fact[]>([]);
  let sshForUser = $state<Entity[]>([]);
  let techOpen = $state(false);
  let pendingOp = $state<string | null>(null);
  let errorMessage = $state("");
  let errorExtra = $state("");
  let systemOpen = $state(false);

  const kind = $derived(kindFromPath(path));

  const privileged = $derived(items.filter((item) => classifyEntity(kind, item) === "privileged"));
  const working = $derived(items.filter((item) => classifyEntity(kind, item) === "working"));
  const system = $derived(items.filter((item) => classifyEntity(kind, item) === "system"));

  async function load(cursor = ""): Promise<void> {
    const suffix = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    const payload = await api<{ items: Entity[]; next: string | null }>(`${path}${suffix}`);
    items = cursor ? [...items, ...payload.items] : payload.items;
    next = payload.next;
  }

  $effect(() => {
    items = [];
    selected = null;
    facts = [];
    sshForUser = [];
    void load().catch((error: unknown) => {
      errorMessage = shownError(error, lang);
      errorExtra = errorDetail(error);
    });
  });

  async function choose(item: Entity): Promise<void> {
    selected = item;
    techOpen = false;
    facts = [];
    sshForUser = [];
    if (!detail) return;
    try {
      const payload = await api<{ facts: Fact[] }>(`${detail}/${encodeURIComponent(item.key)}`);
      facts = payload.facts;
    } catch (error: unknown) {
      errorMessage = shownError(error, lang);
      errorExtra = errorDetail(error);
    }
    if (kind === "user") {
      try {
        const keys = await api<{ items: Entity[] }>("/api/v1/ssh-keys?limit=200");
        sshForUser = keys.items.filter((row) => row.payload.user === item.key);
      } catch {
        sshForUser = [];
      }
    }
  }

  function summarize(item: Entity): string {
    const payload = item.payload;
    if (typeof payload.exposed === "boolean") {
      return payload.exposed ? copy(lang, "exposed") : copy(lang, "local");
    }
    if (typeof payload.active === "string") return payload.active;
    if (typeof payload["unit.active"] === "string") return String(payload["unit.active"]);
    if (typeof payload.name === "string" && payload.name !== item.key) return payload.name;
    if (typeof payload.shell === "string") return payload.shell;
    if (typeof payload.uid === "number" || typeof payload.uid === "string") {
      return `uid ${payload.uid}`;
    }
    return "";
  }

  function show(value: unknown): string {
    if (value === null || value === undefined) return "";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
    if (typeof value === "object" && value !== null) {
      const row = value as { summary_en?: unknown; summary_ru?: unknown };
      if (lang === "ru" && typeof row.summary_ru === "string") return row.summary_ru;
      if (typeof row.summary_en === "string") return row.summary_en;
    }
    return JSON.stringify(value);
  }

  const summaryKeys = new Set([
    "name",
    "uid",
    "shell",
    "home",
    "groups",
    "sudo",
    "active",
    "unit.active",
    "enabled",
    "unit.enabled",
    "description",
    "unit.description",
    "exposed",
    "process",
    "user",
  ]);

  function isSummaryKey(key: string): boolean {
    return summaryKeys.has(key);
  }
</script>

<section>
  <div class="grid gap-4 lg:grid-cols-[1fr_340px]">
    <div>
      {#if privileged.length > 0}
        <p class="mb-2 text-xs uppercase tracking-wide text-ash">{copy(lang, "privilegedSection")}</p>
        <table class="mb-4 w-full border-collapse text-left text-sm">
          <tbody>
            {#each privileged as item (item.key)}
              <tr class="border-t border-graphite">
                <td>
                  <button
                    type="button"
                    class="w-full px-2 py-2 text-left font-mono text-xs {selected?.key === item.key
                      ? 'text-accent'
                      : 'text-paper'}"
                    onclick={() => void choose(item)}
                  >
                    {item.key}
                  </button>
                </td>
                <td class="px-2 text-fog">{summarize(item)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}

      {#if working.length > 0 || (privileged.length === 0 && system.length === 0)}
        <p class="mb-2 text-xs uppercase tracking-wide text-ash">{copy(lang, "workingSection")}</p>
        <table class="w-full border-collapse text-left text-sm">
          <tbody>
            {#each working as item (item.key)}
              <tr class="border-t border-graphite">
                <td>
                  <button
                    type="button"
                    class="w-full px-2 py-2 text-left font-mono text-xs {selected?.key === item.key
                      ? 'text-accent'
                      : 'text-paper'}"
                    onclick={() => void choose(item)}
                  >
                    {item.key}
                  </button>
                </td>
                <td class="px-2 text-fog">{summarize(item)}</td>
              </tr>
            {:else}
              <tr><td class="py-3 text-fog">{copy(lang, "empty")}</td></tr>
            {/each}
          </tbody>
        </table>
      {/if}

      {#if system.length > 0}
        <Accordion title={copy(lang, "systemSection")} count={system.length} bind:open={systemOpen}>
          <table class="w-full border-collapse text-left text-sm">
            <tbody>
              {#each system as item (item.key)}
                <tr class="border-t border-graphite">
                  <td>
                    <button
                      type="button"
                      class="w-full px-2 py-2 text-left font-mono text-xs {selected?.key === item.key
                        ? 'text-accent'
                        : 'text-fog'}"
                      onclick={() => void choose(item)}
                    >
                      {item.key}
                    </button>
                  </td>
                  <td class="px-2 text-ash">{summarize(item)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </Accordion>
      {/if}

      {#if next}
        <button type="button" class="mt-3 text-sm text-fog" onclick={() => void load(next ?? "")}>
          {copy(lang, "loadMore")}
        </button>
      {/if}
    </div>

    {#if selected}
      <aside class="atlas-fade-in rounded-xl border border-graphite bg-carbon p-3">
        <h2 class="mb-3 font-mono text-sm text-paper">{selected.key}</h2>
        <p class="mb-2 text-xs uppercase tracking-wide text-ash">{copy(lang, "summary")}</p>
        {#each Object.entries(selected.payload).filter(([key]) => isSummaryKey(key)) as [key, value] (key)}
          <p class="mb-1 text-xs">
            <span class="text-ash">{fieldLabel(lang, key)}</span>
            <span class="ml-1 text-mist">{show(value)}</span>
          </p>
        {/each}
        {#if kind === "user" && sshForUser.length > 0}
          <p class="mb-1 mt-3 text-xs uppercase tracking-wide text-ash">{copy(lang, "sshKeys")}</p>
          {#each sshForUser as key (key.key)}
            <p class="mb-1 font-mono text-xs text-fog">
              {String(key.payload.type ?? "")} · {key.key.slice(0, 24)}…
            </p>
          {/each}
        {/if}
        <Facts {facts} {lang} {onopen} />
        <details class="mt-3" bind:open={techOpen}>
          <summary class="cursor-pointer text-xs text-fog">{copy(lang, "technical")}</summary>
          <div class="mt-2">
            {#each Object.entries(selected.payload).filter(([key]) => !isSummaryKey(key)) as [key, value] (key)}
              <p class="mb-1 text-xs">
                <span class="font-mono text-ash">{key}</span>
                <span class="ml-1 text-mist">{show(value)}</span>
              </p>
            {/each}
          </div>
        </details>
        {#if canAct && path.endsWith("/services")}
          <button type="button" class="mt-3 text-sm text-info" onclick={() => (pendingOp = "service.restart")}>
            {copy(lang, "restart")}
          </button>
        {/if}
        {#if canAct && path.endsWith("/containers")}
          <button type="button" class="mt-3 text-sm text-info" onclick={() => (pendingOp = "container.restart")}>
            {copy(lang, "restart")}
          </button>
        {/if}
      </aside>
    {/if}
  </div>

  {#if pendingOp && selected}
    <ActionDialog
      {lang}
      op={pendingOp}
      objectName={selected.key}
      risk="medium"
      onclose={() => (pendingOp = null)}
    />
  {/if}

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
</section>
