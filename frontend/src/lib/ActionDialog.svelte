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
    onclose,
  }: {
    lang: Lang;
    op: string;
    objectName: string;
    risk: "medium" | "high" | "critical";
    onclose: () => void;
  } = $props();

  let confirm = $state("");
  let code = $state("");
  let done = $state("");
  let errorMessage = $state("");
  let errorExtra = $state("");

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    errorMessage = "";
    errorExtra = "";
    const params: Record<string, string> =
      op === "host.reboot" || op === "host.poweroff"
        ? { hostname: objectName }
        : op.startsWith("container.")
          ? { name: objectName }
          : { unit: objectName };
    try {
      const body = await api<{ ok?: boolean; pending?: string; result?: string }>(
        `/api/v1/actions/${op}`,
        { method: "POST", body: JSON.stringify({ params, confirm, code }) },
      );
      done = body.pending ? String(body.pending) : copy(lang, "saved");
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
    <p class="mb-4 font-mono text-sm text-fog">{objectName}</p>
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
    <div class="flex gap-3">
      <button
        type="submit"
        class="rounded-md border border-crit bg-obsidian px-3 py-1.5 text-sm text-paper"
      >
        {copy(lang, "confirm")}
      </button>
      <button type="button" class="text-sm text-fog" onclick={onclose}>{copy(lang, "close")}</button>
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
