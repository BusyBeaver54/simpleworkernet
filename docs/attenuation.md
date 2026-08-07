# Оптические затухания (Attenuation)

Расчёт **по запросу** по уже построенному **CGraph**.

## Пользовательский каталог (attenuation.json)

Файл **не хранится в пакете**. Генерируется из БД и лежит рядом с `config.json`:

```
~/.config/simpleworkernet/<app>/attenuation.json   # Linux
```

```python
from simpleworkernet.utils.topology.attenuation import (
    generate_template, update_template, load_attenuation_catalog,
    attenuation_json_path, Attenuation,
)

# Первый раз: кабели + сплиттеры из БД, ratio/α из встроенных defaults
cat = generate_template(client, cache=topo._cache)
print(attenuation_json_path())  # куда сохранился

# Позже: проверить БД, добавить только новое (правки ports/db_per_km сохраняются)
cat = update_template(client, cache=topo._cache)

# Для расчёта
cat = load_attenuation_catalog()
att = Attenuation(cgraph, catalog=cat, wavelength=1550)
report = att.olt_to_customer(customer_id)
```

| Функция | Поведение |
|---------|-----------|
| `generate_template(client)` | Создать JSON. Если файл уже есть → как `update_template` |
| `update_template(client)` | Дописать новые кабели/сплиттеры из БД, не затирая заполненное |
| `load_attenuation_catalog()` | Загрузить JSON (или встроенные ratio, если файла нет) |
| `attenuation_json_path()` | Путь к файлу |

Встроенный `defaults.json` в пакете — только seed ratio (1x2 5/95…) и α волокна.
Реальные имена кабелей/сплиттеров подтягиваются из WorkerNet.

`force_fiber` / `force_splitter_port` / `force_cross` — overrides по id поверх JSON.

## Attenuation — методы

| Метод | Назначение |
|-------|------------|
| `path(src, dst)` | Shortest path + сумма сегментов |
| `along_linear()` | Обход линейного CGraph |
| `olt_to_customer(id)` | Downstream OLT → абонент |
| `customer_to_olt(id)` | Upstream |
| `budget_summary()` | Сводка по абонентам |

## PathReport

`total_db`, `segments`, `to_table()`, `by_kind()`, `warnings` / `missing`.

Приоритет сплиттера: force → instance → catalog_id → catalog_name → ratio → estimate.
Если λ нет в таблице — ближайшая + `log.info`.
