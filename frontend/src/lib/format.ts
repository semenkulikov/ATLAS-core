/** Human units. Raw counters and bare seconds stay out of the panel. */

import { copy, type CopyKey, type Lang } from "./i18n";

const locale = (lang: Lang) => (lang === "ru" ? "ru-RU" : "en-US");

type Unit = "day" | "hour" | "minute";

const words: Record<Lang, Record<Unit, Record<string, string>>> = {
  ru: {
    day: { one: "день", few: "дня", many: "дней", other: "дня" },
    hour: { one: "час", few: "часа", many: "часов", other: "часа" },
    minute: { one: "минута", few: "минуты", many: "минут", other: "минуты" },
  },
  en: {
    day: { one: "day", other: "days" },
    hour: { one: "hour", other: "hours" },
    minute: { one: "minute", other: "minutes" },
  },
};

function plural(lang: Lang, count: number, unit: Unit): string {
  const category = new Intl.PluralRules(locale(lang)).select(count);
  const table = words[lang][unit];
  const word = table[category] ?? table.other ?? table.many ?? "";
  return `${count} ${word}`;
}

export function formatUptime(raw: unknown, lang: Lang): string {
  const seconds = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days >= 1) return plural(lang, days, "day");
  if (hours >= 1 && minutes > 0) return `${plural(lang, hours, "hour")} ${plural(lang, minutes, "minute")}`;
  if (hours >= 1) return plural(lang, hours, "hour");
  if (minutes >= 1) return plural(lang, minutes, "minute");
  return copy(lang, "lessThanMinute");
}

export function formatBytes(raw: unknown, lang: Lang): string {
  const value = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(value) || value < 0) return "";
  const units = lang === "ru" ? ["Б", "КБ", "МБ", "ГБ", "ТБ"] : ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  const digits = size >= 10 || index === 0 ? 0 : 1;
  const text = new Intl.NumberFormat(locale(lang), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(size);
  return `${text} ${units[index]}`;
}

export function formatPercent(raw: number, lang: Lang): string {
  if (!Number.isFinite(raw)) return "";
  const digits = raw > 0 && raw < 10 ? 1 : 0;
  const text = new Intl.NumberFormat(locale(lang), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(raw);
  return `${text}%`;
}

export function formatBitrate(bytesPerSecond: number, lang: Lang): string {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond < 0) return "";
  const bits = bytesPerSecond * 8;
  const mbit = bits / 1_000_000;
  const kbit = bits / 1_000;
  const unit = mbit >= 1 ? (lang === "ru" ? "Мбит/с" : "Mbit/s") : lang === "ru" ? "Кбит/с" : "kbit/s";
  const amount = mbit >= 1 ? mbit : kbit;
  const digits = amount >= 10 ? 0 : 1;
  const text = new Intl.NumberFormat(locale(lang), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
  return `${text} ${unit}`;
}

export function formatWhen(raw: string | null | undefined, lang: Lang, now = Date.now()): string {
  if (!raw) return "";
  const then = Date.parse(raw);
  if (!Number.isFinite(then)) return raw;
  const date = new Date(then);
  const startToday = new Date(now);
  startToday.setHours(0, 0, 0, 0);
  const startYesterday = startToday.getTime() - 86400000;
  const clock = new Intl.DateTimeFormat(locale(lang), { hour: "2-digit", minute: "2-digit" }).format(date);
  if (then >= startToday.getTime()) return `${copy(lang, "today").toLowerCase()}, ${clock}`;
  if (then >= startYesterday) return `${copy(lang, "yesterday").toLowerCase()}, ${clock}`;
  return new Intl.DateTimeFormat(locale(lang), { day: "numeric", month: "long" }).format(date);
}

export type Exposure = "local" | "lan" | "external";

export function exposureOf(address: string): Exposure {
  const text = address.trim().toLowerCase().replace(/^\[|\]$/g, "").split("%")[0] ?? "";
  if (text === "*" || text === "") return "external";
  if (text === "::" || text === "0.0.0.0") return "external";
  if (text === "::1" || text.startsWith("127.")) return "local";
  if (text.startsWith("10.") || text.startsWith("192.168.") || text.startsWith("169.254.")) return "lan";
  const parts = text.split(".");
  if (parts.length === 4 && parts[0] === "172") {
    const second = Number(parts[1]);
    if (second >= 16 && second <= 31) return "lan";
  }
  if (text.startsWith("fe80:") || text.startsWith("fc") || text.startsWith("fd")) return "lan";
  return "external";
}

const PORT_KEYS: Record<number, CopyKey> = {
  443: "knownHttps",
  8443: "knownHttps",
  80: "knownHttp",
  8080: "knownApp",
  3000: "knownApp",
  22: "knownSsh",
  5432: "knownPostgres",
  6379: "knownRedis",
  3306: "knownMysql",
  53: "knownDns",
  25: "knownSmtp",
};

export function portHint(port: number, lang: Lang): string {
  const key = PORT_KEYS[port];
  return key ? copy(lang, key) : "";
}

export function textOf(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}
