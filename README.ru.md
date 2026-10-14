# ATLAS

ATLAS — открытый агент инвентаризации одного Linux-сервера. Он записывает, что есть на машине, и для каждого утверждения указывает файл, команду или ответ API. Если источник прочитать нельзя, поле остаётся неопределённым.

Сканирование не открывает сетевой порт и ничего не отправляет с хоста.

```bash
uv sync --project backend --group dev
uv run --project backend python -m atlas.cli.main scan --root fixtures/partial-host --output /tmp/atlas-report
```

Отчёт пишется в Markdown, JSON и HTML. `--root /` сканирует текущую машину. `--db` сохраняет снимок; без этого флага база временная и после команды остаётся только отчёт.

Список файлов и команд, которые читает ATLAS, собирается из объявлений сборщиков:

```bash
uv run --project backend python -m atlas.cli.main manifest
uv run --project backend python -m atlas.cli.main manifest --lang ru
```

Сборщик метрик можно заменить. См. [заметку о языке сборщика](docs/adr/0001-collector-language.md).

API панели слушает Unix-сокет. `atlas token new` печатает одноразовый токен: первая учётная запись создаётся им, паролем и кодом TOTP. TCP выключен, пока не передан `--tcp`, а публичный адрес без TLS и списка разрешённых адресов отклоняется. Управление хостом выключено, пока для той же базы не выполнена команда `atlas control enable`. После этого панель обращается к отдельному root-помощнику и сама эти команды не запускает.

```bash
uv run --project backend python -m atlas.cli.main token new --db /tmp/atlas.db
uv run --project backend python -m atlas.cli.main serve --db /tmp/atlas.db --root fixtures/partial-host --tcp 127.0.0.1:8765
```

Соберите панель, и тот же процесс отдаст её из `frontend/dist`:

```bash
npm install --prefix frontend
npm run build --prefix frontend
```

Каналы оповещений выключены, пока владелец их не включит. `atlas doctor --db <файл>` показывает права файла и то, может ли канал уйти с хоста. `atlas status` печатает версию. `atlas expose` печатает правила слушателя. `atlas uninstall --prefix <путь>` удаляет файлы продукта и оставляет базу, если не передан `--purge`.

`packaging/install.sh` создаёт `/opt/atlas`, `/etc/atlas`, `/var/lib/atlas` и юниты systemd. Релиз он не скачивает. Аргумент `--url` завершает скрипт с ошибкой, пока нет подписанного архива.

Модель безопасности: [docs/security-model.ru.md](docs/security-model.ru.md). Детекторы: [docs/detectors.ru.md](docs/detectors.ru.md). Список читаемых путей печатает `atlas manifest`.

Лицензия: Apache-2.0.
