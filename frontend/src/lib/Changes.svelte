<script lang="ts">
  import { api, errorDetail, shownError } from "./api";
  import { copy, type CopyKey, type Lang } from "./i18n";
  import ErrorModal from "./ui/ErrorModal.svelte";

  type Change = {
    entity_kind: string;
    entity_key: string;
    change_kind: string;
    before_json: string | null;
    after_json: string | null;
  };

  let { lang }: { lang: Lang } = $props();
  let rows = $state<Change[]>([]);
  let errorMessage = $state("");
  let errorExtra = $state("");

  function changeLabel(kind: string): string {
    const map: Record<string, CopyKey> = {
      added: "changeAdded",
      removed: "changeRemoved",
      changed: "changeChanged",
    };
    const key = map[kind];
    return key ? copy(lang, key) : kind;
  }

  $effect(() => {
    void api<{ changes: Change[] }>("/api/v1/changes")
      .then((payload) => {
        rows = payload.changes;
      })
      .catch((error: unknown) => {
        errorMessage = shownError(error, lang);
        errorExtra = errorDetail(error);
      });
  });
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "changes")}</h1>
  <ul class="divide-y divide-graphite rounded-xl border border-graphite">
    {#each rows as row (`${row.entity_kind}:${row.entity_key}:${row.change_kind}`)}
      <li class="px-4 py-3">
        <p class="text-paper">{changeLabel(row.change_kind)} · {row.entity_kind}</p>
        <p class="font-mono text-xs text-fog">{row.entity_key}</p>
      </li>
    {:else}
      <li class="px-4 py-3 text-fog">{copy(lang, "empty")}</li>
    {/each}
  </ul>
</section>

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
