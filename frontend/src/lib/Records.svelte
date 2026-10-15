<script lang="ts">
  import ActionDialog from "./ActionDialog.svelte";
  import Facts from "./Facts.svelte";
  import { api, shownError, type Entity, type Fact } from "./api";
  import { copy, type Lang } from "./i18n";

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
  let message = $state("");
  let pendingOp = $state<string | null>(null);

  async function load(cursor = ""): Promise<void> {
    const suffix = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    const payload = await api<{ items: Entity[]; next: string | null }>(`${path}${suffix}`);
    items = cursor ? [...items, ...payload.items] : payload.items;
    next = payload.next;
  }

  $effect(() => {
    items = [];
    selected = null;
    void load().catch((error: unknown) => {
      message = shownError(error, lang);
    });
  });

  async function choose(item: Entity): Promise<void> {
    selected = item;
    if (!detail) return;
    const payload = await api<{ facts: Fact[] }>(`${detail}/${encodeURIComponent(item.key)}`);
    facts = payload.facts;
  }

  function summarize(item: Entity): string {
    const payload = item.payload;
    if (typeof payload.exposed === "boolean") return payload.exposed ? "exposed" : "local";
    if (typeof payload.active === "string") return payload.active;
    if (typeof payload.name === "string") return payload.name;
    return "";
  }

  function show(value: unknown): string {
    if (value === null || value === undefined) return "";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
    if (typeof value === "object" && "summary_en" in value) {
      const summary = (value as { summary_en?: unknown }).summary_en;
      return typeof summary === "string" ? summary : JSON.stringify(value);
    }
    return JSON.stringify(value);
  }
</script>

<section>
  {#if message}
    <p class="mb-3 text-sm text-warn" role="status">{message}</p>
  {/if}
  <div class="grid gap-4 lg:grid-cols-[1fr_320px]">
    <table class="w-full border-collapse text-left text-sm">
      <tbody>
        {#each items as item (item.key)}
          <tr class="border-t border-graphite">
            <td>
              <button type="button" class="w-full px-2 py-2 text-left font-mono text-xs text-paper" onclick={() => choose(item)}>
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
    {#if selected}
      <aside class="rounded-xl border border-graphite bg-carbon p-3">
        <h2 class="mb-2 font-mono text-xs text-paper">{selected.key}</h2>
        {#each Object.entries(selected.payload) as [key, value] (key)}
          <p class="mb-1 text-xs"><span class="text-ash">{key}</span> <span class="text-mist">{show(value)}</span></p>
        {/each}
        <Facts {facts} {lang} {onopen} />
        {#if canAct && path.endsWith("/services")}
          <button type="button" class="mt-3 text-sm text-accent" onclick={() => (pendingOp = "service.restart")}>
            {copy(lang, "restart")}
          </button>
        {/if}
        {#if canAct && path.endsWith("/containers")}
          <button type="button" class="mt-3 text-sm text-accent" onclick={() => (pendingOp = "container.restart")}>
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
  {#if next}
    <button type="button" class="mt-3 text-sm text-fog" onclick={() => load(next ?? "")}>{copy(lang, "loadMore")}</button>
  {/if}
</section>
