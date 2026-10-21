<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import ActionDialog from "./ActionDialog.svelte";
  import { api } from "./api";
  import { zoneName } from "./format";
  import { copy, type Lang } from "./i18n";
  import { loadPanel, type PanelData } from "./inventory";

  let { lang, role, onlang }: { lang: Lang; role: string; onlang: (next: Lang) => void } = $props();
  let tab = $state("server");
  let enabled = $state(false);
  let hostname = $state("");
  let risks = $state<{ kind: string; name: string }[]>([]);
  let channels = $state<{ id: number; kind: string; enabled: boolean; target?: string }[]>([]);
  let kind = $state("webhook");
  let target = $state("");
  let turnOn = $state(false);
  let note = $state("");
  let showTarget = $state(false);
  let raw = $state(localStorage.getItem("atlas.raw") === "1");
  let data = $state<PanelData | null>(null);
  let reboot = $state<string | null>(null);
  let updateInfo = $state<{
    current: string;
    latest: string | null;
    update_available: boolean;
    error: string | null;
  } | null>(null);
  let updating = $state(false);
  let showUpdate = $state(false);
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const tabs = [
    ["server", "tabServer"],
    ["panel", "tabPanel"],
    ["alerts", "tabAlerts"],
    ["about", "tabAbout"],
  ] as const;

  function reloadChannels(): void {
    void api<{ channels: { id: number; kind: string; enabled: boolean; target?: string }[] }>("/api/v1/alerts")
      .then((body) => {
        channels = body.channels;
      })
      .catch(() => undefined);
  }

  function loadUpdate(): void {
    void api<{
      current: string;
      latest: string | null;
      update_available: boolean;
      error: string | null;
    }>("/api/v1/update")
      .then((body) => {
        updateInfo = body;
      })
      .catch(() => {
        updateInfo = { current: "—", latest: null, update_available: false, error: "unreachable" };
      });
  }

  function stopPoll(): void {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function watchUpdate(targetVersion: string): void {
    updating = true;
    note = copy(lang, "updateStarted");
    stopPoll();
    let tries = 0;
    pollTimer = setInterval(() => {
      tries += 1;
      void api<{ current: string }>("/api/v1/update")
        .then((body) => {
          if (body.current === targetVersion) {
            stopPoll();
            location.reload();
          }
        })
        .catch(() => {
          // Socket drops while the unit restarts the panel.
          if (tries > 3) {
            /* keep polling until the new process answers or we hit the limit */
          }
        });
      if (tries > 90) {
        stopPoll();
        updating = false;
        note = copy(lang, "error");
      }
    }, 2000);
  }

  onMount(() => {
    const place = location.hash.split("/")[2];
    if (place === "panel" || place === "alerts" || place === "about" || place === "server") tab = place;
    void api<{ enabled: boolean; hostname: string; risks: { kind: string; name: string }[] }>("/api/v1/control")
      .then((body) => {
        enabled = body.enabled;
        hostname = body.hostname;
        risks = body.risks;
      })
      .catch(() => undefined);
    void loadPanel().then((body) => {
      data = body;
    }).catch(() => undefined);
    reloadChannels();
    loadUpdate();
  });

  onDestroy(stopPoll);

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
      note = copy(lang, "saved");
      reloadChannels();
    } catch {
      note = copy(lang, "error");
    }
  }

  function toggleRaw(): void {
    raw = !raw;
    localStorage.setItem("atlas.raw", raw ? "1" : "0");
    note = copy(lang, "saved");
  }

  const riskNote = $derived(
    risks.length
      ? `${copy(lang, "wontReturn")}: ${risks.map((risk) => risk.name).join(", ")}`
      : copy(lang, "noneRisk"),
  );
</script>

