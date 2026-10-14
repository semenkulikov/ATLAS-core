/** Screen ids and the two dictionaries. Keys match across languages. */

export const routes = [
  "overview",
  "projects",
  "services",
  "containers",
  "network",
  "users",
  "monitoring",
  "logs",
  "changes",
  "audit",
  "settings",
] as const;

export type RouteId = (typeof routes)[number];

const en = {
  product: "ATLAS",
  overview: "Overview",
  projects: "Projects",
  services: "Services",
  containers: "Containers",
  network: "Network",
  users: "Users",
  monitoring: "Monitoring",
  logs: "Logs",
  changes: "Changes",
  audit: "Audit",
  settings: "Settings",
  search: "Search",
  palette: "Command palette",
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
  empty: "Nothing in the latest scan.",
  loading: "Loading",
  error: "The request failed.",
  evidence: "Evidence",
  close: "Close",
  unknown: "Unknown",
  readOnly: "Control is off. Actions stay unavailable until atlas control enable is run on the host.",
  noScan: "There is no completed scan yet.",
  loadMore: "Load more",
  source: "Log source",
  show: "Show",
  exposed: "Reachable",
  local: "Local",
  role: "Role",
};

const ru: typeof en = {
  product: "ATLAS",
  overview: "Обзор",
  projects: "Проекты",
  services: "Службы",
  containers: "Контейнеры",
  network: "Сеть",
  users: "Пользователи",
  monitoring: "Мониторинг",
  logs: "Логи",
  changes: "Изменения",
  audit: "Журнал",
  settings: "Настройки",
  search: "Поиск",
  palette: "Палитра команд",
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
  empty: "В последнем снимке этого нет.",
  loading: "Загрузка",
  error: "Запрос не выполнен.",
  evidence: "Доказательство",
  close: "Закрыть",
  unknown: "Не определено",
  readOnly: "Управление выключено. Действия появятся после команды atlas control enable на сервере.",
  noScan: "Завершённого сканирования ещё нет.",
  loadMore: "Ещё",
  source: "Источник лога",
  show: "Показать",
  exposed: "Снаружи",
  local: "Локально",
  role: "Роль",
};

const dictionaries = { en, ru };

export type Lang = keyof typeof dictionaries;
export type CopyKey = keyof typeof en;

export function copy(lang: Lang, key: CopyKey): string {
  return dictionaries[lang][key];
}

export function routeFromHash(hash: string): RouteId {
  const name = hash.replace(/^#\/?/, "").split("?")[0];
  return (routes as readonly string[]).includes(name) ? (name as RouteId) : "overview";
}
