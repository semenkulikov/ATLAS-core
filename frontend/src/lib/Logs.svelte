<script lang="ts">
  import { api } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let source = $state("opt/shop/README.md");
  let lines = $state<string[]>([]);
  let message = $state("");

  async function load(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    message = "";
    try {
      const form = new FormData(event.target as HTMLFormElement);
      const query = String(form.get("q") ?? "");
      const pattern = String(form.get("pattern") ?? "");
      const params = new URLSearchParams({ source, q: query, pattern });
      const payload = await api<{ lines: string[] }>(`/api/v1/logs?${params.toString()}`);
      lines = payload.lines;
    } catch (error) {
      lines = [];
      message = error instanceof Error ? error.message : copy(lang, "error");
    }
  }
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "logs")}</h1>
  <form class="mb-4 flex gap-2" onsubmit={load}>
    <label class="flex-1 text-sm text-fog">
      {copy(lang, "source")}
      <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" name="source" bind:value={source} />
    </label>
    <label class="w-40 text-sm text-fog">
      {copy(lang, "filter")}
      <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" name="q" />
    </label>
    <label class="w-40 text-sm text-fog">
      {copy(lang, "pattern")}
      <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" name="pattern" />
    </label>
    <button class="self-end rounded-md bg-accent px-3 py-2 text-void" type="submit">{copy(lang, "show")}</button>
  </form>
  {#if message}
    <p class="mb-3 text-sm text-warn" role="alert">{message}</p>
  {/if}
  <pre class="overflow-auto rounded-xl border border-graphite bg-carbon p-3 font-mono text-xs text-mist">{lines.join("\n")}</pre>
</section>
