# Публикация панели

Оставьте слушатель на `/run/atlas/web.sock` и открывайте его через `ssh -L`. Это поддерживаемый путь.

Публичный адрес отклоняется, если у `atlas serve` нет `--tls` и хотя бы одного `--allow`. TLS ставьте на обратном прокси или в уже доверенной частной сети. Не выставляйте панель в открытый интернет ради демонстрации.

## Подписанный релиз

Артефакты на [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest):

- `atlas-1.0.0-linux-x86_64.tar.gz`
- `atlas-1.0.0-linux-x86_64.tar.gz.minisig`
- `atlas-1.0.0-linux-x86_64.tar.gz.sha256`
- `minisign.pub`

Проверьте подпись `minisign -V` и checksum, распакуйте и выполните **одну** команду установки:

```bash
sudo ./atlas-1.0.0-linux-x86_64/install.sh
```

`packaging/install.sh --url` по-прежнему завершается с ошибкой: копия из git сама архив не скачивает. Предпочтительный путь — подписанный релиз из [README.ru.md](../README.ru.md).
