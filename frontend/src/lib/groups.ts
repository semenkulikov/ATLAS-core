/** Group a system unit by its name prefix. Project names are not special-cased. */

import type { CopyKey } from "./i18n";

const RULES: { prefix: string; group: CopyKey }[] = [
  { prefix: "unattended-upgrades", group: "groupPackages" },
  { prefix: "qemu-guest-agent", group: "groupHardware" },
  { prefix: "systemd-modules-load", group: "groupBoot" },
  { prefix: "systemd-random-seed", group: "groupBoot" },
  { prefix: "systemd-remount-fs", group: "groupBoot" },
  { prefix: "systemd-update-utmp", group: "groupBoot" },
  { prefix: "systemd-timesyncd", group: "groupNetwork" },
  { prefix: "systemd-networkd", group: "groupNetwork" },
  { prefix: "systemd-resolved", group: "groupNetwork" },
  { prefix: "systemd-hostnamed", group: "groupBoot" },
  { prefix: "systemd-tmpfiles", group: "groupBoot" },
  { prefix: "systemd-journal", group: "groupLogs" },
  { prefix: "accounts-daemon", group: "groupSessions" },
  { prefix: "systemd-sysctl", group: "groupBoot" },
  { prefix: "systemd-logind", group: "groupSessions" },
  { prefix: "systemd-udevd", group: "groupHardware" },
  { prefix: "NetworkManager", group: "groupNetwork" },
  { prefix: "atlas-helper", group: "groupPanel" },
  { prefix: "atlas-scan", group: "groupPanel" },
  { prefix: "packagekit", group: "groupPackages" },
  { prefix: "containerd", group: "groupContainers" },
  { prefix: "irqbalance", group: "groupHardware" },
  { prefix: "auditd", group: "groupLogs" },
  { prefix: "rsyslog", group: "groupLogs" },
  { prefix: "thermald", group: "groupHardware" },
  { prefix: "fwupd", group: "groupPackages" },
  { prefix: "podman", group: "groupContainers" },
  { prefix: "docker", group: "groupContainers" },
  { prefix: "snapd", group: "groupPackages" },
  { prefix: "upower", group: "groupHardware" },
  { prefix: "polkit", group: "groupSessions" },
  { prefix: "nginx", group: "groupNetwork" },
  { prefix: "sshd", group: "groupNetwork" },
  { prefix: "user@", group: "groupSessions" },
  { prefix: "getty", group: "groupSessions" },
  { prefix: "atlas", group: "groupPanel" },
  { prefix: "apt", group: "groupPackages" },
  { prefix: "ssh", group: "groupNetwork" },
];

export const serviceGroupOrder: CopyKey[] = [
  "groupNetwork",
  "groupContainers",
  "groupPackages",
  "groupLogs",
  "groupSessions",
  "groupHardware",
  "groupBoot",
  "groupPanel",
  "groupOther",
];

export function serviceGroup(key: string): CopyKey {
  const base = key.replace(/\.(service|socket|timer)$/i, "");
  const rule = RULES.find((item) => base.startsWith(item.prefix) || key.startsWith(item.prefix));
  return rule?.group ?? "groupOther";
}
