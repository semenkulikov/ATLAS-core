<script lang="ts">
  import { onMount } from "svelte";
  import { ApiError, api } from "./api";
  import { copy, type Lang } from "./i18n";

  type Row = {
    id: number;
    ts: string;
    actor: string;
    action: string;
    result: string;
  };

  let { lang }: { lang: Lang } = $props();
  let rows = $state<Row[]>([]);
  let intact = $state(true);
  let denied = $state(false);
  let failed = $state(false);

  onMount(() => {
    void api<{ items: Row[]; intact: boolean }>("/api/v1/audit")
      .then((body) => {
        rows = body.items;
        intact = body.intact;
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 403) denied = true;
        else failed = true;
      });
  });
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "audit")}</h1>
  {#if denied}
    <p class="text-sm text-fog">{copy(lang, "role")}</p>
  {:else if failed}
    <p class="text-sm text-fog">{copy(lang, "error")}</p>
  {:else}
    <p class="mb-4 text-sm text-fog">{intact ? copy(lang, "intact") : copy(lang, "broken")}</p>
    {#if rows.length === 0}
      <p class="text-sm text-fog">{copy(lang, "empty")}</p>
    {:else}
      <table class="w-full text-left text-sm">
        <thead class="text-mist">
          <tr>
            <th class="py-2 pr-4 font-normal">{copy(lang, "when")}</th>
            <th class="py-2 pr-4 font-normal">{copy(lang, "actor")}</th>
            <th class="py-2 pr-4 font-normal">{copy(lang, "action")}</th>
            <th class="py-2 font-normal">{copy(lang, "result")}</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row (row.id)}
            <tr class="border-t border-graphite font-mono text-paper">
              <td class="py-2 pr-4">{row.ts}</td>
              <td class="py-2 pr-4">{row.actor}</td>
              <td class="py-2 pr-4">{row.action}</td>
              <td class="py-2">{row.result}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</section>
