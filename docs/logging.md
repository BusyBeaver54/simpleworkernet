# Логирование

Библиотека **не управляет** handlers и уровнями. Сообщения идут через стандартный
`logging` (логгер `workernet.<app>`), клиент настраивает вывод сам:

```python
import logging
from simpleworkernet import log

logging.basicConfig(level=logging.DEBUG)

log.info("старт")
log.debug("детали")
log.warning("внимание")
log.error("ошибка")

# или точечно:
# logging.getLogger("workernet").setLevel(logging.INFO)
```

Файловое логирование пакетом не настраивается — используйте handlers stdlib при необходимости.
