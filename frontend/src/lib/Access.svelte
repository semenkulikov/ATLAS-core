<script lang="ts">
  import { onMount } from "svelte";
  import { isSystemUser } from "./apps";
  import { shownError } from "./api";
  import { textOf } from "./format";
  import { copy, type Lang } from "./i18n";
  import { loadPanel, type PanelData } from "./inventory";
  import CopyButton from "./ui/CopyButton.svelte";
  import Mark from "./ui/Mark.svelte";

  let { lang }: { lang: Lang } = $props();
  let data = $state<PanelData | null>(null);
  let errorMessage = $state("");
  let systemOpen = $state(false);
  let openUser = $state("");

  const people = $derived((data?.users ?? []).filter((row) => !isSystemUser(row) || row.key === "root" || Number(row.payload.uid) === 0));
  const system = $derived((data?.users ?? []).filter((row) => isSystemUser(row) && row.key !== "root"));

  onMount(() => {
    void loadPanel()
      .then((body) => {
        data = body;
      })
      .catch((error: unknown) => {
        errorMessage = shownError(error, lang);
      });
  });

  function keysFor(user: string): number {
    return (data?.keys ?? []).filter((row) => row.payload.user === user).length;
  }

  function sudo(row: { payload: Record<string, unknown> }): boolean {
    const value = row.payload.sudo;
    if (!Array.isArray(value) || value.length === 0) return false;
    return textOf(value[0]) !== "not listed";
  }

  function docker(row: { payload: Record<string, unknown> }): boolean {
    const groups = row.payload.groups;
    return Array.isArray(groups) && groups.map((item) => textOf(item)).includes("docker");
  }

  function rootLine(value: string | undefined): string {
    const text = (value ?? "").toLowerCase();
    if (!text) return copy(lang, "sshUnchecked");
    if (text === "yes") return copy(lang, "sshRootPassword");
    if (text === "no") return copy(lang, "sshRootDenied");
    return copy(lang, "sshRootKey");
  }
</script>

<section class="atlas-fade-in">
  <h1 class="screen-title mb-4">{copy(lang, "access")}</h1>
  {#if errorMessage}
    <div class="card"><p>{errorMessage}</p></div>
  {:else if data}
    <div class="card mb-4 grid gap-3">
      <p>{rootLine(data.sshd.permit_root_login)} <Mark {lang} kind={data.sshd.permit_root_login ? "fact" : "unknown"} value={rootLine(data.sshd.permit_root_login)} how="/etc/ssh/sshd_config" /></p>
      <p>
        {data.sshd.password_authentication
          ? data.sshd.password_authentication.toLowerCase() === "no"
            ? copy(lang, "sshPasswordOff")
            : copy(lang, "sshPasswordOn")
          : copy(lang, "sshUnchecked")}
      </p>
      <p class="mono">{copy(lang, "sshPortLabel")}: {data.sshd.port || copy(lang, "unknownStatus")}</p>
    </div>
    <h2 class="block-title mb-2">{copy(lang, "whoEnters")}</h2>
    <div class="card mb-4 overflow-auto p-0">
      <table class="data-table">
        <thead>
          <tr>
            <th>{copy(lang, "loginLabel")}</th>
            <th>{copy(lang, "rightsLabel")}</th>
            <th>{copy(lang, "howEnters")}</th>
            <th>{copy(lang, "lastEntered")}</th>
          </tr>
        </thead>
        <tbody>
          {#each people as row (row.key)}
            <tr class="clickable" onclick={() => (openUser = openUser === row.key ? "" : row.key)}>
              <td>
                <span class="mono text-paper">{row.key}</span>
                <span class="block text-xs text-fog">{textOf(row.payload.shell)}</span>
              </td>
              <td>
                {#if sudo(row)}<span class="chip warn">{copy(lang, "sudoAdmin")}</span>{/if}
                {#if docker(row)}<span class="chip warn">{copy(lang, "dockerGroup")}</span>{/if}
              </td>
              <td>{keysFor(row.key) ? `${copy(lang, "bySshKey")} (${keysFor(row.key)})` : copy(lang, "cannotEnter")}</td>
              <td>{copy(lang, "neverEntered")}</td>
            </tr>
            {#if openUser === row.key}
              <tr>
                <td colspan="4">
                  <p class="kicker">{copy(lang, "homeFolder")}</p>
                  <p class="mono">{textOf(row.payload.home)}</p>
                  <ul class="mt-2">
                    {#each (data.keys ?? []).filter((item) => item.payload.user === row.key) as key (key.key)}
                      <li class="mono text-sm">{textOf(key.payload.type)} {textOf(key.payload.fingerprint)} {textOf(key.payload.comment)}</li>
                    {/each}
                  </ul>
                  {#if data.keys.find((item) => item.payload.user === row.key)}
                    <CopyButton {lang} text={textOf(data.keys.find((item) => item.payload.user === row.key)?.payload.fingerprint)} label={copy(lang, "copyKey")} />
                  {/if}
                </td>
              </tr>
            {/if}
          {:else}
            <tr><td colspan="4" class="text-fog">{copy(lang, "empty")}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <h2 class="block-title mb-2">{copy(lang, "activeSessions")}</h2>
    <p class="mb-4 text-sm text-fog">{data.sessions.trim() ? data.sessions : copy(lang, "nobodyOnline")}</p>
    <section class="card">
      <button type="button" class="flex w-full items-center justify-between" onclick={() => (systemOpen = !systemOpen)} aria-expanded={systemOpen}>
        <span class="block-title">{copy(lang, "systemAccounts")} ({system.length})</span>
        <span>{systemOpen ? "–" : "+"}</span>
      </button>
      <p class="kicker mt-2">{copy(lang, "accountsHint")}</p>
      {#if systemOpen}
        <ul class="mt-3">
          {#each system as row (row.key)}
            <li class="flex justify-between py-1"><span class="mono">{row.key}</span><span class="text-fog">{textOf(row.payload.shell)}</span></li>
          {/each}
        </ul>
      {/if}
    </section>
  {:else}
    <div class="skeleton h-40"></div>
  {/if}
</section>
