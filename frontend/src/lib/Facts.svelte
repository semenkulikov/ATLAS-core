<script lang="ts">
  import { copy, predicateLabel, type Lang } from "./i18n";
  import type { Fact } from "./api";

  let { facts, lang, onopen }: { facts: Fact[]; lang: Lang; onopen: (id: number) => void } = $props();
</script>

{#if facts.length > 0}
  <ul class="mt-3 divide-y divide-graphite">
    {#each facts as fact (fact.id)}
      <li>
        <button
          type="button"
          class="grid w-full grid-cols-[1fr_auto] gap-3 py-2 text-left"
          onclick={() => onopen(fact.id)}
        >
          <span>
            <span class="text-xs text-fog">{predicateLabel(lang, fact.predicate)}</span>
            <span class="mt-1 block text-paper">{fact.value}</span>
          </span>
          {#if fact.certainty === "derived"}
            <span class="h-fit rounded bg-tag/20 px-1.5 py-0.5 text-xs text-tag" title={fact.rule ?? ""}>
              {copy(lang, "derived")}
            </span>
          {:else if fact.certainty === "unknown"}
            <span class="h-fit rounded border border-dashed border-ash px-1.5 py-0.5 text-xs text-ash">
              {copy(lang, "unknown")}
            </span>
          {:else}
            <span class="h-fit rounded border border-graphite px-1.5 py-0.5 text-xs text-fog">
              {copy(lang, "fact")}
            </span>
          {/if}
        </button>
      </li>
    {/each}
  </ul>
  <details class="mt-2">
    <summary class="cursor-pointer text-xs text-ash">{copy(lang, "technical")}</summary>
    <ul class="mt-1 space-y-1">
      {#each facts as fact (fact.id)}
        <li class="font-mono text-xs text-ash">{fact.predicate} · {fact.certainty}{fact.rule ? ` · ${fact.rule}` : ""}</li>
      {/each}
    </ul>
  </details>
{/if}
