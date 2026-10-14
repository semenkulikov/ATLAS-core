# Справочник команд

| Команда | Что делает |
| --- | --- |
| `atlas scan --root <путь> --format md\|json\|html` | Один отчёт. Без `--db` база временная. |
| `atlas manifest --lang en\|ru` | Все файлы и команды, которые объявил сборщик. |
| `atlas serve --db <файл>` | Панель на `/run/atlas/web.sock`. `--tcp 127.0.0.1:ПОРТ` включает loopback. |
| `atlas token new --db <файл>` | Одноразовый токен регистрации. |
| `atlas control enable\|disable --db <файл>` | Действия на хосте выключены, пока не enable. |
| `atlas status --db <файл>` | Версия, переключатель управления, последний снимок. |
| `atlas doctor --db <файл>` | Права файла и может ли канал оповещений уйти с хоста. |
| `atlas expose` | Как можно открыть панель. |
| `atlas user reset-2fa --db <файл>` | Новый секрет TOTP владельца. Только локально. |
| `atlas export --db <файл>` | Последний завершённый снимок в Markdown, JSON и HTML. |
| `atlas uninstall --prefix <путь> [--purge]` | Удаляет файлы продукта. База остаётся без `--purge`. |

`atlas-helper --socket <путь> --uid <uid веб-процесса>` — процесс root. `serve` его не запускает.
