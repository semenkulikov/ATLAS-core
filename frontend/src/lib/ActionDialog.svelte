<script lang="ts">
  import { ApiError, api } from "./api";
  import { copy, type Lang } from "./i18n";

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
  let error = $state("");
  let done = $state("");

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = "";
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
      done = body.pending ? `${body.pending}` : copy(lang, "saved");
    } catch (caught) {
      error = caught instanceof ApiError ? caught.message : copy(lang, "error");
    }
  }
</script>

<div class="fixed inset-0 z-40 grid place-items-center bg-void/80 p-4" role="dialog" aria-modal="true">
  <form class="w-full max-w-md rounded-xl border border-graphite bg-carbon p-5" onsubmit={submit}>
    <h2 class="mb-2 text-lg text-paper">{op}</h2>
    <p class="mb-4 font-mono text-sm text-fog">{objectName}</p>
    <label class="mb-3 block text-sm text-fog">
      {copy(lang, "typeToConfirm")}
      <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-paper" bind:value={confirm} />
    </label>
    {#if risk !== "medium"}
      <label class="mb-3 block text-sm text-fog">
        {copy(lang, "code")}
        <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 text-paper" bind:value={code} inputmode="numeric" />
      </label>
    {/if}
    {#if error}<p class="mb-3 text-sm text-warn" role="status">{error}</p>{/if}
    {#if done}<p class="mb-3 text-sm text-paper" role="status">{done}</p>{/if}
    <div class="flex gap-3">
      <button type="submit" class="rounded-md bg-accent px-3 py-1.5 text-sm text-void">{copy(lang, "confirm")}</button>
      <button type="button" class="text-sm text-fog" onclick={onclose}>{copy(lang, "close")}</button>
    </div>
  </form>
</div>
