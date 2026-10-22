import { describe, expect, it } from "vitest";
import { byteRate, uplinkInterface } from "./net";

const series = [
  "host.net.docker0.rx_bytes",
  "host.net.docker0.tx_bytes",
  "host.net.br-aa.rx_bytes",
  "host.net.br-aa.tx_bytes",
  "host.net.eth0.rx_bytes",
  "host.net.eth0.tx_bytes",
];

describe("uplink interface", () => {
  it("uses the device named in the default route", () => {
    expect(uplinkInterface(series, "10.0.0.1 dev eth0")).toBe("eth0");
  });

  it("skips bridges when the route does not name a device", () => {
    expect(uplinkInterface(series, "")).toBe("eth0");
  });

  it("stays empty when every interface is virtual", () => {
    expect(
      uplinkInterface(
        ["host.net.docker0.rx_bytes", "host.net.docker0.tx_bytes", "host.net.br-aa.rx_bytes"],
        "",
      ),
    ).toBe("");
  });
});

describe("counter rate", () => {
  it("uses the last two samples", () => {
    expect(
      byteRate([
        { ts: 0, value: 1000 },
        { ts: 10, value: 3000 },
        { ts: 20, value: 5000 },
      ]),
    ).toBe(200);
  });

  it("stays empty until two samples exist", () => {
    expect(byteRate([{ ts: 10, value: 1000 }])).toBeNull();
  });

  it("does not go negative when the counter resets", () => {
    expect(
      byteRate([
        { ts: 10, value: 5000 },
        { ts: 20, value: 100 },
      ]),
    ).toBe(0);
  });
});
