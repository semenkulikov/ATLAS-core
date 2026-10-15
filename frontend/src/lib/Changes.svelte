<script lang="ts">
  import { api, shownError } from "./api";
  import { copy, type Lang } from "./i18n";

  type Change = {
    entity_kind: string;
    entity_key: string;
    change_kind: string;
    before_json: string | null;
    after_json: string | null;
  };

  let { lang }: { lang: Lang } = $props();
  let rows = $state<Change[]>([]);
  let message = $state("");

  $effect(() => {
    void api<{ changes: Change[] }>("/api/v1/changes")
      .then((payload) => {
        rows = payload.changes;
      })
      .catch((error: unknown) => {
        message = shownError(error, lang);
      });
  });
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "changes")}</h1>
  {#if message}
    <p class="text-sm text-warn" role="status">{message}</p>
  {/if}
  <ul class="divide-y divide-graphite rounded-xl border border-graphite">
    {#each rows as row (`${row.entity_kind}:${row.entity_key}:${row.change_kind}`)}
      <li class="px-4 py-3">
        <p class="text-paper">{row.change_kind} {row.entity_kind}</p>
        <p class="font-mono text-xs text-fog">{row.entity_key}</p>
      </li>
    {:else}
      <li class="px-4 py-3 text-fog">{copy(lang, "empty")}</li>
    {/each}
  </ul>
</section>
