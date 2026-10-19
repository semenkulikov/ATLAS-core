<script lang="ts">
  import { onMount } from "svelte";
  import Access from "./Access.svelte";
  import Apps from "./Apps.svelte";
  import Events from "./Events.svelte";
  import Logs from "./Logs.svelte";
  import Monitor from "./Monitor.svelte";
  import Network from "./Network.svelte";
  import Overview from "./Overview.svelte";
  import Settings from "./Settings.svelte";
  import System from "./System.svelte";
  import { api, type Account } from "./api";
  import { exposureOf, textOf } from "./format";
  import { copy, hashFor, navRoutes, parseHash, type Lang, type Place, type RouteId } from "./i18n";
  import { loadPanel, refreshedAt, type PanelData } from "./inventory";
  import { proof } from "./proof";
  import { selectedApp } from "./selection";
  import Icon from "./ui/Icon.svelte";

  let { account, onsignedout }: { account: Account; onsignedout: () => Promise<void> } = $props();
  let lang = $state<Lang>(localStorage.getItem("atlas.lang") === "en" ? "en" : "ru");
  let place = $state<Place>(parseHash(location.hash));
  let collapsed = $state(false);
  let palette = $state(false);
  let help = $state(false);
  let more = $state(false);
  let menu = $state(false);
  let switcher = $state(false);
  let query = $state("");
  let panel = $state<PanelData | null>(null);
  let armed = $state("");
  const phoneNav = ["overview", "apps", "monitoring", "network"] as const;
  const letters: Record<string, RouteId> = {
    o: "overview",
    a: "apps",
    m: "monitoring",
    n: "network",
    u: "access",
    l: "logs",
    e: "events",
    s: "settings",
    y: "system",
  };

  const icons: Record<string, string> = {
    overview: "overview",
    apps: "apps",
    monitoring: "monitoring",
    network: "network",
    access: "access",
    logs: "logs",
    events: "events",
    settings: "settings",
    system: "settings",
  };

  const orphanPorts = $derived(
    (panel?.system.ports ?? []).filter(
      (row) => exposureOf(textOf(row.payload.address)) === "external" && !row.payload.process,
    ).length,
  );
  const currentApp = $derived(panel?.apps.find((item) => item.id === $selectedApp) ?? null);
  const foundApps = $derived(
    (panel?.apps ?? []).filter((item) => item.name.toLowerCase().includes(query.trim().toLowerCase())),
  );

  function go(id: RouteId): void {
    location.hash = id === "system" ? "#/system/services" : `#/${id}`;
    palette = false;
    more = false;
    query = "";
  }

  function setLang(next: Lang): void {
    lang = next;
    localStorage.setItem("atlas.lang", next);
    document.documentElement.lang = next;
  }

  function toggleNav(): void {
    collapsed = !collapsed;
    localStorage.setItem("atlas.nav", collapsed ? "1" : "0");
  }

  function sync(): void {
    const next = parseHash(location.hash);
    place = next;
    if (!location.hash || location.hash === "#" || location.hash === "#/") return;
    const canonical = hashFor(next);
    if (location.hash !== canonical) history.replaceState(null, "", canonical);
  }

  onMount(() => {
    const stored = localStorage.getItem("atlas.nav");
    const wide = window.matchMedia("(min-width: 1280px)").matches;
    collapsed = stored === null ? !wide : stored === "1";
    document.documentElement.lang = lang;
    sync();
    void loadPanel()
      .then((body) => {
        panel = body;
      })
      .catch(() => undefined);
    const onHash = () => sync();
    const onKey = (event: KeyboardEvent) => {
      const typing = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        palette = !palette;
        return;
      }
      if (event.key === "Escape") {
        palette = false;
        help = false;
        more = false;
        menu = false;
        switcher = false;
        proof.set(null);
        return;
      }
      if (typing) return;
      if (event.key === "[") {
        toggleNav();
        return;
      }
      if (event.key === "?") {
        help = !help;
        return;
      }
      const target = letters[event.key];
      if (armed === "g" && target) {
        go(target);
        armed = "";
        return;
      }
      armed = event.key === "g" ? "g" : "";
    };
    window.addEventListener("hashchange", onHash);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("keydown", onKey);
    };
  });

  async function logout(): Promise<void> {
    await api("/api/v1/auth/logout", { method: "POST" });
    await onsignedout();
  }
</script>

