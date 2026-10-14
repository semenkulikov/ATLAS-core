<script lang="ts">
  import { onMount } from "svelte";
  import Audit from "./Audit.svelte";
  import Changes from "./Changes.svelte";
  import Settings from "./Settings.svelte";
  import EvidenceDrawer from "./EvidenceDrawer.svelte";
  import Logs from "./Logs.svelte";
  import Monitor from "./Monitor.svelte";
  import Overview from "./Overview.svelte";
  import Projects from "./Projects.svelte";
  import Records from "./Records.svelte";
  import { api, type Account } from "./api";
  import { copy, routeFromHash, routes, type Lang, type RouteId } from "./i18n";

  let { account, onsignedout }: { account: Account; onsignedout: () => Promise<void> } = $props();
  let lang = $state<Lang>(localStorage.getItem("atlas.lang") === "ru" ? "ru" : "en");
  let route = $state<RouteId>("overview");
  let palette = $state(false);
  let query = $state("");
  let factId = $state<number | null>(null);
  let armed = $state("");

  const visible = $derived(
    routes.filter((id) => copy(lang, id).toLowerCase().includes(query.toLowerCase())),
  );

  function go(id: RouteId): void {
    location.hash = `#/${id}`;
    palette = false;
    query = "";
  }

  function setLang(next: Lang): void {
    lang = next;
    localStorage.setItem("atlas.lang", next);
    document.documentElement.lang = next;
  }

  onMount(() => {
    const apply = () => {
      route = routeFromHash(location.hash);
    };
    apply();
    document.documentElement.lang = lang;
    const onHash = () => apply();
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        palette = !palette;
        return;
      }
      if (event.key === "Escape") {
        palette = false;
        factId = null;
        return;
      }
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (armed === "g" && event.key === "p") {
        go("projects");
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

  function openFact(id: number): void {
    factId = id;
  }
</script>

<div class="grid h-full grid-cols-1 bg-void md:grid-cols-[220px_1fr]">
  <nav class="flex gap-1 overflow-x-auto border-b border-graphite bg-carbon p-2 md:block md:overflow-visible md:border-r md:border-b-0 md:p-3" aria-label={copy(lang, "product")}>
    <p class="hidden px-2 text-sm text-paper md:mb-4 md:block">{copy(lang, "product")}</p>
    {#each routes as id (id)}
      <a
        class="block shrink-0 rounded-md px-2 py-1.5 text-sm {route === id ? 'text-accent' : 'text-mist'}"
        href={`#/${id}`}
        aria-current={route === id ? "page" : undefined}
      >
        {copy(lang, id)}
      </a>
    {/each}
  </nav>
  <div class="flex min-w-0 flex-col {factId !== null ? 'pr-[360px]' : ''}">
    <header class="flex flex-wrap items-center justify-between gap-2 border-b border-graphite px-4 py-3">
      <p class="text-sm text-fog">{account.username} · {account.role}</p>
      <div class="flex items-center gap-3">
        <button type="button" class="rounded-md border border-graphite px-3 py-1 text-sm text-fog" onclick={() => (palette = true)}>
          {copy(lang, "palette")}
        </button>
        <button type="button" class="text-sm text-fog" onclick={() => setLang(lang === "en" ? "ru" : "en")}>
          {lang === "en" ? "RU" : "EN"}
        </button>
        <button type="button" class="text-sm text-fog" onclick={logout}>{copy(lang, "signOut")}</button>
      </div>
    </header>
    <main class="min-h-0 flex-1 overflow-auto p-6">
      {#if route === "overview"}
        <Overview {lang} />
      {:else if route === "projects"}
        <Projects {lang} onopen={openFact} />
      {:else if route === "services"}
        <h1 class="mb-4 text-2xl text-paper">{copy(lang, "services")}</h1>
        <Records {lang} path="/api/v1/services" detail="/api/v1/services" onopen={openFact} canAct={account.role !== "viewer"} />
      {:else if route === "schedules"}
        <h1 class="mb-4 text-2xl text-paper">{copy(lang, "schedules")}</h1>
        <Records {lang} path="/api/v1/schedules" detail={null} onopen={openFact} />
      {:else if route === "containers"}
        <h1 class="mb-4 text-2xl text-paper">{copy(lang, "containers")}</h1>
        <Records {lang} path="/api/v1/containers" detail="/api/v1/containers" onopen={openFact} canAct={account.role !== "viewer"} />
      {:else if route === "network"}
        <h1 class="mb-4 text-2xl text-paper">{copy(lang, "network")}</h1>
        <Records {lang} path="/api/v1/ports" detail={null} onopen={openFact} />
      {:else if route === "users"}
        <h1 class="mb-4 text-2xl text-paper">{copy(lang, "users")}</h1>
        <Records {lang} path="/api/v1/users" detail={null} onopen={openFact} />
      {:else if route === "monitoring"}
        <Monitor {lang} />
      {:else if route === "logs"}
        <Logs {lang} />
      {:else if route === "changes"}
        <Changes {lang} />
      {:else if route === "audit"}
        <Audit {lang} />
      {:else if route === "settings"}
        <Settings {lang} role={account.role} />
      {:else}
        <section>
          <h1 class="mb-4 text-2xl text-paper">{copy(lang, route)}</h1>
          <p class="max-w-xl text-sm text-fog">{copy(lang, "readOnly")}</p>
          <p class="mt-4 text-sm text-mist">{copy(lang, "role")}: {account.role}</p>
        </section>
      {/if}
    </main>
  </div>
</div>

{#if factId !== null}
  <EvidenceDrawer {factId} {lang} onclose={() => (factId = null)} />
{/if}

{#if palette}
  <div class="fixed inset-0 z-30 grid place-items-start bg-void/80 pt-24" role="dialog" aria-modal="true" aria-label={copy(lang, "palette")}>
    <div class="mx-auto w-full max-w-lg rounded-xl border border-graphite bg-obsidian p-3">
      <input class="w-full rounded-md border border-graphite bg-void px-3 py-2 text-paper" bind:value={query} placeholder={copy(lang, "search")} />
      <ul class="mt-2">
        {#each visible as id (id)}
          <li>
            <button type="button" class="w-full rounded-md px-2 py-1.5 text-left text-mist hover:bg-graphite" onclick={() => go(id)}>
              {copy(lang, id)}
            </button>
          </li>
        {/each}
      </ul>
    </div>
  </div>
{/if}
