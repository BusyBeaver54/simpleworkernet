# Конфигурация

`config_manager` — синглтон процесса (`ConfigManager`). Изменения в памяти применяются сразу к кэшу/клиенту; на диск — только через `save()`.

Имя приложения: `get_app_name(with_hash=True)` → отдельный каталог config/cache на процесс.

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
| `smartdata_max_depth` | `100` | макс. глубина кастинга SmartData |

Устаревшие ключи в `config.json` (например старые настройки логов) при загрузке **игнорируются**.

## Свойства

Чтение/запись как атрибуты:

```python
from simpleworkernet import config_manager

config_manager.cache_enabled = True
config_manager.cache_max_size = 100000
config_manager.cache_evict_strategy = "lfu"
config_manager.cache_evict_threshold = 0.9
config_manager.cache_evict_percent = 0.2
config_manager.cache_auto_save = True

config_manager.default_timeout = 60
config_manager.max_retries = 5
config_manager.user_agent = "MyApp/1.0"
config_manager.smartdata_max_depth = 50
```

Сеттеры кэша вызывают `cache._apply_config()` / `enable()` / `disable()`.

## Методы

| Метод | Описание |
|-------|----------|
| `get()` | Объект `WorkerNetConfig`. |
| `save()` | Запись в `config.json`. `True`/`False`. |
| `reset(save=False)` | Defaults; при `save=True` сразу на диск. |
| `update(save=False, **kwargs)` | Массовое обновление. Вложенный кэш: `cache={"max_size": 1e5, ...}`. |
| `show_config(return_string=False)` | Печать (через log) или строка. |
| `get_cache_config()` | dict для SmartDataCache (+ `cache_dir`). |
| `get_client_config()` | `timeout`, `max_retries`, `user_agent`. |
| `get_smartdata_config()` | `max_depth`. |

```python
config_manager.update(
    cache={"max_size": 100000, "evict_strategy": "fifo"},
    default_timeout=45,
    save=True,
)
config_manager.show_config()
config_manager.reset(save=True)
```

## Пути

| Атрибут | Смысл |
|---------|--------|
| `config_manager.app_name` | Имя с хешем |
| `config_manager.display_name` | Без хеша |
| `config_manager.config_dir` / `config_file` | Каталог и `config.json` |
| `config_manager.cache_dir` | Кэш |
| `config_manager.logs_dir` | Legacy-логи (только cleanup) |

Подробнее: [Кэш и каталоги данных](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/cache-and-data.md).
