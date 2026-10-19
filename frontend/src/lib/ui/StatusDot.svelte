<script lang="ts">
  let { kind, label }: { kind: "ok" | "warn" | "bad" | "unknown"; label: string } = $props();
</script>

<span class="inline-flex items-center gap-2">
  <span class="dot {kind === 'ok' ? 'ok' : kind === 'warn' ? 'warn' : kind === 'bad' ? 'bad' : ''}"></span>
  <span>{label}</span>
</span>
