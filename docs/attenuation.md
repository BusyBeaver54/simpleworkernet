# Оптические затухания (Attenuation)

Расчёт **по запросу** по уже построенному **CGraph** (не при `build`).

---

## 1. Общая идея

1. Один раз **сгенерировать** JSON-каталог затуханий из БД WorkerNet.
2. **Проверить и при необходимости поправить** значения (реальные IL сплиттеров, α кабелей).
3. При появлении новых кабелей/сплиттеров в БД — **обновить** файл (новые записи добавляются, правки не затираются).
4. В расчётах передать каталог в `Attenuation`.

Файл **не хранится в пакете**. Путь общий для всех приложений:

```
~/.config/simpleworkernet/attenuation_<host>.json
```

- Linux: `~/.config/simpleworkernet/`
- Windows: `%APPDATA%\simpleworkernet\`
- macOS: `~/Library/Application Support/simpleworkernet/`

`<host>` — hostname из URL `WorkerNetClient` (например `kz.example.com`).
Можно задать своё имя: `client_key="kz"` → `attenuation_kz.json`.

---

## 2. Быстрый старт

```python
from simpleworkernet.utils.topology.attenuation import (
    generate_template, update_template, load_attenuation_catalog,
    attenuation_json_path, Attenuation,
)

# --- шаг 1: создать JSON из БД ---
# splitter_catalog_names — имена секций каталога ТМЦ (обязательно)
cat = generate_template(client, ("PLC", "FBT"), cache=cache)
print(attenuation_json_path(client))  # куда сохранился

# --- шаг 2: открыть файл, проверить ports / db_per_km ---
# при необходимости поправить db / db_max вручную

# --- шаг 3: позже — дописать только новое из БД ---
cat = update_template(client, ("PLC", "FBT"), cache=cache)

