# ATLAS

**Агент инвентаризации одного Linux-сервера.**  
ATLAS фиксирует, что работает на машине, и для каждого утверждения сохраняет файл, команду или ответ API. Непрочитанный источник остаётся неизвестным. Скан не открывает сетевой порт и ничего не отправляет с хоста.

[![Release](https://img.shields.io/github/v/release/semenkulikov/ATLAS-core?label=release)](https://github.com/semenkulikov/ATLAS-core/releases/latest)
[![License](https://img.shields.io/github/license/semenkulikov/ATLAS-core)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/semenkulikov/ATLAS-core/ci.yml?branch=main&label=CI)](https://github.com/semenkulikov/ATLAS-core/actions)
[![English](https://img.shields.io/badge/README-EN-blue)](README.md)

---

## Установка

Одна команда на Ubuntu 24.04 x86_64 (от root):

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

Скрипт скачивает подписанный релиз, проверяет SHA-256 (и minisign, если установлен `minisign`), запускает установщик из архива, ждёт `/run/atlas/web.sock` и печатает команду туннеля плюс одноразовый токен регистрации.

### Открыть панель

```bash
ssh -L 127.0.0.1:8765:/run/atlas/web.sock root@YOUR_HOST
```

Откройте `http://127.0.0.1:8765` и зарегистрируйте владельца токеном, паролем и TOTP.

### Удаление

Одна команда:

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
```

Офлайн, если ATLAS уже стоит:

```bash
sudo /opt/atlas/packaging/remove-atlas.sh
```

---

## Что внутри

| Область | Поведение |
| --- | --- |
| Инвентаризация | ОС, пользователи, systemd, порты, nginx/сайты, пакеты, Docker/Podman через root-помощника |
| Доказательства | У каждого факта есть файл, команда или путь API; секреты маскируются |
| Панель | FastAPI на Unix-сокете; первая учётка — токен + пароль + TOTP |
| Метрики | Ряды хоста и cgroup CPU/память служб и контейнеров; живой поток 1 с, пока открыт Monitor |
| Оповещения | Только webhook и Telegram; оба выключены, пока владелец не включит канал |
| Управление | Выключено до `atlas control enable`; действия идут через белый список помощника |
| Размер | Свой stripped CPython; бюджет 400 МиБ (~141 МиБ дерева в 1.0.0) |

Debian, AlmaLinux и arm64 пока остаются задачей пользователей; этот релиз проверен на Ubuntu 24.04 x86_64.

---

## Разработка из git

```bash
uv sync --project backend --group dev
uv run --project backend python -m atlas.cli.main scan \
  --root fixtures/partial-host --output /tmp/atlas-report

npm install --prefix frontend && npm run build --prefix frontend
uv run --project backend python -m atlas.cli.main token new --db /tmp/atlas.db
uv run --project backend python -m atlas.cli.main serve \
  --db /tmp/atlas.db --root fixtures/partial-host --tcp 127.0.0.1:8765
```

```bash
uv run --project backend python -m atlas.cli.main manifest
uv run --project backend python -m atlas.cli.main manifest --lang ru
```

Из git без скачивания релиза: `sudo packaging/install.sh`.  
То же, что curl-установщик: `sudo packaging/install.sh --url`.

Ручной путь (скачать → проверить → распаковать → `sudo ./atlas-1.0.0-linux-x86_64/install.sh`) описан в [docs/publish.ru.md](docs/publish.ru.md).

---

## Документация

| Тема | RU | EN |
| --- | --- | --- |
| Модель безопасности | [docs/security-model.ru.md](docs/security-model.ru.md) | [docs/security-model.md](docs/security-model.md) |
| CLI | [docs/cli.ru.md](docs/cli.ru.md) | [docs/cli.md](docs/cli.md) |
| FAQ | [docs/faq.ru.md](docs/faq.ru.md) | [docs/faq.md](docs/faq.md) |
| Публикация панели | [docs/publish.ru.md](docs/publish.ru.md) | [docs/publish.md](docs/publish.md) |
| Детекторы | [docs/detectors.ru.md](docs/detectors.ru.md) | [docs/detectors.md](docs/detectors.md) |
| Политика безопасности | — | [SECURITY.md](SECURITY.md) |

Changelog: [CHANGELOG.md](CHANGELOG.md) · Релизы: [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest)

---

## Лицензия

Apache-2.0. См. [LICENSE](LICENSE) и [NOTICE](NOTICE).
