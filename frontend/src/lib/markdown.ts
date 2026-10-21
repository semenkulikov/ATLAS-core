/** A small markdown renderer. The source is escaped before any tag is added. */

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function safeHref(url: string): string | null {
  const trimmed = url.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("/") || trimmed.startsWith("#")) return trimmed;
  return null;
}

function inline(text: string): string {
  let value = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  value = value.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_match, label: string, href: string) => {
    const safe = safeHref(href);
    if (!safe) return label;
    return `<a href="${escapeHtml(safe)}" rel="noreferrer">${label}</a>`;
  });
  value = value.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  value = value.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  return value;
}

function renderBlocks(source: string): string {
  const lines = source.split("\n");
  const parts: string[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index] ?? "";
    const heading = /^(#{1,3}) (.+)$/.exec(line);
    if (heading) {
      const level = heading[1]?.length ?? 1;
      parts.push(`<h${level}>${inline(heading[2] ?? "")}</h${level}>`);
      index += 1;
      continue;
    }
    if (/^[-*] /.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*] /.test(lines[index] ?? "")) {
        items.push(`<li>${inline((lines[index] ?? "").slice(2))}</li>`);
        index += 1;
      }
      parts.push(`<ul>${items.join("")}</ul>`);
      continue;
    }
    if (/^\d+\. /.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\. /.test(lines[index] ?? "")) {
        items.push(`<li>${inline((lines[index] ?? "").replace(/^\d+\. /, ""))}</li>`);
        index += 1;
      }
      parts.push(`<ol>${items.join("")}</ol>`);
      continue;
    }
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const paragraph: string[] = [];
    while (index < lines.length && (lines[index] ?? "").trim() && !/^(#{1,3} |[-*] |\d+\. )/.test(lines[index] ?? "")) {
      paragraph.push(lines[index] ?? "");
      index += 1;
    }
    parts.push(`<p>${inline(paragraph.join(" "))}</p>`);
  }
  return parts.join("");
}

export function renderMarkdown(source: string): string {
  const escaped = escapeHtml(source).replaceAll("\r\n", "\n");
  const blocks = escaped.split("```");
  return blocks
    .map((block, index) => {
      if (index % 2 === 0) return renderBlocks(block);
      const body = block.replace(/^[^\n]*\n/, "");
      return `<pre><code>${body.replace(/```$/, "")}</code></pre>`;
    })
    .join("");
}