<section class="atlas-fade-in">
  <h1 class="screen-title mb-4">{copy(lang, "settings")}</h1>
  <div class="mb-4 flex gap-2 overflow-x-auto">
    {#each tabs as [id, key] (id)}
      <a class="chip whitespace-nowrap" href={`#/settings/${id}`} aria-current={tab === id ? "page" : undefined} onclick={() => (tab = id)}>
        {copy(lang, key)}
      </a>
    {/each}
  </div>
  {#if note}<p class="kicker mb-3" role="status">{note}</p>{/if}

  {#if tab === "server"}
    <div class="card mb-4">
      <p class="kicker">{copy(lang, "displayName")}</p>
      <p class="mt-1 text-paper">{data?.hostname || hostname || "—"}</p>
      <p class="kicker mt-3">{copy(lang, "timezoneLabel")}</p>
      <p class="mt-1">{data?.timezone ? zoneName(data.timezone) : copy(lang, "notSet")}</p>
    </div>
    <section class="card">
      <h2 class="block-title">{copy(lang, "dangerZone")}</h2>
      <p class="mt-2 text-sm text-fog">{copy(lang, "powerHint")}</p>
      <div class="mt-4 flex flex-col gap-2 sm:flex-row">
        <button type="button" class="btn btn-danger" disabled={role === "viewer" || !enabled} onclick={() => (reboot = "host.reboot")}>{copy(lang, "rebootHost")}</button>
        <button type="button" class="btn btn-danger" disabled={role === "viewer" || !enabled} onclick={() => (reboot = "host.poweroff")}>{copy(lang, "powerOff")}</button>
      </div>
      {#if !enabled}<p class="kicker mt-3">{copy(lang, "readOnly")}</p>{/if}
    </section>
  {:else if tab === "panel"}
    <div class="card grid gap-3">
      <p><span class="kicker">{copy(lang, "role")}</span> <span class="text-paper">{role}</span></p>
      <p><span class="kicker">{copy(lang, "twoFactor")}</span> {copy(lang, "twoFactorOn")}</p>
      <p class="text-sm text-fog">{copy(lang, "allowedAddr")}</p>
    </div>
  {:else if tab === "alerts"}
    <p class="mb-3 text-sm text-fog">{copy(lang, "channelLater")}</p>
    {#if channels.length === 0}
      <p class="card mb-4">{copy(lang, "emptyChannel")}</p>
    {:else}
      <ul class="card mb-4">
        {#each channels as channel (channel.id)}
          <li class="flex items-center justify-between py-2">
            <span>{channel.kind}</span>
            <span class="mono text-fog">{showTarget ? (channel.target ?? "") : copy(lang, "webhookMask")}</span>
          </li>
        {/each}
      </ul>
      <button type="button" class="btn btn-ghost mb-4" onclick={() => (showTarget = !showTarget)}>{showTarget ? copy(lang, "hideSecret") : copy(lang, "showSecret")}</button>
    {/if}
    <form class="card grid gap-3" onsubmit={saveChannel}>
      <label class="text-sm text-fog">{copy(lang, "channelKind")}
        <input class="mt-1 block h-8 w-full rounded-md border border-smoke bg-void px-3" bind:value={kind} />
      </label>
      <label class="text-sm text-fog">{copy(lang, "channelTarget")}
        <input class="mt-1 block h-8 w-full rounded-md border border-smoke bg-void px-3" bind:value={target} />
      </label>
      <label class="flex items-center gap-2 text-sm"><input type="checkbox" bind:checked={turnOn} /> {copy(lang, "channelEnable")}</label>
      <button class="btn btn-accent w-fit" type="submit">{copy(lang, "save")}</button>
    </form>
  {:else}
    <div class="card grid gap-3">
      {#if updateInfo}
        <p><span class="kicker">{copy(lang, "installedVersion")}</span> <span class="mono text-paper">{updateInfo.current}</span></p>
        {#if updateInfo.latest}
          <p><span class="kicker">{copy(lang, "availableVersion")}</span> <span class="mono text-paper">{updateInfo.latest}</span></p>
        {/if}
        {#if updateInfo.error && !updateInfo.latest}
          <p class="text-sm text-fog">{copy(lang, "updateUnavailable")}</p>
        {:else if updateInfo.update_available}
          <p class="text-sm text-fog">{copy(lang, "updateHint")}</p>
          <button
            type="button"
            class="btn btn-accent w-fit"
            disabled={role !== "owner" || !enabled || updating || !updateInfo.latest}
            onclick={() => (showUpdate = true)}
          >
            {copy(lang, "updateNow")}
          </button>
          {#if !enabled}<p class="kicker">{copy(lang, "readOnly")}</p>{/if}
        {:else if updateInfo.latest}
          <p class="text-sm text-fog">{copy(lang, "updateCurrent")}</p>
        {/if}
      {:else}
        <p class="text-sm text-fog">{copy(lang, "updateChecking")}</p>
      {/if}
      <p class="text-sm text-fog">{copy(lang, "signatureHint")}</p>
      <label class="text-sm text-fog">{copy(lang, "languageLabel")}
        <select class="mt-1 block h-8 rounded-md border border-smoke bg-void px-2" value={lang} onchange={(event) => onlang((event.currentTarget as HTMLSelectElement).value === "en" ? "en" : "ru")}>
          <option value="ru">Русский</option>
          <option value="en">English</option>
        </select>
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={raw} onchange={toggleRaw} />
        {copy(lang, "showRaw")}
      </label>
      <p class="kicker">{copy(lang, "rawHint")}</p>
      <p><span class="kicker">{copy(lang, "sourcesCount")}</span> {data?.sourceCount ?? "—"}</p>
      <a class="text-sm text-info" href="#/system/services">{copy(lang, "systemServices")}</a>
    </div>
  {/if}
</section>

{#if reboot}
  <ActionDialog
    {lang}
    op={reboot}
    objectName={hostname || data?.hostname || ""}
    risk="critical"
    note={riskNote}
    onclose={() => (reboot = null)}
  />
{/if}

{#if showUpdate && updateInfo?.latest}
  <ActionDialog
    {lang}
    op="app.update"
    objectName={updateInfo.latest}
    risk="high"
    note={copy(lang, "updateHint")}
    onclose={() => (showUpdate = false)}
    ondone={() => {
      const targetVersion = updateInfo?.latest;
      showUpdate = false;
      if (targetVersion) watchUpdate(targetVersion);
    }}
  />
{/if}
