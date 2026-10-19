<script lang="ts">
  import { onMount } from "svelte";
  import Auth from "./lib/Auth.svelte";
  import Shell from "./lib/Shell.svelte";
  import { ApiError, api, type Account } from "./lib/api";

  let phase = $state<"loading" | "anon" | "in">("loading");
  let account = $state<Account | null>(null);
  let message = $state("");

  async function refresh(): Promise<void> {
    try {
      account = await api<Account>("/api/v1/me");
      phase = "in";
      message = "";
    } catch (error) {
      phase = "anon";
      account = null;
      if (!(error instanceof ApiError) || error.status !== 401) {
        message = error instanceof Error ? error.message : "";
      }
    }
  }

  onMount(() => {
    void refresh();
  });
</script>

{#if phase === "loading"}
  <main class="grid min-h-full place-items-center bg-void">
    <div class="skeleton h-64 w-full max-w-md" aria-hidden="true"></div>
  </main>
{:else if phase === "anon" || account === null}
  <Auth {message} onready={refresh} />
{:else}
  <Shell {account} onsignedout={refresh} />
{/if}
