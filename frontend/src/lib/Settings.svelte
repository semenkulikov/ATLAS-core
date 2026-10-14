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
    void api<{ channels: { id: number; kind: string; enabled: boolean }[] }>("/api/v1/alerts")
      .then((body) => {
        channels = body.channels;
      })
      .catch(() => {
        failed = true;
      });
  });
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
    <div class="mt-8">
    {#if channels.some((channel) => channel.enabled)}
      <ul class="space-y-2">
        {#each channels as channel (channel.id)}
          <li class="font-mono text-sm text-paper">{channel.kind} {channel.enabled ? "on" : "off"}</li>
        {/each}
      </ul>
    {:else}
      <p class="max-w-xl text-sm text-fog">{copy(lang, "channelsOff")}</p>
    {/if}
    </div>
    {#if role === "owner" && enabled && hostname}
      <button type="button" class="mt-8 text-sm text-accent" onclick={() => (reboot = true)}>host.reboot</button>
    {/if}
  {/if}
</section>

{#if reboot && hostname}
  <ActionDialog {lang} op="host.reboot" objectName={hostname} risk="critical" onclose={() => (reboot = false)} />
{/if}
