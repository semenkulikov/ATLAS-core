<script lang="ts">
  import { copy, type Lang } from "../i18n";
  import { proof, type ProofKind } from "../proof";

  let {
    lang,
    kind,
    value,
    how,
    at = "",
  }: { lang: Lang; kind: ProofKind; value: string; how: string; at?: string } = $props();

  const glyph = $derived(kind === "fact" ? "✓" : kind === "derived" ? "ƒ" : "?");
  const title = $derived(copy(lang, kind === "fact" ? "factShort" : kind === "derived" ? "derivedShort" : "unknownShort"));
</script>

<button
  type="button"
  class="btn-ghost inline-flex h-6 items-center gap-1 rounded px-1 text-xs text-info"
  title={title}
  aria-label={copy(lang, "showProof")}
  onclick={() => proof.set({ value, how, kind, at })}
>
  <span aria-hidden="true">{glyph}</span>
</button>
