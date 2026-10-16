<script lang="ts">
  import { copy, type Lang } from "../i18n";

  let { lang, on = true }: { lang: Lang; on?: boolean } = $props();
</script>

{#if on}
  <span class="inline-flex items-center gap-1.5 rounded-full border border-graphite px-2 py-0.5 text-xs text-fog">
    <span class="atlas-live-dot inline-block h-1.5 w-1.5 rounded-full bg-ok" aria-hidden="true"></span>
    {copy(lang, "live")}
  </span>
{/if}
