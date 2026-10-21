<script lang="ts">
  import { onMount } from "svelte";
  import { isSystemUser } from "./apps";
  import { shownError } from "./api";
  import { formatBytes, formatUptime, textOf } from "./format";
  import { copy, type Lang } from "./i18n";
  import { loadPanel, type PanelData } from "./inventory";

  let { lang, tab = "services" }: { lang: Lang; tab?: string } = $props();
  let data = $state<PanelData | null>(null);
  let errorMessage = $state("");
  let onlyDown = $state(false);
  let query = $state("");

  const tabs = [
    ["services", "servicesWord"],
    ["timers", "timerWord"],
    ["containers", "containersWord"],
    ["accounts", "accountsWord"],
    ["server", "serverTab"],
  ] as const;

  onMount(() => {
    void loadPanel()
      .then((body) => {
        data = body;
      })
      .catch((error: unknown) => {
        errorMessage = shownError(error, lang);
      });
  });

  function scheduleTitle(row: { key: string; payload: Record<string, unknown> }): string {
    const description = textOf(row.payload.description);
    const command = textOf(row.payload.command);
    if (description && description !== row.key) return description;
    if (command.length > 72) return `${command.slice(0, 69)}…`;
    return command || row.key;
  }

  const services = $derived(
    (data?.system.services ?? []).filter((row) => {
      if (query && !row.key.toLowerCase().includes(query.toLowerCase())) return false;
      if (!onlyDown) return true;
      const active = textOf(row.payload["unit.active"]);
      return active === "failed" || active === "inactive";
    }),
  );
</script>

<section class="atlas-fade-in">
  <h1 class="screen-title mb-2">{copy(lang, "system")}</h1>
  <p class="mb-4 max-w-prose text-sm text-fog">{copy(lang, "systemIntro")}</p>
  <div class="mb-4 flex gap-2 overflow-x-auto">
    {#each tabs as [id, key] (id)}
      <a class="chip whitespace-nowrap" href={`#/system/${id}`} aria-current={tab === id ? "page" : undefined}>{copy(lang, key)}</a>
    {/each}
  </div>
  {#if errorMessage}
    <div class="card"><p>{errorMessage}</p></div>
  {:else if !data}
    <div class="skeleton h-40"></div>
  {:else if tab === "timers"}
    <div class="card overflow-auto p-0">
      <table class="data-table">
        <thead><tr><th>{copy(lang, "doesWhat")}</th><th>{copy(lang, "whenLabel")}</th><th>{copy(lang, "outcome")}</th></tr></thead>
        <tbody>
          {#each data.system.schedules as row (row.key)}
            <tr>
              <td>{scheduleTitle(row)}</td>
              <td class="mono">{textOf(row.payload.schedule) || textOf(row.payload.expression) || row.key}</td>
              <td>{textOf(row.payload.last_result) || "—"}</td>
            </tr>
          {:else}
            <tr><td colspan="3">{copy(lang, "empty")}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if tab === "containers"}
    <div class="card overflow-auto p-0">
      <table class="data-table">
        <thead><tr><th>{copy(lang, "fieldName")}</th><th>{copy(lang, "imageLabel")}</th><th>{copy(lang, "stateLabel")}</th></tr></thead>
        <tbody>
          {#each data.system.containers as row (row.key)}
            <tr>
              <td class="mono">{textOf(row.payload.name) || row.key}</td>
              <td class="mono">{textOf(row.payload.image)}</td>
              <td>{textOf(row.payload.state)}</td>
            </tr>
          {:else}
            <tr><td colspan="3">{copy(lang, "empty")}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if tab === "accounts"}
    <p class="kicker mb-3">{copy(lang, "accountsHint")}</p>
    <ul class="card">
      {#each data.users.filter((row) => isSystemUser(row)) as row (row.key)}
        <li class="flex justify-between border-b border-smoke py-2"><span class="mono">{row.key}</span><span class="text-fog">{textOf(row.payload.shell)}</span></li>
      {/each}
    </ul>
  {:else if tab === "server"}
    <dl class="card grid gap-3 md:grid-cols-2">
      <div><dt class="kicker">{copy(lang, "osWord")}</dt><dd>{data.os || "—"}</dd></div>
      <div><dt class="kicker">{copy(lang, "kernelWord")}</dt><dd class="mono">{data.kernel || "—"}</dd></div>
      <div><dt class="kicker">{copy(lang, "virtWord")}</dt><dd>{data.virt || "—"}</dd></div>
      <div><dt class="kicker">{copy(lang, "archWord")}</dt><dd>{data.arch || "—"}</dd></div>
      <div><dt class="kicker">{copy(lang, "uptimeLabel")}</dt><dd>{formatUptime(data.uptimeRaw, lang) || "—"}</dd></div>
      <div><dt class="kicker">{copy(lang, "memory")}</dt><dd>{data.memTotal ? formatBytes(data.memTotal, lang) : "—"}</dd></div>
      <div><dt class="kicker">{copy(lang, "serverName")}</dt><dd>{data.hostname || "—"}</dd></div>
    </dl>
  {:else}
    <div class="mb-3 flex flex-wrap gap-2">
      <input class="h-8 rounded-md border border-smoke bg-void px-3 text-sm" placeholder={copy(lang, "filterQuery")} bind:value={query} />
      <button type="button" class="btn btn-secondary" aria-pressed={onlyDown} onclick={() => (onlyDown = !onlyDown)}>{copy(lang, "onlyFailed")}</button>
    </div>
    <div class="card overflow-auto p-0">
      <table class="data-table">
        <thead>
          <tr>
            <th>{copy(lang, "fieldName")}</th>
            <th>{copy(lang, "doesWhat")}</th>
            <th>{copy(lang, "stateLabel")}</th>
            <th>{copy(lang, "enabledWord")}</th>
          </tr>
        </thead>
        <tbody>
          {#each services as row (row.key)}
            <tr>
              <td class="mono text-paper">{row.key}</td>
              <td>{textOf(row.payload.description) || copy(lang, "noDescription")}</td>
              <td>
                {textOf(row.payload["unit.active"]) || "—"}
                {#if row.key === "ssh.service" && textOf(row.payload["unit.active"]) !== "active"}
                  <span class="block text-xs text-fog">{copy(lang, "socketListen")}</span>
                {/if}
              </td>
              <td>{textOf(row.payload["unit.enabled"]) === "enabled" ? copy(lang, "startOnBoot") : copy(lang, "notOnBoot")}</td>
            </tr>
          {:else}
            <tr><td colspan="4">{copy(lang, "empty")}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
