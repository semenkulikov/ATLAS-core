import { describe, expect, it } from "vitest";
import { exposureOf, formatBytes, formatCount, formatPercent, formatUptime, listenerKey, readmeLead, zoneName } from "./format";

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

  it("agrees Russian counts and shows UTC without the Etc prefix", () => {
    expect(formatCount("ru", 1, "stopped")).toBe("1 остановлен");
    expect(formatCount("ru", 3, "container")).toBe("3 контейнера");
    expect(zoneName("Etc/UTC")).toBe("UTC");
  });

  it("reads the first paragraph after blank lines and joins address families", () => {
    expect(readmeLead("\n\n# Bedolaga Bot\n\nMore.")).toBe("Bedolaga Bot");
    expect(listenerKey("tcp", 22)).toBe(listenerKey("tcp6", 22));
    expect(listenerKey("udp", 53)).not.toBe(listenerKey("tcp", 53));
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
