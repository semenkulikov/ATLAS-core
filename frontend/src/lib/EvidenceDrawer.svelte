<script lang="ts">
  import { copy, type Lang } from "./i18n";
  import type { Evidence } from "./api";
  import { api } from "./api";

  let { factId, lang, onclose }: { factId: number; lang: Lang; onclose: () => void } = $props();
  let rows = $state<Evidence[]>([]);
  let message = $state("");

  $effect(() => {
    const id = factId;
    rows = [];
    message = "";
    void api<{ evidence: Evidence[] }>(`/api/v1/facts/${id}/evidence`)
      .then((payload) => {
        rows = payload.evidence;
      })
      .catch((error: unknown) => {
        message = error instanceof Error ? error.message : copy(lang, "error");
      });
  });
</script>

<aside class="fixed inset-y-0 right-0 z-20 w-[360px] overflow-auto border-l border-graphite bg-carbon p-4" aria-label={copy(lang, "evidence")}>
  <div class="mb-4 flex items-center justify-between">
    <h2 class="text-paper">{copy(lang, "evidence")}</h2>
    <button type="button" class="text-sm text-fog" onclick={onclose}>{copy(lang, "close")}</button>
  </div>
  {#if message}
    <p class="text-sm text-crit" role="alert">{message}</p>
  {/if}
  {#each rows as row (row.id)}
    <article class="mb-3 rounded-xl border border-graphite p-3">
      <p class="text-xs uppercase tracking-wide text-ash">{row.kind}</p>
      <p class="mt-1 font-mono text-xs text-info">{row.ref}</p>
      <pre class="mt-2 whitespace-pre-wrap font-mono text-xs text-mist">{row.excerpt}</pre>
    </article>
  {/each}
</aside>
