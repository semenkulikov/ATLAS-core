/** Screen ids and the two dictionaries. Keys match across languages. */

import { phrases } from "./phrases";

export const navRoutes = [
  "overview",
  "apps",
  "monitoring",
  "network",
  "access",
  "logs",
  "events",
  "settings",
] as const;

export const routes = [...navRoutes, "system"] as const;

export type RouteId = (typeof routes)[number];

const en = {
  product: "ATLAS",
  overview: "Overview",
  projects: "Projects",
  services: "Services",
  schedules: "Schedules",
  containers: "Containers",
  network: "Network",
  users: "Users",
  monitoring: "Monitoring",
  logs: "Logs",
  changes: "Changes",
  audit: "Audit",
  settings: "Settings",
  search: "Search",
  palette: "Jump to…",
  signIn: "Sign in",
  signOut: "Sign out",
  username: "Username",
  password: "Password",
  code: "Authenticator code",
  enroll: "First-time setup",
  enrollToken: "Enrollment token",
  continue: "Continue",
  confirm: "Confirm",
  language: "Language",
  empty: "Nothing here yet.",
  loading: "Loading…",
  error: "Something went wrong.",
  errorTitle: "Couldn’t complete that",
  showDetails: "Technical details",
  hideDetails: "Hide details",
  evidence: "Where this came from",
  close: "Close",
  unknown: "Unknown",
  readOnly: "Host control is off. Run atlas control enable on the server to allow actions.",
  noScan: "No scan yet",
  noScanHint: "Run a scan to fill the panel with services, projects, and containers on this host.",
  runScan: "Run scan",
  scanning: "Scanning…",
  scanDone: "Scan finished.",
  loadMore: "Load more",
  source: "Log source",
  show: "Show",
  exposed: "Reachable from outside",
  local: "Local only",
  role: "Role",
  controlOn: "Host control is on. Each action goes through the root helper and is written to the audit log.",
  risks: "Running now, but will not start again after reboot",
  intact: "Audit log integrity checks out.",
  broken: "Audit log integrity failed. Do not trust this history.",
  when: "When",
  actor: "Who",
  action: "Action",
  result: "Result",
  restart: "Restart",
  typeToConfirm: "Type the name to confirm",
  saved: "Done",
  channelsOff: "Alert channels are off. Nothing leaves this host.",
  filter: "Contains",
  pattern: "Regex",
  scanCode: "Scan this with your authenticator app, then enter the six-digit code.",
  rejected: "Username, password, or second factor was not accepted.",
  forbidden: "Your role cannot do that.",
  csrf: "Page security token expired. Reload and try again.",
  follow: "Live",
  pause: "Pause",
  alerts: "Alerts",
  channelKind: "Channel",
  channelTarget: "Address",
  channelEnable: "Enable and send off this host",
  channelSaved: "Channel saved.",
  save: "Save",
  on: "on",
  off: "off",
  live: "Live",
  systemSection: "System / built-in",
  workingSection: "Accounts & apps",
  privilegedSection: "Privileged",
  summary: "Summary",
  technical: "Technical details",
  sources: "Data sources",
  hostIdentity: "This host",
  chartsMore: "More charts",
  chartsHost: "Host",
  chartsDisk: "Disks",
  chartsNet: "Network",
  chartsService: "Services",
  chartsContainer: "Containers",
  loadAvg: "Load average",
  memAvailable: "Memory free",
  cpuIdle: "CPU idle",
  unitMemory: "Memory",
  collapseNav: "Collapse",
  expandNav: "Expand",
  opRestartService: "Restart service",
  opRestartContainer: "Restart container",
  opReboot: "Reboot host",
  opPoweroff: "Power off host",
  fact: "Verified",
  derived: "Inferred",
  sshKeys: "SSH keys",
  sudoAccess: "Sudo",
  fieldHostname: "Hostname",
  fieldOs: "Operating system",
  fieldKernel: "Kernel",
  fieldArch: "Architecture",
  fieldUptime: "Uptime",
  fieldVirt: "Virtualization",
  fieldUid: "User ID",
  fieldGid: "Group ID",
  fieldShell: "Login shell",
  fieldHome: "Home directory",
  fieldGroups: "Groups",
  fieldName: "Name",
  fieldActive: "State",
  fieldEnabled: "Starts on boot",
  fieldDescription: "Description",
  predUserUid: "User ID",
  predUserShell: "Login shell",
  predUserHome: "Home directory",
  predUserGroups: "Groups",
  predUserSudo: "Sudo rules",
  predUnitActive: "State",
  predUnitEnabled: "Starts on boot",
  predUnitDescription: "Description",
  metricHostLoad1: "Load (1 min)",
  metricHostLoad5: "Load (5 min)",
  metricHostLoad15: "Load (15 min)",
  metricHostMemAvail: "Memory available",
  metricHostMemTotal: "Memory total",
  metricHostCpuIdle: "CPU idle",
  metricHostCpuIowait: "CPU waiting on disk",
  metricHostCpuSteal: "CPU steal",
  metricHintBytes: "Bytes",
  metricHintMib: "MiB",
  metricHintLoad: "Average runnable processes",
  metricHintCpu: "Percent of time idle",
  metricHintDisk: "Disk throughput",
  metricHintNet: "Network throughput",
  metricHintServiceMem: "Service memory use",
  metricHintContainerMem: "Container memory use",
  logPresetAtlas: "ATLAS journal",
  logPresetSyslog: "System journal",
  errGeneric: "Something went wrong. Try again.",
  errNetwork: "Could not reach the panel. Check the tunnel and try again.",
  errRecordMissing: "That item is not in the latest scan.",
  errProjectMissing: "That project is not in the latest scan.",
  errControlOff: "Host control is off.",
  errActionFailed: "The action did not complete.",
  errActionConfirm: "Confirmation text did not match.",
  errScanFailed: "The scan did not finish.",
  errLogsSource:
    "Could not read the journal. The panel user is not allowed to. Add the panel user to the systemd-journal group.",
  errMetricsQuery: "Could not load that chart.",
  errHttpLimit: "Invalid page size.",
  changeAdded: "Added",
  changeRemoved: "Removed",
  changeChanged: "Changed",
};

