# ATLAS

**Весь сервер и все проекты на нём — в одной панели.**

ATLAS — production-панель для одного Linux-хоста. Она показывает, что запущено на машине, следит за состоянием в реальном времени и даёт дашборды по продуктам и сервисам, которые на ней живут: инвентаризация, метрики, логи, оповещения и безопасное управление — без сборки из пяти разных инструментов.

[![Release](https://img.shields.io/github/v/release/semenkulikov/ATLAS-core?label=release)](https://github.com/semenkulikov/ATLAS-core/releases/latest)
[![License](https://img.shields.io/github/license/semenkulikov/ATLAS-core)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/semenkulikov/ATLAS-core/ci.yml?branch=main&label=CI)](https://github.com/semenkulikov/ATLAS-core/actions)
[![English](https://img.shields.io/badge/README-EN-blue)](README.md)

---

## Зачем ATLAS

| | |
| --- | --- |
| **Полная картина** | Пользователи, службы, контейнеры, сайты, пакеты и проекты, к которым они относятся |
| **Живые дашборды** | CPU, память и здоровье сервисов — и хоста, и того, что вы реально крутите |
| **Одна панель** | Инвентаризация, мониторинг, логи, настройки и оповещения в одном интерфейсе |
| **Данные на сервере** | Без SaaS; наружу ничего не уходит, пока вы сами не включите алерты |
| **Безопасно по умолчанию** | Пароль + 2FA, управление хостом выключено, пока вы его не включите |

---

## Установка

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

Откройте панель через SSH:

```bash
ssh -L 127.0.0.1:8765:/run/atlas/web.sock root@YOUR_HOST
```

Зайдите на [http://127.0.0.1:8765](http://127.0.0.1:8765), введите одноразовый токен из установщика, задайте пароль и 2FA. Установщик сам делает первый скан; потом его можно повторить в панели: **Обзор → Запустить скан**.

### Обновление

Та же команда, что и установка. Берётся **последний** релиз с GitHub, обновляется `/opt/atlas`, службы перезапускаются, `/var/lib/atlas` (учётки, сканы, настройки) сохраняется:

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

Закрепить версию: `ATLAS_VERSION=1.0.0 curl … | sudo sh`.  
Отдельного автообновления нет — апгрейд запускаете вы.

### Удаление

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
```

---

## Требования

- Linux x86_64 (проверено на Ubuntu 24.04)
- Root для установки
- SSH, чтобы открыть панель

---

## Документация

- [Безопасность](docs/security-model.ru.md) · [FAQ](docs/faq.ru.md) · [Команды](docs/cli.ru.md)
- [English README](README.md)
- [Релизы](https://github.com/semenkulikov/ATLAS-core/releases/latest) · [Changelog](CHANGELOG.md)

---

## Лицензия

Apache-2.0 — [LICENSE](LICENSE)