<a class="skip" href="#content">{copy(lang, "skipContent")}</a>
<div class="shell {collapsed ? 'is-collapsed' : ''}">
  <nav class="side" aria-label={copy(lang, "navLabel")}>
    <p class="nav-label px-2 pb-2 text-sm font-medium text-paper">{copy(lang, "product")}</p>
    {#each navRoutes as id (id)}
      <a class="nav-item" href={`#/${id}`} aria-current={place.route === id ? "page" : undefined} title={copy(lang, id)}>
        <Icon name={icons[id]} />
        <span class="nav-label">{copy(lang, id)}</span>
        {#if id === "network" && orphanPorts > 0}
          <span class="badge">{orphanPorts}</span>
        {/if}
      </a>
    {/each}
    <div class="side-foot">
      <p class="side-foot-text flex items-center gap-2 text-xs text-fog">
        <span class="dot ok"></span>
        <span class="truncate">{panel?.hostname || copy(lang, "serverName")}</span>
      </p>
      <button type="button" class="btn btn-ghost" onclick={toggleNav} title={collapsed ? copy(lang, "expand") : copy(lang, "collapse")}>
        {collapsed ? "»" : copy(lang, "collapse")}
      </button>
    </div>
  </nav>
  <div class="workspace">
    <header class="topbar">
      <div class="relative">
        <button type="button" class="btn btn-secondary w-full justify-between" onclick={() => (switcher = !switcher)}>
          <span class="truncate">{currentApp ? currentApp.name : copy(lang, "allApps")}</span>
        </button>
        {#if switcher}
          <div class="menu mt-2 w-full">
            <input class="mb-2 h-8 w-full rounded-md border border-smoke bg-void px-2 text-sm" placeholder={copy(lang, "switcherSearch")} bind:value={query} />
            <button type="button" class="btn btn-ghost w-full justify-start" onclick={() => { selectedApp.set(""); switcher = false; }}>
              {copy(lang, "allApps")}
            </button>
            {#each panel?.apps ?? [] as item (item.id)}
              <button
                type="button"
                class="btn btn-ghost w-full justify-start"
                onclick={() => {
                  selectedApp.set(item.id);
                  switcher = false;
                  if (place.route === "overview") location.hash = `#/apps/${item.id}/summary`;
                }}
              >
                {item.name}
              </button>
            {/each}
          </div>
        {/if}
      </div>
      <button type="button" class="search-btn btn btn-secondary hidden justify-start md:flex" onclick={() => (palette = true)}>
        <Icon name="search" />
        {copy(lang, "searchPlaceholder")}
      </button>
      <div class="flex items-center justify-end gap-2">
        <button type="button" class="btn btn-ghost md:hidden" onclick={() => (palette = true)} aria-label={copy(lang, "search")}>
          <Icon name="search" />
        </button>
        <span class="hidden items-center gap-2 sm:inline-flex">
          <span class="dot {$refreshedAt ? 'ok' : ''}"></span>
          <span class="kicker">{copy(lang, "liveWord")}</span>
        </span>
        <div class="relative">
          <button type="button" class="btn btn-ghost" onclick={() => (menu = !menu)} aria-label={copy(lang, "userMenu")}>
            <Icon name="user" />
          </button>
          {#if menu}
            <div class="menu right-0 mt-2">
              <p class="px-2 py-1 text-sm text-paper">{account.username}</p>
              <button type="button" class="btn btn-ghost w-full justify-start" onclick={() => setLang(lang === "ru" ? "en" : "ru")}>
                {lang === "ru" ? "EN" : "RU"}
              </button>
              <button type="button" class="btn btn-ghost w-full justify-start" onclick={() => void logout()}>{copy(lang, "signOut")}</button>
            </div>
          {/if}
        </div>
      </div>
    </header>
    <main id="content" class="canvas">
      <div class="canvas-inner">
        {#key `${place.route}:${place.appId}:${place.tab}:${lang}`}
          <div class="atlas-fade-in">
            {#if place.route === "overview"}
              <Overview {lang} canScan={account.role === "owner"} />
            {:else if place.route === "apps"}
              <Apps {lang} appId={place.appId} tab={place.tab} role={account.role} />
            {:else if place.route === "monitoring"}
              <Monitor {lang} />
            {:else if place.route === "network"}
              <Network {lang} />
            {:else if place.route === "access"}
              <Access {lang} />
            {:else if place.route === "logs"}
              <Logs {lang} />
            {:else if place.route === "events"}
              <Events {lang} />
            {:else if place.route === "settings"}
              <Settings {lang} role={account.role} onlang={setLang} />
            {:else}
              <System {lang} tab={place.tab} />
            {/if}
          </div>
        {/key}
      </div>
    </main>
  </div>
</div>

<nav class="tabbar" aria-label={copy(lang, "navLabel")}>
  {#each phoneNav as id (id)}
    <a href={`#/${id}`} aria-current={place.route === id ? "page" : undefined}>
      <Icon name={icons[id]} />
      {copy(lang, id)}
    </a>
  {/each}
  <button type="button" class="text-fog" onclick={() => (more = !more)}>
    <Icon name="more" />
    {copy(lang, "navMore")}
    {#if orphanPorts > 0}<span class="badge">{orphanPorts}</span>{/if}
  </button>
</nav>

{#if more}
  <div class="drawer" role="dialog" aria-label={copy(lang, "moreSheet")}>
    {#each ["access", "logs", "events", "settings", "system"] as id (id)}
      <a class="nav-item" href={id === "system" ? "#/system/services" : `#/${id}`} onclick={() => (more = false)}>
        {copy(lang, id as RouteId)}
      </a>
    {/each}
  </div>
{/if}

{#if palette}
  <div class="atlas-backdrop-in fixed inset-0 z-30 grid place-items-start bg-void/80 px-4 pt-24" role="dialog" aria-modal="true" aria-label={copy(lang, "search")}>
    <div class="card mx-auto w-full max-w-lg">
      <input class="h-10 w-full rounded-md border border-smoke bg-void px-3" bind:value={query} placeholder={copy(lang, "searchPlaceholder")} />
      <p class="kicker mt-3">{copy(lang, "navLabel")}</p>
      {#each navRoutes.filter((id) => copy(lang, id).toLowerCase().includes(query.toLowerCase())) as id (id)}
        <button type="button" class="btn btn-ghost w-full justify-start" onclick={() => go(id)}>{copy(lang, id)}</button>
      {/each}
      <p class="kicker mt-3">{copy(lang, "apps")}</p>
      {#each foundApps.slice(0, 6) as item (item.id)}
        <button type="button" class="btn btn-ghost w-full justify-start" onclick={() => { location.hash = `#/apps/${item.id}/summary`; palette = false; }}>
          {item.name}
        </button>
      {/each}
    </div>
  </div>
{/if}

{#if help}
  <div class="atlas-backdrop-in fixed inset-0 z-30 grid place-items-center bg-void/80 p-4" role="dialog" aria-modal="true" aria-label={copy(lang, "shortcuts")}>
    <div class="card w-full max-w-md">
      <h2 class="block-title mb-3">{copy(lang, "shortcuts")}</h2>
      <ul class="space-y-2 text-sm">
        <li>Ctrl+K · {copy(lang, "search")}</li>
        <li>[ · {copy(lang, "collapse")}</li>
        <li>g {copy(lang, "press")} o · {copy(lang, "overview")}</li>
        <li>g {copy(lang, "press")} l · {copy(lang, "logs")}</li>
        <li>? · {copy(lang, "helpKeys")}</li>
      </ul>
      <button type="button" class="btn btn-secondary mt-4" onclick={() => (help = false)}>{copy(lang, "close")}</button>
    </div>
  </div>
{/if}

{#if $proof}
  <div class="drawer" role="dialog" aria-modal="true" aria-label={copy(lang, "showProof")}>
    <div class="mb-4 flex items-center justify-between">
      <h2 class="block-title">{copy(lang, "showProof")}</h2>
      <button type="button" class="btn btn-ghost" onclick={() => proof.set(null)}>{copy(lang, "close")}</button>
    </div>
    <p class="kicker">{copy(lang, "whatShown")}</p>
    <p class="mt-1 text-paper">{$proof.value}</p>
    <p class="kicker mt-4">{copy(lang, "howKnown")}</p>
    <p class="mono mt-1 break-all">{$proof.how}</p>
    <p class="kicker mt-4">{copy(lang, "howSure")}</p>
    <p class="mt-1">
      {copy(lang, $proof.kind === "fact" ? "proofKindFact" : $proof.kind === "derived" ? "proofKindDerived" : "proofKindUnknown")}
    </p>
    {#if $proof.at}<p class="kicker mt-3">{copy(lang, "collected")} {$proof.at}</p>{/if}
  </div>
{/if}

