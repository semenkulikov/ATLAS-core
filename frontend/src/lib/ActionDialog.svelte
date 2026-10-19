<script lang="ts">
  import { ApiError, api, errorDetail, shownError } from "./api";
  import { actionTitle, copy, type Lang } from "./i18n";
  import ErrorModal from "./ui/ErrorModal.svelte";
  import Modal from "./ui/Modal.svelte";

  let {
    lang,
    op,
    objectName,
    risk,
    note = "",
    onclose,
    ondone,
  }: {
    lang: Lang;
    op: string;
    objectName: string;
    risk: "medium" | "high" | "critical";
    note?: string;
    onclose: () => void;
    ondone?: () => void;
  } = $props();

  let confirm = $state("");
  let wait = $state(0);
  let cancelButton = $state<HTMLButtonElement | null>(null);
  let code = $state("");
  let done = $state("");
  let errorMessage = $state("");
  let errorExtra = $state("");

  $effect(() => {
    cancelButton?.focus();
    if (!op.startsWith("host.")) return;
    wait = 3;
    const timer = setInterval(() => {
      wait = Math.max(0, wait - 1);
    }, 1000);
    return () => clearInterval(timer);
  });

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    errorMessage = "";
    errorExtra = "";
    const params: Record<string, string> =
      op === "host.reboot" || op === "host.poweroff"
        ? { hostname: objectName }
        : op === "app.update"
          ? { version: objectName }
          : op.startsWith("container.")
            ? { name: objectName }
            : { unit: objectName };
    try {
      const body = await api<{ ok?: boolean; pending?: string; result?: string }>(
        `/api/v1/actions/${op}`,
        { method: "POST", body: JSON.stringify({ params, confirm, code }) },
      );
      done = body.pending ? String(body.pending) : copy(lang, "saved");
      if (!body.pending) ondone?.();
    } catch (caught) {
      errorMessage = shownError(caught, lang);
      errorExtra = errorDetail(caught);
      if (!(caught instanceof ApiError)) {
        errorMessage = copy(lang, "errGeneric");
      }
    }
  }
</script>

<Modal {lang} title={actionTitle(lang, op)} {onclose} danger>
  <form onsubmit={submit}>
    <p class="mb-2 text-sm text-paper">{objectName}</p>
    {#if note}<p class="mb-4 text-sm text-fog">{note}</p>{/if}
    <label class="mb-3 block text-sm text-fog">
      {copy(lang, "typeToConfirm")}
      <input
        class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-paper"
        bind:value={confirm}
      />
    </label>
    {#if risk !== "medium"}
      <label class="mb-3 block text-sm text-fog">
        {copy(lang, "code")}
        <input
          class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 text-paper"
          bind:value={code}
          inputmode="numeric"
        />
      </label>
    {/if}
    {#if done}<p class="mb-3 text-sm text-ok" role="status">{done}</p>{/if}
    <div class="flex flex-wrap gap-3">
      <button type="button" class="btn btn-secondary" bind:this={cancelButton} onclick={onclose}>{copy(lang, "cancel")}</button>
      <button type="submit" class="btn btn-danger" disabled={wait > 0}>
        {wait > 0 ? `${copy(lang, "countdown")} ${wait}` : copy(lang, "confirm")}
      </button>
    </div>
  </form>
</Modal>

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
