<script lang="ts">
  import { copy, type Lang } from "../i18n";

  let {
    lang,
    title,
    onclose,
    danger = false,
    children,
  }: {
    lang: Lang;
    title: string;
    onclose: () => void;
    danger?: boolean;
    children: import("svelte").Snippet;
  } = $props();
</script>

<div
  class="atlas-backdrop-in fixed inset-0 z-40 grid place-items-center bg-void/80 p-4"
  role="dialog"
  aria-modal="true"
  aria-label={title}
>
  <div
    class="atlas-fade-in w-full max-w-md rounded-xl border bg-carbon p-5 {danger
      ? 'border-crit'
      : 'border-graphite'}"
  >
    <div class="mb-3 flex items-start justify-between gap-3">
      <h2 class="text-lg text-paper">{title}</h2>
      <button type="button" class="text-sm text-fog" onclick={onclose}>{copy(lang, "close")}</button>
    </div>
    {@render children()}
  </div>
</div>
