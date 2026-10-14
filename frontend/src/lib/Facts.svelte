<script lang="ts">
  import { copy, type Lang } from "./i18n";
  import type { Fact } from "./api";

  let { facts, lang, onopen }: { facts: Fact[]; lang: Lang; onopen: (id: number) => void } = $props();
</script>

<ul class="divide-y divide-graphite">
  {#each facts as fact (fact.id)}
    <li>
      <button type="button" class="grid w-full grid-cols-[1fr_auto] gap-3 py-2 text-left" onclick={() => onopen(fact.id)}>
        <span>
          <span class="font-mono text-xs text-fog">{fact.predicate}</span>
          <span class="mt-1 block text-paper">{fact.value}</span>
        </span>
        {#if fact.certainty === "derived"}
          <span class="h-fit rounded px-1.5 py-0.5 text-xs text-tag">{fact.rule}</span>
        {:else if fact.certainty === "unknown"}
          <span class="h-fit rounded border border-dashed border-ash px-1.5 py-0.5 text-xs text-ash">{copy(lang, "unknown")}</span>
        {:else}
          <span class="h-fit rounded border border-graphite px-1.5 py-0.5 text-xs text-fog">{fact.certainty}</span>
        {/if}
      </button>
    </li>
  {/each}
</ul>
