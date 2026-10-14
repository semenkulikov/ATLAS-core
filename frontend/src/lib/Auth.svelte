<script lang="ts">
  import { ApiError, api } from "./api";
  import { copy, type Lang } from "./i18n";

  let { message = "", onready }: { message?: string; onready: () => Promise<void> } = $props();
  let lang = $state<Lang>("en");
  let mode = $state<"login" | "enroll" | "confirm">("login");
  let username = $state("");
  let password = $state("");
  let code = $state("");
  let token = $state("");
  let secret = $state("");
  let error = $state("");
  let busy = $state(false);

  function text(key: Parameters<typeof copy>[1]): string {
    return copy(lang, key);
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    error = "";
    try {
      if (mode === "login") {
        await api("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ username, password, code }),
        });
        await onready();
      } else if (mode === "enroll") {
        const started = await api<{ enrollment_token: string; otpauth_uri: string }>(
          "/api/v1/auth/bootstrap",
          { method: "POST", body: JSON.stringify({ token, username, password }) },
        );
        token = started.enrollment_token;
        secret = new URL(started.otpauth_uri).searchParams.get("secret") ?? started.otpauth_uri;
        mode = "confirm";
      } else {
        await api("/api/v1/auth/enroll", {
          method: "POST",
          body: JSON.stringify({ token, code }),
        });
        await onready();
      }
    } catch (caught) {
      error = caught instanceof ApiError ? caught.message : text("error");
    } finally {
      busy = false;
    }
  }
</script>

<main class="grid min-h-full place-items-center bg-void px-4">
  <form class="w-full max-w-md rounded-xl border border-graphite bg-carbon p-6" onsubmit={submit}>
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-xl text-paper">{text("product")}</h1>
      <button
        type="button"
        class="text-sm text-fog"
        onclick={() => (lang = lang === "en" ? "ru" : "en")}
      >
        {lang === "en" ? "RU" : "EN"}
      </button>
    </div>
    {#if mode !== "confirm"}
      <label class="mb-3 block text-sm text-fog">
        {text("username")}
        <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 text-paper" bind:value={username} autocomplete="username" />
      </label>
      <label class="mb-3 block text-sm text-fog">
        {text("password")}
        <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 text-paper" type="password" bind:value={password} autocomplete="current-password" />
      </label>
    {/if}
    {#if mode === "enroll"}
      <label class="mb-3 block text-sm text-fog">
        {text("enrollToken")}
        <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-sm text-paper" bind:value={token} />
      </label>
    {:else}
      <label class="mb-3 block text-sm text-fog">
        {text("code")}
        <input class="mt-1 w-full rounded-md border border-graphite bg-void px-3 py-2 font-mono text-paper" inputmode="numeric" bind:value={code} />
      </label>
    {/if}
    {#if secret}
      <p class="mb-3 break-all rounded-md border border-dashed border-ash p-3 font-mono text-xs text-fog">{secret}</p>
    {/if}
    {#if error || message}
      <p class="mb-3 text-sm text-crit" role="alert">{error || message}</p>
    {/if}
    <button class="w-full rounded-md bg-accent px-3 py-2 text-void" type="submit" disabled={busy}>
      {mode === "confirm" ? text("confirm") : mode === "enroll" ? text("continue") : text("signIn")}
    </button>
    <button
      class="mt-3 w-full text-sm text-fog"
      type="button"
      onclick={() => (mode = mode === "login" ? "enroll" : "login")}
    >
      {mode === "login" ? text("enroll") : text("signIn")}
    </button>
  </form>
</main>
