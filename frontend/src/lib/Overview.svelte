<script lang="ts">
  import { api, type Entity } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let host = $state<Entity[]>([]);
  let sources = $state<Array<Record<string, string>>>([]);
  let projects = $state<Entity[]>([]);
  let message = $state("");

  $effect(() => {
    void Promise.all([
      api<{ entities: Entity[]; sources: Array<Record<string, string>> }>("/api/v1/host"),
      api<{ items: Entity[] }>("/api/v1/projects"),
    ])
      .then(([passport, listed]) => {
        host = passport.entities;
        sources = passport.sources;
        projects = listed.items;
      })
      .catch((error: unknown) => {
        message = error instanceof Error ? error.message : copy(lang, "error");
      });
  });

  const identity = $derived(host.find((item) => item.key === "host")?.payload ?? {});
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "overview")}</h1>
  {#if message}
    <p class="mb-4 text-sm text-warn" role="status">{message}</p>
  {/if}
  <div class="mb-4 grid gap-3 md:grid-cols-3">
    {#each Object.entries(identity) as [key, value] (key)}
      <article class="rounded-xl border border-graphite bg-carbon p-4">
        <p class="font-mono text-xs text-ash">{key}</p>
        <p class="mt-2 text-paper">{value}</p>
      </article>
    {/each}
  </div>
  <h2 class="mb-2 text-paper">{copy(lang, "projects")}</h2>
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
  <h2 class="mb-2 text-paper">Sources</h2>
  <ul class="text-sm text-fog">
    {#each sources as source (`${source.collector}:${source.target}`)}
      <li class="flex justify-between border-t border-graphite py-1">
        <span class="font-mono text-xs">{source.target}</span>
        <span class={source.status === "ok" ? "text-ok" : "text-warn"}>{source.status}</span>
      </li>
    {/each}
  </ul>
</section>
