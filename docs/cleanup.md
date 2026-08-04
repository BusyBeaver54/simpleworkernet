# Очистка данных

Точка входа CLI: `cleanup-simpleworkernet` (`simpleworkernet.cli:main`).

## CLI

```bash
cleanup-simpleworkernet                 # все данные, с подтверждением
cleanup-simpleworkernet --force         # без подтверждения
cleanup-simpleworkernet --dry-run       # только показать, что удалится
cleanup-simpleworkernet --list          # список приложений и размеры
cleanup-simpleworkernet --info --app NAME
cleanup-simpleworkernet --logs-only
cleanup-simpleworkernet --cache-only
cleanup-simpleworkernet --config-only
cleanup-simpleworkernet --app myapp_abc123
cleanup-simpleworkernet --verbose
cleanup-simpleworkernet --version
```

| Флаг | Описание |
|------|----------|
| `--force` / `-f` | Без интерактивного подтверждения |
| `--dry-run` | Не удалять, только отчёт |
| `--list` / `-l` | Список app + размеры config/cache/logs |
| `--info` / `-i` | Детали одного app (нужен `--app`) |
| `--app` / `-a` | Ограничить одним приложением |
| `--logs-only` / `--cache-only` / `--config-only` | Режим очистки |
| `--verbose` | Больше деталей (файлы) |
| `--version` / `-v` | Версия пакета |

## Из Python

```python
from simpleworkernet import cleanup
from simpleworkernet.scripts.uninstall import (
    cleanup_with_confirmation,
    list_applications,
    get_app_info,
)

cleanup(force=True, mode="all")     # logs | cache | config | all
cleanup(force=True, mode="cache", app_name="myapp_abc123")

apps = list_applications()
info = get_app_info("myapp_abc123")
```

`cleanup_with_confirmation(force=..., mode=..., app_name=...)` — то же с запросом подтверждения, если не `force`.

Директория Logs не используется для записи новых логов; `--logs-only` чистит legacy.

Пути: [Кэш и каталоги данных](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/cache-and-data.md).
