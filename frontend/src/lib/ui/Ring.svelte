<script lang="ts">
  let { value, label, caption }: { value: number | null; label: string; caption: string } = $props();
  const radius = 32;
  const turn = 2 * Math.PI * radius;
  let offset = $state(turn);

  const tone = $derived(
    value === null ? "var(--color-ash)" : value >= 90 ? "var(--color-crit)" : value >= 70 ? "var(--color-warn)" : "var(--color-ok)",
  );

  $effect(() => {
    const next = value === null ? turn : turn * (1 - Math.min(100, Math.max(0, value)) / 100);
    const frame = requestAnimationFrame(() => {
      offset = next;
    });
    return () => cancelAnimationFrame(frame);
  });
</script>

<div class="grid justify-items-center gap-2 text-center">
  <svg width="84" height="84" viewBox="0 0 84 84" role="img" aria-label={`${label}: ${caption}`}>
    <circle cx="42" cy="42" r={radius} fill="none" stroke="var(--color-graphite)" stroke-width="6" />
    <circle
      class="ring-arc"
      cx="42"
      cy="42"
      r={radius}
      fill="none"
      stroke={tone}
      stroke-width="6"
      stroke-linecap="round"
      stroke-dasharray={turn}
      stroke-dashoffset={offset}
    />
    <text x="42" y="46" text-anchor="middle" fill="white" font-size="16" font-weight="590">
      {value === null ? "—" : `${Math.round(value)}%`}
    </text>
  </svg>
  <p class="block-title">{label}</p>
  <p class="kicker">{caption}</p>
</div>
