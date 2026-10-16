<script lang="ts">
  import { onMount } from "svelte";
  import ActionDialog from "./ActionDialog.svelte";
  import { api } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang, role }: { lang: Lang; role: string } = $props();
  let enabled = $state(false);
  let hostname = $state("");
  let risks = $state<{ kind: string; name: string; enabled: string }[]>([]);
  let channels = $state<{ id: number; kind: string; enabled: boolean }[]>([]);
  let failed = $state(false);
  let reboot = $state(false);
  let kind = $state("webhook");
  let target = $state("");
  let turnOn = $state(false);
  let note = $state("");

  function reloadChannels(): void {
    void api<{ channels: { id: number; kind: string; enabled: boolean }[] }>("/api/v1/alerts")
      .then((body) => {
        channels = body.channels;
      })
      .catch(() => {
        failed = true;
      });
  }

  onMount(() => {
    void api<{
      enabled: boolean;
      hostname: string;
      risks: { kind: string; name: string; enabled: string }[];
    }>("/api/v1/control")
      .then((body) => {
        enabled = body.enabled;
        hostname = body.hostname;
        risks = body.risks;
      })
      .catch(() => {
        failed = true;
      });
    reloadChannels();
  });

  async function saveChannel(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    note = "";
    try {
      await api("/api/v1/alerts/channels", {
        method: "POST",
        body: JSON.stringify({ kind, target, enabled: turnOn }),
      });
      target = "";
      turnOn = false;
      note = copy(lang, "channelSaved");
      reloadChannels();
    } catch {
      note = copy(lang, "error");
    }
  }
</script>

<section>
  <h1 class="mb-4 text-2xl text-paper">{copy(lang, "settings")}</h1>
  {#if failed}
    <p class="text-sm text-fog">{copy(lang, "error")}</p>
  {:else}
    <p class="max-w-xl text-sm text-fog">{enabled ? copy(lang, "controlOn") : copy(lang, "readOnly")}</p>
    <h2 class="mt-8 mb-3 text-sm text-mist">{copy(lang, "risks")}</h2>
    {#if risks.length === 0}
      <p class="text-sm text-fog">{copy(lang, "empty")}</p>
    {:else}
      <ul class="space-y-2">
        {#each risks as risk (`${risk.kind}:${risk.name}`)}
          <li class="font-mono text-sm text-paper">{risk.kind} {risk.name}</li>
        {/each}
      </ul>
    {/if}
    <h2 class="mt-8 mb-3 text-sm text-mist">{copy(lang, "alerts")}</h2>
    {#if channels.length === 0}
      <p class="max-w-xl text-sm text-fog">{copy(lang, "channelsOff")}</p>
    {:else}
      <ul class="mb-4 space-y-2">
        {#each channels as channel (channel.id)}
          <li class="font-mono text-sm text-paper">
            {channel.kind} {channel.enabled ? copy(lang, "on") : copy(lang, "off")}
          </li>
        {/each}
      </ul>
    {/if}
    {#if role === "owner"}
      <form class="mt-4 flex max-w-xl flex-col gap-3" onsubmit={saveChannel}>
        <label class="text-sm text-fog">
          {copy(lang, "channelKind")}
          <select class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 text-paper" bind:value={kind}>
            <option value="webhook">webhook</option>
            <option value="telegram">telegram</option>
          </select>
        </label>
        <label class="text-sm text-fog">
          {copy(lang, "channelTarget")}
          <input
            class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper"
            bind:value={target}
            placeholder={kind === "telegram" ? "bot-token chat-id" : "https://hooks.example/path"}
          />
        </label>
        <label class="flex items-center gap-2 text-sm text-fog">
          <input type="checkbox" bind:checked={turnOn} />
          {copy(lang, "channelEnable")}
        </label>
        <button class="self-start rounded-md bg-accent px-3 py-2 text-void" type="submit">{copy(lang, "save")}</button>
        {#if note}
          <p class="text-sm text-fog" role="status">{note}</p>
        {/if}
      </form>
    {/if}
    {#if role === "owner" && enabled && hostname}
      <button type="button" class="mt-8 rounded-md border border-crit px-3 py-1.5 text-sm text-paper" onclick={() => (reboot = true)}>
        {copy(lang, "opReboot")}
      </button>
    {/if}
  {/if}
</section>

{#if reboot && hostname}
  <ActionDialog {lang} op="host.reboot" objectName={hostname} risk="critical" onclose={() => (reboot = false)} />
{/if}
