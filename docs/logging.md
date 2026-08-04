# Логирование

Библиотека **не управляет** handlers, уровнями и файлами. Используется стандартный `logging`; фасад — объект `log` (логгер вида `workernet.<app>`).

## Базовая настройка

```python
import logging
from simpleworkernet import log

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log.debug("детали")
log.info("старт")
log.warning("внимание")
log.error("ошибка")
log.exception("с traceback")  # внутри except
```

Точечно:

```python
logging.getLogger("workernet").setLevel(logging.INFO)
```

## Что пишет клиент

- Инициализация `WorkerNetClient`, создание/закрытие сессии.
- API-вызовы и ответы (через методы фасада вроде `log_api_call` / `log_api_response` на уровне debug/info).
- Ошибки соединения, таймауты, разбор ответа.

Файловое логирование пакетом **не настраивается**. Нужны handlers stdlib (`FileHandler`, `RotatingFileHandler` и т.д.).

Старые каталоги логов (legacy) можно удалить через `cleanup-simpleworkernet --logs-only` — см. [Очистка](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/cleanup.md).