const ru: typeof en = {
  product: "ATLAS",
  overview: "Обзор",
  projects: "Проекты",
  services: "Службы",
  schedules: "Расписания",
  containers: "Контейнеры",
  network: "Сеть",
  users: "Пользователи",
  monitoring: "Мониторинг",
  logs: "Логи",
  changes: "Изменения",
  audit: "Журнал",
  settings: "Настройки",
  search: "Поиск",
  palette: "Перейти…",
  signIn: "Войти",
  signOut: "Выйти",
  username: "Имя",
  password: "Пароль",
  code: "Код аутентификатора",
  enroll: "Первый вход",
  enrollToken: "Токен регистрации",
  continue: "Дальше",
  confirm: "Подтвердить",
  language: "Язык",
  empty: "Пока пусто.",
  loading: "Загрузка…",
  error: "Не получилось выполнить запрос.",
  errorTitle: "Не удалось",
  showDetails: "Технические детали",
  hideDetails: "Скрыть детали",
  evidence: "Откуда это взято",
  close: "Закрыть",
  unknown: "Не определено",
  readOnly: "Управление хостом выключено. Чтобы разрешить действия, выполните atlas control enable на сервере.",
  noScan: "Скана ещё не было",
  noScanHint: "Запустите скан — панель заполнится службами, проектами и контейнерами этого хоста.",
  runScan: "Запустить скан",
  scanning: "Сканирование…",
  scanDone: "Скан завершён.",
  loadMore: "Ещё",
  source: "Источник",
  show: "Показать",
  exposed: "Доступен снаружи",
  local: "Только локально",
  role: "Роль",
  controlOn: "Управление включено. Каждое действие идёт через root-помощник и пишется в журнал.",
  risks: "Сейчас работает, но после перезагрузки не поднимется",
  intact: "Целостность журнала в порядке.",
  broken: "Целостность журнала нарушена. Этой истории нельзя доверять.",
  when: "Когда",
  actor: "Кто",
  action: "Действие",
  result: "Результат",
  restart: "Перезапустить",
  typeToConfirm: "Введите имя для подтверждения",
  saved: "Готово",
  channelsOff: "Каналы оповещений выключены. С хоста ничего не уходит.",
  filter: "Содержит",
  pattern: "Regex",
  scanCode: "Отсканируйте приложением-аутентификатором и введите шесть цифр.",
  rejected: "Имя, пароль или второй фактор не приняты.",
  forbidden: "У вашей роли нет такого действия.",
  csrf: "Токен страницы устарел. Обновите страницу и повторите.",
  follow: "Вживую",
  pause: "Пауза",
  alerts: "Оповещения",
  channelKind: "Канал",
  channelTarget: "Адрес",
  channelEnable: "Включить и отправлять наружу",
  channelSaved: "Канал сохранён.",
  save: "Сохранить",
  on: "вкл",
  off: "выкл",
  live: "Вживую",
  systemSection: "Системные",
  workingSection: "Рабочие",
  privilegedSection: "Привилегированные",
  summary: "Сводка",
  technical: "Технические детали",
  sources: "Источники данных",
  hostIdentity: "Этот хост",
  chartsMore: "Ещё графики",
  chartsHost: "Хост",
  chartsDisk: "Диски",
  chartsNet: "Сеть",
  chartsService: "Службы",
  chartsContainer: "Контейнеры",
  loadAvg: "Средняя нагрузка",
  memAvailable: "Свободная память",
  cpuIdle: "CPU простаивает",
  unitMemory: "Память",
  collapseNav: "Свернуть",
  expandNav: "Развернуть",
  opRestartService: "Перезапустить службу",
  opRestartContainer: "Перезапустить контейнер",
  opReboot: "Перезагрузить хост",
  opPoweroff: "Выключить хост",
  fact: "Проверено",
  derived: "Выведено",
  sshKeys: "SSH-ключи",
  sudoAccess: "Sudo",
  fieldHostname: "Имя хоста",
  fieldOs: "Система",
  fieldKernel: "Ядро",
  fieldArch: "Архитектура",
  fieldUptime: "Аптайм",
  fieldVirt: "Виртуализация",
  fieldUid: "UID",
  fieldGid: "GID",
  fieldShell: "Оболочка",
  fieldHome: "Домашний каталог",
  fieldGroups: "Группы",
  fieldName: "Имя",
  fieldActive: "Состояние",
  fieldEnabled: "Автозапуск",
  fieldDescription: "Описание",
  predUserUid: "UID",
  predUserShell: "Оболочка",
  predUserHome: "Домашний каталог",
  predUserGroups: "Группы",
  predUserSudo: "Правила sudo",
  predUnitActive: "Состояние",
  predUnitEnabled: "Автозапуск",
  predUnitDescription: "Описание",
  metricHostLoad1: "Нагрузка (1 мин)",
  metricHostLoad5: "Нагрузка (5 мин)",
  metricHostLoad15: "Нагрузка (15 мин)",
  metricHostMemAvail: "Свободная память",
  metricHostMemTotal: "Всего памяти",
  metricHostCpuIdle: "CPU простаивает",
  metricHostCpuIowait: "CPU ждёт диск",
  metricHostCpuSteal: "CPU steal",
  metricHintBytes: "Байты",
  metricHintMib: "МиБ",
  metricHintLoad: "Среднее число готовых процессов",
  metricHintCpu: "Доля времени простоя",
  metricHintDisk: "Скорость диска",
  metricHintNet: "Сетевой трафик",
  metricHintServiceMem: "Память службы",
  metricHintContainerMem: "Память контейнера",
  logPresetAtlas: "Журнал ATLAS",
  logPresetSyslog: "Системный журнал",
  errGeneric: "Что-то пошло не так. Попробуйте ещё раз.",
  errNetwork: "Панель недоступна. Проверьте SSH-туннель и повторите.",
  errRecordMissing: "Этого объекта нет в последнем скане.",
  errProjectMissing: "Этого проекта нет в последнем скане.",
  errControlOff: "Управление хостом выключено.",
  errActionFailed: "Действие не выполнено.",
  errActionConfirm: "Текст подтверждения не совпал.",
  errScanFailed: "Скан не завершился.",
  errLogsSource:
    "Не удалось прочитать журнал. У панели нет прав на чтение. Добавьте пользователя панели в группу systemd-journal.",
  errMetricsQuery: "Не удалось загрузить график.",
  errHttpLimit: "Неверный размер страницы.",
  changeAdded: "Добавлено",
  changeRemoved: "Удалено",
  changeChanged: "Изменено",
};

