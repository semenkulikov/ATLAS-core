<script lang="ts">
  let { name, size = 16 }: { name: string; size?: number } = $props();
  const paths: Record<string, string> = {
    overview: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
    apps: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
    monitoring: "M4 16l4-5 3 3 5-7 4 4",
    network: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.8 2.5 15.2 0 18M12 3c-2.5 2.8-2.5 15.2 0 18",
    access: "M12 12a3.5 3.5 0 1 0-3.5-3.5A3.5 3.5 0 0 0 12 12zm-7 8a7 7 0 0 1 14 0",
    logs: "M6 4h9l3 3v13H6zM9 12h6M9 16h6",
    events: "M12 7v6l4 2M12 3a9 9 0 1 0 9 9",
    settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 12h2M18 12h2M12 4v2M12 18v2",
    search: "M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM20 20l-3.5-3.5",
    more: "M6 12h.01M12 12h.01M18 12h.01",
    user: "M12 12a3.5 3.5 0 1 0-3.5-3.5A3.5 3.5 0 0 0 12 12zM5 20a7 7 0 0 1 14 0",
    close: "M6 6l12 12M18 6 6 18",
    copy: "M8 8h10v12H8zM6 16H5a1 1 0 0 1-1-1V4h10v1",
    chevron: "M9 6l6 6-6 6",
    globe: "M12 3a9 9 0 1 0 .01 18.01A9 9 0 0 0 12 3zM3 12h18",
    lock: "M8 11V8a4 4 0 0 1 8 0v3M7 11h10v9H7z",
  };
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d={paths[name] ?? paths.overview} />
</svg>
