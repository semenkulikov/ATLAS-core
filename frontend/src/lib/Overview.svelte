<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { hasPublicPort, portList, statusLabel, statusTone, type AppModel } from "./apps";
  import { api, shownError } from "./api";
  import { exposureOf, formatBitrate, formatBytes, formatPercent, formatUptime, formatWhen, textOf } from "./format";
  import { copy, type Lang } from "./i18n";
  import { loadPanel, type PanelData } from "./inventory";
  import Mark from "./ui/Mark.svelte";
  import MiniBar from "./ui/MiniBar.svelte";
  import Ring from "./ui/Ring.svelte";
  import StatusDot from "./ui/StatusDot.svelte";

  let { lang, canScan = false }: { lang: Lang; canScan?: boolean } = $props();
  let data = $state<PanelData | null>(null);
  let missing = $state(false);
  let errorMessage = $state("");
  let busy = $state(false);
  let about = $state(false);
  let cpu = $state<number | null>(null);
  let netIn = $state<number | null>(null);
  let netOut = $state<number | null>(null);
  let risks = $state<{ kind: string; name: string }[]>([]);
  let timer: ReturnType<typeof setInterval> | undefined;

  const memPct = $derived(
    data && data.memTotal && data.memAvail !== null ? ((data.memTotal - data.memAvail) / data.memTotal) * 100 : null,
  );
  const diskPct = $derived(
    data && data.diskTotal && data.diskFree !== null ? ((data.diskTotal - data.diskFree) / data.diskTotal) * 100 : null,
  );

  const attention = $derived.by(() => {
    if (!data) return [];
    const rows: { level: "bad" | "warn"; text: string; href: string }[] = [];
    for (const app of data.apps) {
      const stopped = app.containers.filter((row) => textOf(row.payload.state).toLowerCase() !== "running" && textOf(row.payload.state));
      if (app.status === "down" || stopped.length > 0) {
        rows.push({
          level: "bad",
          text: `${app.name}: ${stopped.length || app.services.length} ${copy(lang, "attentionStopped")}`,
          href: `#/apps/${app.id}/running`,
        });
      }
    }
    if (diskPct !== null && diskPct >= 85) {
      rows.push({
        level: diskPct >= 95 ? "bad" : "warn",
        text: `${copy(lang, "attentionDisk")} ${formatPercent(diskPct, lang)}`,
        href: "#/monitoring",
      });
    }
    if (memPct !== null && memPct >= 90) {
      rows.push({ level: "warn", text: copy(lang, "attentionMemory"), href: "#/monitoring" });
    }
    for (const port of data.system.ports) {
      if (exposureOf(textOf(port.payload.address)) !== "external") continue;
      if (port.payload.process) continue;
      rows.push({
        level: "warn",
        text: `${copy(lang, "portWord")} ${port.payload.port} ${copy(lang, "attentionOrphan")}`,
        href: "#/network",
      });
    }
    if (data.sshd.permit_root_login?.toLowerCase() === "yes") {
      rows.push({ level: "warn", text: copy(lang, "attentionRoot"), href: "#/access" });
    }
    for (const risk of risks) {
      if (risk.kind !== "service") continue;
      rows.push({
        level: "warn",
        text: `${risk.name} ${copy(lang, "attentionBoot")}`,
        href: "#/system/services",
      });
    }
    if (data.collectedAt && Date.now() - Date.parse(data.collectedAt) > 15 * 60 * 1000) {
      rows.push({
        level: "bad",
        text: `${copy(lang, "attentionStale")} ${formatWhen(data.collectedAt, lang)}`,
        href: "#/overview",
      });
    }
    return rows.slice(0, 5);
  });

  const ordered = $derived.by(() => {
    if (!data) return [];
    const rank = { down: 0, partial: 1, unknown: 2, running: 3 };
    return [...data.apps].sort((a, b) => rank[a.status] - rank[b.status] || b.containers.length - a.containers.length);
  });

  async function load(): Promise<void> {
    try {
      data = await loadPanel();
      missing = false;
      errorMessage = "";
      void api<{ series: string[] }>("/api/v1/metrics/series")
        .then(async (body) => {
          if (body.series.includes("host.cpu.idle")) {
            const end = Math.floor(Date.now() / 1000);
            const points = await api<{ points: { value: number }[] }>(
              `/api/v1/metrics/query?series=host.cpu.idle&start=${end - 120}&end=${end}&step=10`,
            );
            const last = points.points.at(-1);
            if (last) cpu = Math.max(0, Math.min(100, 100 - last.value));
          }
        })
        .catch(() => undefined);
      void api<{ risks: { kind: string; name: string }[] }>("/api/v1/control")
        .then((body) => {
          risks = body.risks;
        })
        .catch(() => {
          risks = [];
        });
    } catch (error) {
      missing = shownError(error, lang) === copy(lang, "noScan");
      if (!data) errorMessage = missing ? "" : shownError(error, lang);
    }
  }

  async function runScan(): Promise<void> {
    busy = true;
    try {
      await api("/api/v1/scans", { method: "POST", body: "{}" });
      await load();
    } catch (error) {
      errorMessage = shownError(error, lang);
    } finally {
      busy = false;
    }
  }

  function memText(app: AppModel): string {
    return "—";
  }

  onMount(() => {
    void load();
    const tick = () => {
      if (document.visibilityState === "visible") void load();
    };
    timer = setInterval(tick, 5000);
  });

  onDestroy(() => clearInterval(timer));

  const headline = $derived(
    data ? `${data.os || copy(lang, "unknownStatus")} · ${data.virt || copy(lang, "unknownStatus")} · ${copy(lang, "workingNow")} ${formatUptime(data.uptimeRaw, lang) || copy(lang, "unknownStatus")}` : "",
  );
