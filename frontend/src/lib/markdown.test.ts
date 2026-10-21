import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

describe("markdown", () => {
  it("renders headings and emphasis without raw html", () => {
    const html = renderMarkdown("# Ledger\n\nA **bold** and *lean* note.\n\n<script>alert(1)</script>\n");
    expect(html).toContain("<h1>Ledger</h1>");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<em>lean</em>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("keeps a safe link and drops a script url", () => {
    const html = renderMarkdown("[docs](https://example.test/ledger) [bad](javascript:alert(1))");
    expect(html).toContain('href="https://example.test/ledger"');
    expect(html).not.toContain("javascript:");
  });
});
