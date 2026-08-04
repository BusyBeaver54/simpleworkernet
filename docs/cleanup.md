# Очистка данных

## CLI

```bash
cleanup-simpleworkernet
cleanup-simpleworkernet --force
cleanup-simpleworkernet --dry-run
cleanup-simpleworkernet --list
cleanup-simpleworkernet --logs-only
cleanup-simpleworkernet --cache-only
cleanup-simpleworkernet --config-only
```

## Из Python

```python
from simpleworkernet import cleanup

cleanup(force=True, mode="all")    # logs | cache | config | all
cleanup(force=True, mode="cache")
```

Директория Logs больше не используется для записи новых логов;
`--logs-only` удаляет только legacy-файлы.

Пути: см. [Кэш и каталоги данных](cache-and-data.md).
