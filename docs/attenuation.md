# Оптические затухания

Модуль считает **вносимое затухание** вдоль пути коммутации: волокно, сплиттеры, сварки, коннекторы, адаптеры кросса.

Для каждого сегмента и для всего пути сразу считаются три значения:

| Поле | Смысл |
|------|--------|
| **calc** (`db` / `total_db`) | номинал (типичное значение) |
| **min** (`db_min` / `total_db_min`) | нижняя оценка |
| **max** (`db_max` / `total_db_max`) | верхняя оценка |

```python
from simpleworkernet.utils.topology.attenuation import (
    Attenuation, AttenuationError,
    AttenuationCatalog, PathReport, MultiPathReport, EndpointInfo,
    generate_template, update_template, load_attenuation_catalog,
    save_path_report, load_path_report,
    attenuation_json_path, client_file_key,
    PairPlan, pair_plan, validate_pair_inputs, guess_ratio_key,
)
# или:
from simpleworkernet.utils.topology import Attenuation, PathReport, MultiPathReport
```

---

## 1. Рабочий процесс (обязательно)

1. **Сгенерировать JSON-каталог** из дефолтов пакета + объектов БД (`generate_template`).
2. **Проверить** значения (особенно сплиттеры и кабели), поправить вручную.
3. При появлении новых объектов в БД — **`update_template`** (не затирает ручные правки).
4. Считать затухания через **`Attenuation.calculate(...)`**.

Файл каталога (на хост API):

```text
~/.config/simpleworkernet/attenuation_<hostname>.json
```

```python
from simpleworkernet.utils.topology.attenuation import (
    generate_template, update_template, load_attenuation_catalog, attenuation_json_path,
)

print(attenuation_json_path(client))

cat = generate_template(
    client,
    splitter_catalog_names=("PLC", "FBT"),  # обязательно: имена каталогов в БД
    overwrite=False,
)
cat = update_template(client, splitter_catalog_names=("PLC", "FBT"))
cat = load_attenuation_catalog(client)
```

`splitter_catalog_names` — **обязательный** параметр: имена каталогов сплиттеров в WorkerNet.

---

## 2. Структура JSON-каталога

Значения — число или словарь min/calc/max:

```json
{ "db_min": 0.17, "db": 0.19, "db_max": 0.22 }
```

Если только `db` + `db_max`, то `db_min = db`. Одно число — все три равны.

См. `defaults.json` в пакете и сгенерированный файл хоста.

---

## 3. `Attenuation.calculate`

```python
att = Attenuation(client=client, catalog=cat)  # или cgraph=..., cache=...
res = att.calculate("customer", 17711, "olt", 11808, obj2_port=11, wavelength=1490)
res = att.calculate(
    "fiber", 13259, "fiber", 13235,
    obj1_side=2, obj1_port=1, obj2_side=2, obj2_port=1,
)
print(res.total_db, res.total_db_min, res.total_db_max)
print(res.to_table())
```

Для **fiber** укажите `port` (номер ОВ) хотя бы с одной стороны.

Если `self.g` уже содержит объекты — перестройки нет. Иначе (нужен `client`) строится CGraph по стратегии пары типов.

---

## 5. Отчёты

### `EndpointInfo`

| Поле | Описание |
|------|----------|
| `obj_type`, `obj_id` | тип и id |
| `obj_name` | имя (customer: `full_name`/`name`; device: имя; fiber: марка кабеля) |
| `side`, `port` | сторона и порт; для **fiber** — **номер ОВ** (не id волокна) |
| `port_name` | имя порта: устройство — `PON0`; сплиттер — доля; **fiber** — `m1f5` (модуль+ОВ) |
| `host` | host/IP для olt/switch/onu/radio |
| `commutation_index` | индекс коммутации у абонента |
| `meta` | доп. поля: для fiber — `fiber_core_id`, `fiber_number`, `module`, `cable_name` |

Имена и `api_obj` при отсутствии в вершине подтягиваются лениво (`_ensure_api_obj` → cache / API).

`format_sp()` → `"s1p0"`.  
`format_header()` → `"olt:11808 s0p3 host=10.1.2.3 name=OLT-Main port=PON0"`.

### `AttenuationSegment`

`kind`: fiber / splitter / splice / connector / adapter / force.  
`db`, `db_min`, `db_max`; для fiber — `length_m`, `length_source` (`opticalen` / `geo` / `cache` / `missing`).  
`source`: default / cable / name / ratio:… / force / estimated.

Для **fiber**-сегмента:

| Поле | Значение |
|------|----------|
| `obj_id` | id кабельной линии |
| `port` | **номер ОВ** (`number` из списка волокон) |
| `port_name` | `m{module}f{number}`, например `m1f5` |
| `obj_name` | марка/имя кабеля |
| `meta.fiber_core_id` | id волокна в БД |
| `meta.fiber_number` | номер ОВ |
| `meta.module` | номер модуля (1-based) |

Резолв волокна: `api_obj.fibers` или `Fiber.get_fiber(fiber_id=…)`. Текущий `port` вершины CGraph сопоставляется сначала с id волокна, затем с номером ОВ.

### `PathReport`

- `total_db`, `total_db_min`, `total_db_max`
- `from_endpoint`, `to_endpoint`, `device_endpoint`, `customer_endpoint`
- `by_kind()`, `fiber_length_m`, `fiber_db`, `splitter_db`, `joint_db`
- `to_table()`, `save()` / `load()`, `to_dict()` / `from_dict()`

### `MultiPathReport`

- `branches`, `count`, `total_db`/`avg`, `total_db_min`, `total_db_max`
- `branch_for(obj_type, obj_id)`
- `to_table()`, **`save(path)` / `load(path)`**

---

## 6. Длина волокна (`length_source`)

| Источник | Откуда |
|----------|--------|
| `opticalen` | оптическая длина из модели fiber |
| `geo` / `geo_api` | геометрия × `geo_slack_k` |
| `cache` | DataCache |
| `missing` / `unknown` | длина неизвестна → db=0 + warning |

Подробнее о топологии: [topology.md](topology.md).
