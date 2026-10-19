<script lang="ts">
  import { copy, type Lang } from "../i18n";

  let { lang, text, label }: { lang: Lang; text: string; label?: string } = $props();
  let done = $state(false);

  async function copyText(): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      done = true;
      setTimeout(() => {
        done = false;
      }, 1500);
    } catch {
      done = false;
    }
  }
</script>

<button type="button" class="btn btn-ghost" onclick={() => void copyText()}>
  {done ? copy(lang, "copyDone") : (label ?? copy(lang, "copyPath"))}
</button>
