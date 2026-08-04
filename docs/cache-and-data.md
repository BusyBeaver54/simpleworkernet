# Кэш и каталоги данных

## SmartDataCache (`cache`)

Синглтон кэша **схем полей** моделей (не ответы API). Используется DataProcessor / SmartData при разборе JSON.

```python
from simpleworkernet import cache, config_manager

config_manager.cache_enabled = True
cache.stats()       # размер, hits/misses, стратегия
cache.clear()
cache.save()
cache.load()
```

### Поведение

| Параметр (config) | Роль |
|-------------------|------|
| `enabled` | Вкл/выкл |
| `max_size` | Лимит записей |
| `evict_strategy` | `lru` / `lfu` / `fifo` |
| `evict_threshold` | Доля заполнения, после которой идёт eviction |
| `evict_percent` | Какую долю записей вытеснять |
| `auto_save` | Сохранение при выходе процесса (`atexit`) |

При старте пакета (если кэш включён и файл не загрузился) выполняется `SmartData.preload_from_models(...)` по всем category-моделям.

Classmethods на `SmartData`: `save_cache`, `load_cache`, `clear_cache`, `get_cache_stats`, `set_cache_max_size`, `preload_from_models`.

## DataCache (топология)

Отдельный **экземплярный** кэш в `utils.topology.cache` — инвентарь, длины волокон, geo для build/attenuation. Не синглтон; передаётся в `Topology(..., cache=...)`.

Не путать с глобальным `simpleworkernet.cache`.

## Каталоги данных

Пути из `core.config` / `scripts/uninstall`.
`<app>` = `get_app_name(with_hash=True)`.

| ОС | Config | Cache | Logs (legacy) |
|----|--------|-------|---------------|
| **Linux** | `~/.config/simpleworkernet/<app>/` | `~/.cache/simpleworkernet/<app>/` | `~/.local/share/simpleworkernet/<app>/logs/` |
| **Windows** | `%APPDATA%\\simpleworkernet\\<app>\\` | `%LOCALAPPDATA%\\simpleworkernet\\<app>\\` | `%APPDATA%\\simpleworkernet\\<app>\\logs\\` |
| **macOS** | `~/Library/Application Support/simpleworkernet/<app>/` | `~/Library/Caches/simpleworkernet/<app>/` | `~/Library/Logs/simpleworkernet/<app>/` |

- Конфиг: `config.json` в Config-директории.
- Logs **не пишутся** пакетом; cleanup `--logs-only` удаляет только старые файлы.

```python
from simpleworkernet import config_manager

print(config_manager.config_dir)
print(config_manager.cache_dir)
print(config_manager.logs_dir)
```
