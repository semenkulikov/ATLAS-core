import { describe, expect, it } from "vitest";
import { exposureOf, formatBytes, formatPercent, formatUptime } from "./format";

describe("human units", () => {
  it("turns raw uptime seconds into days", () => {
    expect(formatUptime(12451776.21, "ru")).toBe("144 дня");
    expect(formatUptime(12451776.21, "en")).toBe("144 days");
    expect(formatUptime(50, "ru")).toBe("меньше минуты");
  });

  it("uses binary sizes and a percent sign", () => {
    expect(formatBytes(312 * 1024 * 1024, "ru")).toBe("312 МБ");
    expect(formatPercent(4.2, "ru")).toBe("4,2%");
    expect(formatPercent(88, "en")).toBe("88%");
  });

  it("treats the whole loopback range as this server only", () => {
    expect(exposureOf("127.0.0.53")).toBe("local");
    expect(exposureOf("127.0.1.1")).toBe("local");
    expect(exposureOf("::1")).toBe("local");
    expect(exposureOf("0.0.0.0")).toBe("external");
    expect(exposureOf("::")).toBe("external");
    expect(exposureOf("10.0.0.5")).toBe("lan");
  });
});
