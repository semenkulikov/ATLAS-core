<script lang="ts">
  import { onMount } from "svelte";
  import { shownError } from "./api";
  import { exposureOf, listenerKey, portHint, textOf, type Exposure } from "./format";
  import { copy, type Lang } from "./i18n";
  import { chooseFirewall, portFirewall } from "./firewall";
  import { loadPanel, type PanelData } from "./inventory";
  import { selectedApp } from "./selection";
  import CopyButton from "./ui/CopyButton.svelte";
  import Mark from "./ui/Mark.svelte";

  let { lang }: { lang: Lang } = $props();
  let data = $state<PanelData | null>(null);
  let errorMessage = $state("");
  let filter = $state<"all" | Exposure | "orphan">("all");
  let picked = $state<string>("");
  let appFilter = $state("");

  $effect(() => {
    if (!picked) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") picked = "";
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  selectedApp.subscribe((id) => {
    appFilter = id;
  });

  type Row = {
    key: string;
    port: number;
    protocol: string;
    addresses: string[];
    exposure: Exposure;
    owner: string;
    appId: string;
    appName: string;
    command: string;
    orphan: boolean;
  };

  const rows = $derived.by(() => {
    if (!data) return [];
    const all = [
      ...data.apps.flatMap((app) => app.ports.map((port) => ({ port, appId: app.id, appName: app.name }))),
      ...data.system.ports.map((port) => ({ port, appId: "", appName: "" })),
    ];
    const grouped = new Map<string, Row>();
    for (const item of all) {
      const address = textOf(item.port.payload.address);
      const rawProtocol = textOf(item.port.payload.protocol) || "tcp";
      const protocol = rawProtocol.toLowerCase().startsWith("udp") ? "udp" : "tcp";
      const port = Number(item.port.payload.port);
      const key = listenerKey(rawProtocol, port);
      const process = item.port.payload.process as { comm?: string; cmdline?: string } | null;
      const exposure = exposureOf(address);
      const current = grouped.get(key) ?? {
        key,
        port,
        protocol,
        addresses: [],
        exposure,
        owner: textOf(process?.comm),
        appId: item.appId,
        appName: item.appName,
        command: textOf(process?.cmdline),
        orphan: !process && !item.appId,
      };
      if (address && !current.addresses.includes(address)) current.addresses.push(address);
      if (exposure === "external") current.exposure = "external";
      else if (exposure === "lan" && current.exposure === "local") current.exposure = "lan";
      if (item.appName) {
        current.appName = item.appName;
        current.appId = item.appId;
        current.orphan = false;
      }
      if (process?.comm) current.owner = textOf(process.comm);
      grouped.set(key, current);
    }
    const rank = (row: Row) => (row.orphan && row.exposure === "external" ? 0 : row.exposure === "external" ? 1 : row.exposure === "lan" ? 2 : 3);
    return [...grouped.values()]
      .filter((row) => !appFilter || row.appId === appFilter)
      .sort((a, b) => rank(a) - rank(b) || a.port - b.port);
  });

  const shown = $derived(
    rows.filter((row) => {
      if (filter === "all") return true;
      if (filter === "orphan") return row.orphan;
      return row.exposure === filter;
    }),
  );
  const counts = $derived({
    external: rows.filter((row) => row.exposure === "external").length,
    local: rows.filter((row) => row.exposure === "local").length,
    orphan: rows.filter((row) => row.orphan).length,
  });
  const firewall = $derived(data ? chooseFirewall(data.firewall) : null);
  const open = $derived(shown.find((row) => row.key === picked) ?? null);

  onMount(() => {
    void loadPanel()
      .then((body) => {
        data = body;
      })
      .catch((error: unknown) => {
        errorMessage = shownError(error, lang);
      });
  });

  function exposureLabel(kind: Exposure): string {
    if (kind === "external") return copy(lang, "fromInternet");
    if (kind === "lan") return copy(lang, "fromLan");
    return copy(lang, "onlyServer");
  }
</script>

<section class="atlas-fade-in">
  <h1 class="screen-title mb-4">{copy(lang, "network")}</h1>
  {#if appFilter}
    <p class="chip mb-4">
      {copy(lang, "appFilter")}: {data?.apps.find((item) => item.id === appFilter)?.name ?? appFilter}
      <button type="button" class="ml-2" onclick={() => selectedApp.set("")}>{copy(lang, "clearApp")}</button>
    </p>
  {/if}
  {#if errorMessage}
    <div class="card"><p>{errorMessage}</p></div>
  {:else}
    <div class="mb-4 grid gap-3 sm:grid-cols-3">
      <button type="button" class="card text-left" onclick={() => (filter = filter === "external" ? "all" : "external")}>
        <p class="kicker">{copy(lang, "portsInternet")}</p>
        <p class="mt-2 text-2xl text-paper">{counts.external}</p>
      </button>
      <button type="button" class="card text-left" onclick={() => (filter = filter === "local" ? "all" : "local")}>
        <p class="kicker">{copy(lang, "portsLocal")}</p>
        <p class="mt-2 text-2xl text-paper">{counts.local}</p>
      </button>
      <button type="button" class="card text-left" onclick={() => (filter = filter === "orphan" ? "all" : "orphan")}>
        <p class="kicker">{copy(lang, "portsOrphan")}</p>
        <p class="mt-2 text-2xl text-paper">{counts.orphan}</p>
      </button>
    </div>
    <p class="kicker mb-3">
      {copy(lang, "sortRisk")} · {copy(lang, "mergeV4")}
      {#if !firewall} · {copy(lang, "firewallNote")}{/if}
    </p>
    <div class="card overflow-auto p-0">
      <table class="data-table">
        <thead>
          <tr>
            <th>{copy(lang, "portWord")}</th>
            <th>{copy(lang, "whoListens")}</th>
            <th>{copy(lang, "whoConnects")}</th>
            <th>{copy(lang, "needed")}</th>
          </tr>
        </thead>
        <tbody>
          {#each shown as row (row.key)}
            <tr class="clickable" onclick={() => (picked = row.key)}>
              <td>
                <span class="mono text-paper">{row.port} · {row.protocol.toUpperCase()}</span>
                {#if portHint(row.port, lang)}<span class="mt-1 block text-xs text-fog">{portHint(row.port, lang)}</span>{/if}
              </td>
              <td>
                {#if row.appId}<a class="text-info" href={`#/apps/${row.appId}/network`}>{row.appName}</a>{/if}
                <span class="block">{row.owner || copy(lang, "ownerUnknown")}</span>
                {#if row.orphan}<Mark {lang} kind="unknown" value={copy(lang, "ownerUnknown")} how={copy(lang, "noProcess")} />{/if}
              </td>
              <td>
                <span class="chip {row.exposure === 'external' ? 'warn' : ''}">{exposureLabel(row.exposure)}</span>
                {#if row.exposure === "external" && firewall}
                  {@const mark = portFirewall(row.exposure, row.protocol, row.port, firewall)}
                  {#if mark === "allowed"}
                    <span class="mt-1 block text-xs text-fog">{copy(lang, "firewallAllowed")}</span>
                  {:else if mark === "missing"}
                    <span class="mt-1 block text-xs text-fog">{copy(lang, "firewallMissing")}</span>
                  {/if}
                {/if}
              </td>
              <td>{row.orphan ? copy(lang, "checkThis") : "—"}</td>
            </tr>
          {:else}
            <tr><td colspan="4" class="text-fog">{copy(lang, "empty")}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

{#if open}
  <button type="button" class="scrim" aria-label={copy(lang, "close")} onclick={() => (picked = "")}></button>
  <div class="drawer" role="dialog" aria-label={copy(lang, "portWord")}>
    <div class="mb-4 flex items-center justify-between">
      <h2 class="block-title">{open.port}</h2>
      <button type="button" class="btn btn-ghost" onclick={() => (picked = "")}>{copy(lang, "close")}</button>
    </div>
    <p class="kicker">{copy(lang, "addressesLabel")}</p>
    <ul class="mb-4">{#each open.addresses as address (address)}<li class="mono">{address}</li>{/each}</ul>
    <p class="kicker">{copy(lang, "commandLabel")}</p>
    <p class="mono mb-3 break-all">{open.command || copy(lang, "noProcess")}</p>
    {#if open.command}<CopyButton {lang} text={open.command} />{/if}
    {#if open.appId}<p class="mt-4"><a class="text-info" href={`#/apps/${open.appId}/summary`}>{copy(lang, "openApp")}</a></p>{/if}
    <p class="mt-4 text-sm text-fog">{copy(lang, "closePortNone")}</p>
    <details class="mt-6">
      <summary class="kicker cursor-pointer">{copy(lang, "outbound")}</summary>
      <p class="mt-2 text-sm text-fog">{copy(lang, "outboundHint")}</p>
    </details>
  </div>
{/if}
