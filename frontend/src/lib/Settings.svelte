<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "./api";
  import { copy, type Lang } from "./i18n";

  let { lang }: { lang: Lang } = $props();
  let enabled = $state(false);
  let risks = $state<{ kind: string; name: string; enabled: string }[]>([]);
  let failed = $state(false);

  onMount(() => {
    void api<{ enabled: boolean; risks: { kind: string; name: string; enabled: string }[] }>(
      "/api/v1/control",
    )
      .then((body) => {
        enabled = body.enabled;
        risks = body.risks;
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
  {/if}
</section>
