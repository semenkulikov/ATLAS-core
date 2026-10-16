<script lang="ts">
  import { copy, type Lang } from "../i18n";
  import Modal from "./Modal.svelte";

  let {
    lang,
    message,
    detail = "",
    onclose,
  }: {
    lang: Lang;
    message: string;
    detail?: string;
    onclose: () => void;
  } = $props();

  let showDetail = $state(false);
</script>

<Modal {lang} title={copy(lang, "errorTitle")} {onclose} danger>
  <p class="mb-3 text-sm text-mist" role="alert">{message}</p>
  {#if detail}
    <button type="button" class="mb-3 text-xs text-fog underline" onclick={() => (showDetail = !showDetail)}>
      {showDetail ? copy(lang, "hideDetails") : copy(lang, "showDetails")}
    </button>
    {#if showDetail}
      <pre class="mb-3 overflow-auto rounded-md border border-graphite bg-void p-2 font-mono text-xs text-fog">{detail}</pre>
    {/if}
  {/if}
  <button type="button" class="rounded-md border border-graphite px-3 py-1.5 text-sm text-paper" onclick={onclose}>
    {copy(lang, "close")}
  </button>
</Modal>
