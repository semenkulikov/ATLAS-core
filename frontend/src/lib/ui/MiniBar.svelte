<script lang="ts">
  let { label, text, percent }: { label: string; text: string; percent: number | null } = $props();
</script>

<div class="grid grid-cols-[auto_1fr_auto] items-center gap-2">
  <span class="kicker">{label}</span>
  <span class="h-1 overflow-hidden rounded-full bg-graphite">
    {#if percent !== null}
      <span class="minibar-fill block" style:width={`${Math.max(2, Math.min(100, percent))}%`}></span>
    {/if}
  </span>
  <span class="kicker text-paper">{text}</span>
</div>
