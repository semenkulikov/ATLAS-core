<script lang="ts">
  let {
    title,
    count = 0,
    open = $bindable(false),
    children,
  }: {
    title: string;
    count?: number;
    open?: boolean;
    children: import("svelte").Snippet;
  } = $props();
</script>

<details
  class="mt-4 rounded-xl border border-graphite bg-carbon"
  bind:open
>
  <summary class="cursor-pointer list-none px-4 py-3 text-sm text-fog marker:content-none">
    <span class="inline-flex items-center gap-2">
      <span class="text-mist">{title}</span>
      {#if count > 0}
        <span class="rounded px-1.5 py-0.5 font-mono text-xs text-ash">{count}</span>
      {/if}
    </span>
  </summary>
  <div class="border-t border-graphite px-2 pb-2">
    {@render children()}
  </div>
</details>
