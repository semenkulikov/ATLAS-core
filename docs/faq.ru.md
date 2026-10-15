# FAQ

**Что такое ATLAS?**  
Одна панель для одного Linux-сервера: инвентаризация, живые метрики, дашборды проектов, логи, оповещения и при необходимости управление хостом.

**Как установить?**

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/get-atlas.sh | sudo sh
```

**Как удалить?**

```bash
curl -fsSL https://raw.githubusercontent.com/semenkulikov/ATLAS-core/main/packaging/remove-atlas.sh | sudo sh
```

**Данные уходят в облако?**  
Нет. Всё остаётся на сервере, пока вы сами не включите Telegram или webhook.

**Можно перезапускать службы из панели?**  
Да, после включения управления. Опасные действия просят подтверждение.