const enFull = { ...en, ...phrases.en };
const ruFull = { ...ru, ...phrases.ru };

const dictionaries = { en: enFull, ru: ruFull };

export type Lang = keyof typeof dictionaries;
export type CopyKey = keyof typeof enFull;
export const copyKeys = Object.keys(enFull) as CopyKey[];

export function copy(lang: Lang, key: CopyKey): string {
  return dictionaries[lang][key];
}

const aliases: Record<string, RouteId> = {
  projects: "apps",
  services: "system",
  schedules: "system",
  containers: "system",
  users: "access",
  changes: "events",
  audit: "events",
};

export type Place = { route: RouteId; appId: string; tab: string };

export function parseHash(hash: string): Place {
  const parts = hash
    .replace(/^#\/?/, "")
    .split("?")[0]
    .split("/")
    .filter(Boolean)
    .map((part) => {
      try {
        return decodeURIComponent(part);
      } catch {
        return part;
      }
    });
  const head = aliases[parts[0] ?? ""] ?? parts[0] ?? "";
  const route = (routes as readonly string[]).includes(head) ? (head as RouteId) : "overview";
  let appId = "";
  let tab = "";
  if (route === "apps" && parts[1]) {
    appId = parts[1];
    tab = parts[2] || "summary";
  } else if (route === "system") {
    tab = parts[1] || "services";
  } else if (route === "settings") {
    tab = parts[1] || "server";
  }
  return { route, appId, tab };
}

export function hashFor(place: Place): string {
  if (place.route === "apps" && place.appId) {
    return `#/apps/${encodeURIComponent(place.appId)}/${place.tab || "summary"}`;
  }
  if (place.route === "system") return `#/system/${place.tab || "services"}`;
  if (place.route === "settings" && place.tab && place.tab !== "server") {
    return `#/settings/${place.tab}`;
  }
  return `#/${place.route}`;
}

export function routeFromHash(hash: string): RouteId {
  return parseHash(hash).route;
}

/** Human label for a host/user/service payload key. */
export function fieldLabel(lang: Lang, key: string): string {
  const map: Record<string, CopyKey> = {
    hostname: "fieldHostname",
    "os.pretty_name": "fieldOs",
    pretty_name: "fieldOs",
    "kernel.release": "fieldKernel",
    "kernel.name": "fieldKernel",
    arch: "fieldArch",
    uptime_seconds: "fieldUptime",
    virt: "fieldVirt",
    uid: "fieldUid",
    gid: "fieldGid",
    shell: "fieldShell",
    home: "fieldHome",
    groups: "fieldGroups",
    name: "fieldName",
    active: "fieldActive",
    "unit.active": "fieldActive",
    enabled: "fieldEnabled",
    "unit.enabled": "fieldEnabled",
    description: "fieldDescription",
    "unit.description": "fieldDescription",
    "unit.exec_start": "execStart",
    exec_start: "execStart",
    "unit.restart": "restartPolicy",
    restart: "restartPolicy",
    "unit.working_directory": "workDir",
    working_directory: "workDir",
    exposed: "exposed",
  };
  const hit = map[key];
  return hit ? copy(lang, hit) : key;
}

/** Human label for a fact predicate. */
export function predicateLabel(lang: Lang, predicate: string): string {
  const map: Record<string, CopyKey> = {
    "user.uid": "predUserUid",
    "user.shell": "predUserShell",
    "user.home": "predUserHome",
    "user.groups": "predUserGroups",
    "user.sudo": "predUserSudo",
    "unit.active": "predUnitActive",
    "unit.enabled": "predUnitEnabled",
    "unit.description": "predUnitDescription",
    "unit.sub": "predUnitActive",
    "unit.exec_start": "execStart",
    "unit.restart": "restartPolicy",
    "unit.working_directory": "workDir",
  };
  const hit = map[predicate];
  return hit ? copy(lang, hit) : predicate;
}

export function actionTitle(lang: Lang, op: string): string {
  if (op === "service.restart") return copy(lang, "opRestartService");
  if (op === "container.restart") return copy(lang, "opRestartContainer");
  if (op === "host.reboot") return copy(lang, "opReboot");
  if (op === "host.poweroff") return copy(lang, "opPoweroff");
  if (op === "app.update") return copy(lang, "opUpdate");
  return op;
}

export type MetricMeta = { title: string; hint: string; unit: string; group: string };

export function metricMeta(lang: Lang, name: string): MetricMeta {
  if (name === "host.load.1")
    return { title: copy(lang, "metricHostLoad1"), hint: copy(lang, "metricHintLoad"), unit: "", group: "host" };
  if (name === "host.load.5")
    return { title: copy(lang, "metricHostLoad5"), hint: copy(lang, "metricHintLoad"), unit: "", group: "host" };
  if (name === "host.load.15")
    return { title: copy(lang, "metricHostLoad15"), hint: copy(lang, "metricHintLoad"), unit: "", group: "host" };
  if (name === "host.memory.available_bytes")
    return {
      title: copy(lang, "metricHostMemAvail"),
      hint: copy(lang, "metricHintMib"),
      unit: "MiB",
      group: "host",
    };
  if (name === "host.memory.total_bytes")
    return {
      title: copy(lang, "metricHostMemTotal"),
      hint: copy(lang, "metricHintMib"),
      unit: "MiB",
      group: "host",
    };
  if (name === "host.cpu.idle")
    return { title: copy(lang, "metricHostCpuIdle"), hint: copy(lang, "metricHintCpu"), unit: "%", group: "host" };
  if (name === "host.cpu.iowait")
    return {
      title: copy(lang, "metricHostCpuIowait"),
      hint: copy(lang, "metricHintCpu"),
      unit: "%",
      group: "host",
    };
  if (name === "host.cpu.steal")
    return {
      title: copy(lang, "metricHostCpuSteal"),
      hint: copy(lang, "metricHintCpu"),
      unit: "%",
      group: "host",
    };
  if (name.startsWith("host.disk."))
    return {
      title: name.replace(/^host\.disk\./, "Disk "),
      hint: copy(lang, "metricHintDisk"),
      unit: "B",
      group: "disk",
    };
  if (name.startsWith("host.net."))
    return {
      title: name.replace(/^host\.net\./, "Net "),
      hint: copy(lang, "metricHintNet"),
      unit: "B",
      group: "net",
    };
  if (name.startsWith("host.service.")) {
    const rest = name.replace(/^host\.service\./, "");
    return {
      title: rest.replace(/\.memory_bytes$/, " · RAM").replace(/\.cpu_usage_usec$/, " · CPU"),
      hint: copy(lang, "metricHintServiceMem"),
      unit: name.includes("memory") ? "MiB" : "µs",
      group: "service",
    };
  }
  if (name.startsWith("host.container.")) {
    const rest = name.replace(/^host\.container\./, "");
    return {
      title: rest.replace(/\.memory_bytes$/, " · RAM").replace(/\.cpu_usage_usec$/, " · CPU"),
      hint: copy(lang, "metricHintContainerMem"),
      unit: name.includes("memory") ? "MiB" : "µs",
      group: "container",
    };
  }
  return { title: name, hint: "", unit: "", group: "other" };
}

export function groupLabel(lang: Lang, group: string): string {
  if (group === "host") return copy(lang, "chartsHost");
  if (group === "disk") return copy(lang, "chartsDisk");
  if (group === "net") return copy(lang, "chartsNet");
  if (group === "service") return copy(lang, "chartsService");
  if (group === "container") return copy(lang, "chartsContainer");
  return copy(lang, "chartsMore");
}
