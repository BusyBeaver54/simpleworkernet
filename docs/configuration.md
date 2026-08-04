# Конфигурация

`config_manager` — синглтон процесса. Изменения применяются сразу;
persistence — только через `save()`.

## Значения по умолчанию

| Параметр | Default | Описание |
|----------|---------|----------|
| `cache.enabled` | `True` | SmartDataCache включён |
| `cache.max_size` | `200000` | макс. записей |
| `cache.evict_strategy` | `"lru"` | `lru` / `lfu` / `fifo` |
| `cache.evict_threshold` | `0.95` | порог заполнения для eviction |
| `cache.evict_percent` | `0.25` | доля удаляемых записей |
| `cache.auto_save` | `True` | автосохранение при выходе |
| `default_timeout` | `30` | таймаут HTTP (сек) |
| `max_retries` | `3` | число повторов |
| `user_agent` | `"SimpleWorkerNet/1.0"` | User-Agent |
| `smartdata_max_depth` | `100` | макс. глубина кастинга |

## Примеры

```python
from simpleworkernet import config_manager

config_manager.cache_enabled = True
config_manager.cache_max_size = 200000
config_manager.cache_evict_strategy = "lfu"

config_manager.default_timeout = 60
config_manager.save()          # записать в config.json

config_manager.show_config()  # печать текущих значений
config_manager.reset(save=True)  # сброс на defaults
```

Массовое обновление:

```python
config_manager.update(
    cache={"max_size": 100000, "evict_strategy": "fifo"},
    save=True,
)
```

Файл конфигурации: `config.json` в Config-директории (см. [Кэш и каталоги данных](cache-and-data.md)).