# --- шаг 4: расчёт ---
cat = load_attenuation_catalog(client)
att = Attenuation(cgraph, catalog=cat, wavelength=1490)  # downstream OLT обычно 1490
report = att.olt_to_customer(customer_id)
print(report.total_db)
print(report.to_table())
```

Если файла ещё нет, `load_attenuation_catalog` вернёт встроенные дефолты (α волокна + ratio-шаблоны), без записей из вашей БД.

---

## 3. Генерация и обновление

| Функция | Назначение |
|---------|------------|
| `generate_template(client, splitter_catalog_names, ...)` | Создать файл. Если уже есть → как `update_template` (если не `overwrite=True`) |
| `update_template(client, splitter_catalog_names, ...)` | Добавить новые кабели/сплиттеры из БД, **не затирая** заполненные `ports` / `db_per_km` |
| `load_attenuation_catalog(client)` | Загрузить JSON для расчёта |
| `attenuation_json_path(client)` | Путь к файлу |

### Параметры

```python
generate_template(
    client,
    ("PLC", "FBT"),          # обязательный: секции Inventory (имена как в БД)
    cache=cache,             # опционально: кэш топологии
    client_key=None,         # явное имя файла вместо host
    path=None,               # полный путь, если нужен свой
    fill_defaults=True,      # дописать недостающие λ из package-шаблонов
    auto_fill_ratio=True,    # подставить ports по guess_ratio_key(имя)
    include_topology_splitters=False,  # ещё и экземпляры Splitter.get()
    overwrite=False,         # True — пересоздать с нуля
)
```

Как выбираются сплиттеры:

1. `Inventory.get_inventory_section_catalog()` — секции с именами из `splitter_catalog_names`.
2. Для каждой секции — все позиции `get_inventory_catalog(section_id=...)`.
3. По `name` — `guess_ratio_key` → ports из package-шаблонов.
4. Кабели — `Fiber.catalog_cables_get()`, имя = **model** (марка), без brand.

---

## 4. Формат JSON

```json
{
  "defaults": {
    "fiber_db_per_km": {
      "1310": {"db": 0.34, "db_max": 0.4},
      "1490": {"db": 0.23, "db_max": 0.26},
      "1550": {"db": 0.19, "db_max": 0.22}
    },
    "splice_db": {"db": 0.05, "db_max": 0.1},
    "connector_db": {"db": 0.3, "db_max": 0.5},
    "adapter_db": {"db": 0.2, "db_max": 0.4},
    "geo_slack_k": 1.03,
    "splitter_excess_db": 0.5
  },
  "cables": [
    {
      "id": "12",
      "name": "ОКБК-01",
      "db_per_km": {
        "1490": {"db": 0.23, "db_max": 0.26},
        "1550": {"db": 0.19, "db_max": 0.22}
      }
    }
  ],
  "splitters": [
    {
      "catalog_id": "5",
      "name": "PLC 1x8",
      "ratio": "1x8_equal",
      "ports": {
        "all": {
          "name": "equal",
          "attenuation": {
            "1490": {"db": 9.69, "db_max": 10.39},
            "1550": {"db": 9.59, "db_max": 10.29}
          }
        }
      }
    },
    {
      "catalog_id": "7",
      "name": "FBT 1x2 5/95",
      "ratio": "1x2_5/95",
      "ports": {
        "1": {"name": "5%", "attenuation": {"1490": {"db": 13.61, "db_max": 14.31}}},
        "2": {"name": "95%", "attenuation": {"1490": {"db": 0.82, "db_max": 1.52}}}
      }
    }
  ],
  "cross_adapters": {"default": {"db": 0.2, "db_max": 0.4}},
  "force": {"fibers": {}, "splitters": {}, "crosses": {}, "objects": {}, "edges": {}}
}
```

### Кабели

Список. Поиск: по `id` или `name`.

### Сплиттеры

Тоже **список** (не `items`). Поля: `catalog_id`, `id` (экземпляр), `name`, `ratio`, `ports`.

**Порты:**

- Неравномерный — `"1"`, `"2"`… и/или имена (`"5%"`).
- Равномерный — ключ **`"all"`**: один IL на любой выход.

Расчёт: номер → имя → `"all"`.

**λ** только в `Attenuation(..., wavelength=1490)`. Нет в таблице — ближайшая + `log.info`.

`db` — типичное, `db_max` — для `use_max=True`.

---

## 5. Приоритет сплиттера

1. `force` по `splitter_id`
2. Запись с `id` (instance)
3. `catalog_id` / `name`
4. Package ratio по `ratio` / `guess_ratio_key(name)`
5. `10·log10(N) + splitter_excess_db`

Волокно: `force` → кабель → `defaults.fiber_db_per_km`.

---

## 6. Overrides (force)

```python
cat = load_attenuation_catalog(client)
cat.force_fiber(fiber_id, {"1490": {"db": 0.20, "db_max": 0.25}})
cat.force_splitter_port(splitter_id, port=1, db=10.5, port_name="5%")
cat.force_cross(cross_id, 0.35)
cat.save(attenuation_json_path(client))
```

---

## 7. API расчёта

```python
att = Attenuation(cgraph, catalog=cat, wavelength=1490, use_max=False)
att.path(src, dst)
att.olt_to_customer(id)
att.customer_to_olt(id)
att.budget_summary()
```

`PathReport`: `total_db`, `segments`, `to_table()`, `by_kind()`, `warnings` / `missing`.

---

## 8. Рабочий процесс

1. **Сгенерировать** файл на каждый WorkerNet-хост.
2. **Проверить JSON**: equal → порт `"all"`; FBT → порты и λ (для GPON downstream — **1490**).
3. Подставить **реальные** IL из БД/паспортов.
4. В скриптах — только `load_attenuation_catalog(client)`.
5. Периодически `update_template(...)` — только новые позиции; заполненное не трогается.
6. Разовые исключения — `force_*`.

Пересоздать с нуля (затрёт ручные правки):

```python
generate_template(client, ("PLC", "FBT"), overwrite=True)
```