</script>

<section class="atlas-fade-in">
  {#if !data && !errorMessage && !missing}
    <div class="grid gap-4 md:grid-cols-4">
      {#each [0, 1, 2, 3] as item (item)}
        <div class="skeleton h-36"></div>
      {/each}
    </div>
  {:else if missing}
    <div class="card max-w-xl">
      <h1 class="screen-title">{copy(lang, "noScan")}</h1>
      <p class="mt-2 text-sm text-fog">{copy(lang, "noScanHint")}</p>
      {#if canScan}
        <button type="button" class="btn btn-accent mt-4" disabled={busy} onclick={() => void runScan()}>
          {busy ? copy(lang, "scanning") : copy(lang, "runScan")}
        </button>
      {/if}
    </div>
  {:else if errorMessage && !data}
    <div class="card max-w-xl">
      <p class="text-paper">{errorMessage}</p>
      <button type="button" class="btn btn-secondary mt-4" onclick={() => void load()}>{copy(lang, "retry")}</button>
    </div>
  {:else if data}
    <header class="mb-6">
      <div class="flex flex-wrap items-center gap-3">
        <h1 class="screen-title">{data.hostname || copy(lang, "serverName")}</h1>
        {#if attention.length === 0}
          <StatusDot kind="ok" label={copy(lang, "serverFine")} />
        {:else}
          <StatusDot kind={attention.some((row) => row.level === "bad") ? "bad" : "warn"} label={`${copy(lang, "attentionCount")}: ${attention.length}`} />
        {/if}
      </div>
      <p class="mt-2 text-sm text-fog">
        {headline}
        <Mark {lang} kind="fact" value={headline} how="/etc/os-release, uname, /proc/uptime" at={data.collectedAt ?? ""} />
      </p>
    </header>

    <div class="rings mb-6 grid gap-4 md:grid-cols-4">
      <a class="card lift" href="#/monitoring">
        <Ring value={cpu} label={copy(lang, "cpu")} caption={cpu === null ? copy(lang, "unknownStatus") : `${copy(lang, "occupied")} ${formatPercent(cpu, lang)}`} />
      </a>
      <a class="card lift" href="#/monitoring">
        <Ring
          value={memPct}
          label={copy(lang, "memory")}
          caption={data.memTotal && data.memAvail !== null
            ? `${formatBytes(data.memTotal - data.memAvail, lang)} ${copy(lang, "ofTotal")} ${formatBytes(data.memTotal, lang)}`
            : copy(lang, "unknownStatus")}
        />
      </a>
      <a class="card lift" href="#/monitoring">
        <Ring
          value={diskPct}
          label={copy(lang, "disk")}
          caption={data.diskTotal && data.diskFree !== null
            ? `${formatBytes(data.diskFree, lang)} ${copy(lang, "freeLabel")} ${copy(lang, "ofTotal")} ${formatBytes(data.diskTotal, lang)}`
            : copy(lang, "unknownStatus")}
        />
      </a>
      <a class="card lift" href="#/monitoring">
        <p class="block-title">{copy(lang, "network")}</p>
        <p class="mt-6 text-sm text-paper">
          {netIn === null ? copy(lang, "unknownStatus") : `↓ ${formatBitrate(netIn, lang)} · ↑ ${formatBitrate(netOut ?? 0, lang)}`}
        </p>
        <p class="kicker mt-2">{copy(lang, "netSpeed")}</p>
      </a>
    </div>

    {#if attention.length > 0}
      <section class="card mb-6">
        <h2 class="block-title mb-3">{copy(lang, "attention")}</h2>
        <ul class="divide-y divide-smoke">
          {#each attention as row (`${row.href}:${row.text}`)}
            <li class="flex flex-wrap items-center gap-3 py-2">
              <StatusDot kind={row.level} label={row.level === "bad" ? copy(lang, "down") : copy(lang, "attention")} />
              <p class="min-w-0 flex-1 text-sm text-paper">{row.text}</p>
              <a class="btn btn-secondary" href={row.href}>{copy(lang, "openItem")}</a>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    <div class="mb-3 flex items-center justify-between gap-3">
      <h2 class="block-title">{copy(lang, "applications")} ({data.apps.length})</h2>
      <a class="text-sm text-info" href="#/apps">{copy(lang, "apps")} →</a>
    </div>
    <div class="mb-6 grid gap-4 md:grid-cols-2">
      {#each ordered as app, index (app.id)}
        <a class="card lift grid gap-3" href={`#/apps/${app.id}/summary`} style:animation-delay={`${index * 40}ms`}>
          <div class="flex items-center justify-between gap-2">
            <p class="text-paper">{app.name}</p>
            <StatusDot kind={statusTone(app.status)} label={statusLabel(app.status, lang)} />
          </div>
          <div class="flex flex-wrap gap-2">
            {#each app.stack.slice(0, 4) as name (name)}
              <span class="chip">{name}</span>
            {/each}
            {#if app.stack.length > 4}
              <span class="chip">+{app.stack.length - 4}</span>
            {/if}
            {#each app.envs as env (env)}
              <span class="chip">{env}</span>
            {/each}
          </div>
          <MiniBar label="CPU" text="—" percent={null} />
          <MiniBar label={copy(lang, "memory")} text={memText(app)} percent={null} />
          <p class="kicker">
            {app.containers.length} {copy(lang, "containerCount")}
            · {copy(lang, "portsWord")} {portList(app.ports).join(", ") || "—"}
            {#if hasPublicPort(app.ports)} · {copy(lang, "fromInternet")}{/if}
          </p>
        </a>
      {:else}
        <p class="text-sm text-fog">{copy(lang, "emptyApps")}</p>
      {/each}
    </div>

    <section class="card">
      <button type="button" class="flex w-full items-center justify-between text-left" onclick={() => (about = !about)} aria-expanded={about}>
        <span class="block-title">{copy(lang, "aboutServer")}</span>
        <span class="kicker">{about ? "–" : "+"}</span>
      </button>
      {#if about}
        <dl class="mt-4 grid gap-3 md:grid-cols-2">
          <div><dt class="kicker">{copy(lang, "virtWord")}</dt><dd class="text-paper">{data.virt || copy(lang, "unknownStatus")}</dd></div>
          <div><dt class="kicker">{copy(lang, "kernelWord")}</dt><dd class="mono text-paper">{data.kernel || "—"}</dd></div>
          <div><dt class="kicker">{copy(lang, "archWord")}</dt><dd class="text-paper">{data.arch || "—"}{data.cpuCount ? ` · ${data.cpuCount} ${copy(lang, "cores")}` : ""}</dd></div>
          <div><dt class="kicker">{copy(lang, "memory")}</dt><dd class="text-paper">{data.memTotal ? formatBytes(data.memTotal, lang) : "—"}</dd></div>
          <div><dt class="kicker">{copy(lang, "primaryIp")}</dt><dd class="mono text-paper">{data.ip || "—"}</dd></div>
          <div><dt class="kicker">{copy(lang, "timezoneLabel")}</dt><dd class="text-paper">{data.timezone || "—"}</dd></div>
        </dl>
        <a class="mt-4 inline-block text-sm text-info" href="#/system/services">{copy(lang, "systemServices")}</a>
      {/if}
    </section>
  {/if}
</section>
