# Публикация панели

Оставьте слушатель на `/run/atlas/web.sock` и открывайте его через `ssh -L`. Это поддерживаемый путь.

Публичный адрес отклоняется, если у `atlas serve` нет `--tls` и хотя бы одного `--allow`. TLS ставьте на обратном прокси или в уже доверенной частной сети. Не выставляйте панель в открытый интернет ради демонстрации.

## Установка одной командой

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
```

Установщик скачивает подписанный архив x86_64 с [GitHub Releases](https://github.com/semenkulikov/ATLAS-core/releases/latest), проверяет SHA-256 (и minisign, если есть), затем запускает `install.sh` из архива.

## Ручной архив

```bash
# после загрузки, проверки и распаковки
sudo ./atlas-1.0.0-linux-x86_64/install.sh
```

Артефакты: `.tar.gz`, `.minisig`, `.sha256`, `minisign.pub`.
