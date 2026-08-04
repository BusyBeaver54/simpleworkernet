# Кэш и каталоги данных

## SmartDataCache

`cache` — синглтон SmartDataCache (метаданные полей моделей).

```python
from simpleworkernet import cache, config_manager

config_manager.cache_enabled = True
cache.stats()       # размер, hits/misses
cache.clear()
cache.save()
cache.load()
```

При старте пакета (если кэш включён) выполняется предзагрузка схем из всех category-моделей.

Для топологии используется отдельный **DataCache** (не синглтон) — см. [Топология](topology.md).

## Каталоги данных

Пути совпадают с `core.config` и `scripts/uninstall`.
`<app>` — имя приложения с хешем (`get_app_name(with_hash=True)`).

| ОС | Config | Cache | Logs |
|----|--------|-------|------|
| **Linux** | `~/.config/simpleworkernet/<app>/` | `~/.cache/simpleworkernet/<app>/` | `~/.local/share/simpleworkernet/<app>/logs/` (legacy) |
| **Windows** | `%APPDATA%\\simpleworkernet\\<app>\\` | `%LOCALAPPDATA%\\simpleworkernet\\<app>\\` | `%APPDATA%\\simpleworkernet\\<app>\\logs\\` (legacy) |
| **macOS** | `~/Library/Application Support/simpleworkernet/<app>/` | `~/Library/Caches/simpleworkernet/<app>/` | `~/Library/Logs/simpleworkernet/<app>/` (legacy) |

Файл конфигурации: `config.json` в Config-директории.

Директория Logs больше не используется для записи; `cleanup-simpleworkernet --logs-only` удаляет только старые (legacy) файлы.
