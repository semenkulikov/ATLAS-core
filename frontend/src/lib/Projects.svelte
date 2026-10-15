<script lang="ts">
  import Facts from "./Facts.svelte";
  import { api, shownError, type Entity, type Fact } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang, onopen }: { lang: Lang; onopen: (id: number) => void } = $props();
  let items = $state<Entity[]>([]);
  let selected = $state<string>("");
  let facts = $state<Fact[]>([]);
  let docs = $state<Array<Record<string, unknown>>>([]);
  let query = $state("");
  let hits = $state<Array<Record<string, string>>>([]);
  let note = $state("");

  $effect(() => {
    void api<{ items: Entity[] }>("/api/v1/projects")
      .then((payload) => {
        items = payload.items;
        if (!selected && payload.items[0]) selected = payload.items[0].key;
      })
      .catch((error: unknown) => {
        note = shownError(error, lang);
      });
  });

  $effect(() => {
    if (!selected) return;
    const id = selected;
    void api<{ facts: Fact[] }>(`/api/v1/projects/${id}`).then((payload) => {
      facts = payload.facts;
    });
    void api<{ docs: Array<Record<string, unknown>> }>(`/api/v1/projects/${id}/docs`).then((payload) => {
      docs = payload.docs;
    });
  });

  async function search(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    note = "";
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    const field = form?.elements.namedItem("q");
    const typed = field instanceof HTMLInputElement ? field.value : query;
    try {
      const payload = await api<{ hits: Array<Record<string, string>> }>(
        `/api/v1/search?q=${encodeURIComponent(typed)}`,
      );
      hits = payload.hits;
    } catch (error) {
      hits = [];
      note = shownError(error, lang);
    }
  }
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "projects")}</h1>
  <div class="grid gap-4 lg:grid-cols-[240px_1fr]">
    <ul class="rounded-xl border border-graphite">
      {#each items as item (item.key)}
        <li>
          <button
            type="button"
            class="w-full px-3 py-2 text-left {selected === item.key ? 'text-accent' : 'text-mist'}"
            onclick={() => (selected = item.key)}
          >
            {item.payload.name ?? item.key}
            <span class="block font-mono text-xs text-fog">{item.payload.root_path}</span>
          </button>
        </li>
      {:else}
        <li class="px-3 py-2 text-fog">{copy(lang, "empty")}</li>
      {/each}
    </ul>
    <div>
      <Facts {facts} {lang} {onopen} />
      {#each docs as doc (`${doc.path}`)}
        <article class="mt-3 rounded-xl border border-graphite bg-carbon p-3">
          <p class="font-mono text-xs text-info">{doc.path}</p>
          <pre class="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-xs text-mist">{doc.body}</pre>
        </article>
      {/each}
      <form class="mt-4 flex gap-2" onsubmit={search}>
        <input
          name="q"
          class="flex-1 rounded-md border border-graphite bg-void px-3 py-2"
          placeholder={copy(lang, "search")}
          bind:value={query}
        />
        <button class="rounded-md bg-accent px-3 text-void" type="submit">{copy(lang, "search")}</button>
      </form>
      {#if note}
        <p class="mt-2 text-sm text-crit" role="alert">{note}</p>
      {/if}
      {#each hits as hit, index (`${hit.project_id}:${hit.path}:${index}`)}
        <p class="mt-2 font-mono text-xs text-fog">{hit.path} {hit.snippet}</p>
      {/each}
    </div>
  </div>
</section>
