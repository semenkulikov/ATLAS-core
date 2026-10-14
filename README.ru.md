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

Лицензия: Apache-2.0.
