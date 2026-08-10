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

```json
{
  "defaults": {
    "fiber_db_per_km": {
      "1310": { "db_min": 0.32, "db": 0.34, "db_max": 0.40 },
      "1490": { "db": 0.23, "db_max": 0.26 },
      "1550": { "db": 0.19, "db_max": 0.22 }
    },
    "splice_db": { "db": 0.05, "db_max": 0.10 },
    "connector_db": { "db": 0.15, "db_max": 0.30 },
    "adapter_db": { "db": 0.30, "db_max": 0.50 },
    "cross_loss_mode": "adapter",
    "geo_slack_k": 1.03,
    "splitter_excess_db": 0.5
  },
  "cables": [
    { "id": "12", "name": "ОКС-16",
      "db_per_km": { "1550": { "db_min": 0.17, "db": 0.19, "db_max": 0.22 } } }
  ],
  "splitters": [
    {
      "catalog_id": "15",
      "name": "FBT 1x2 50/50",
      "ratio": "1x2_50/50",
      "ports": {
        "1": { "name": "50%", "attenuation": {
          "1490": { "db": 3.61, "db_max": 4.31 },
          "1550": { "db": 3.51, "db_max": 4.21 }
        }},
        "2": { "name": "50%", "attenuation": {
          "1550": { "db": 3.51, "db_max": 4.21 }
        }}
      }
    }
  ],
  "cross_adapters": { "default": { "db": 0.3, "db_max": 0.5 } },
  "force": {
    "splitters": { "42": { "1": { "db": 3.2, "db_max": 3.5 }, "all": 3.4 } },
    "edges": { "connect-uuid-1": 0.08 }
  }
}
```

### Приоритет порта сплиттера

1. `force.splitters[<id>]`
2. JSON по **имени** (`prefer_name=True`)
3. по instance id / `catalog_id`
4. `ratio_defaults` из package `defaults.json`
5. оценка `10·log10(N) + splitter_excess_db` → `source=estimated`

Длина волны: точное совпадение, иначе **ближайшая** (лог).  
Порт — по номеру или имени (`"50%"`, `"all"`).

### `cross_loss_mode`

| Режим | Смысл |
|-------|--------|
| `"adapter"` (default) | внутреннее ребро кросса → сегмент `adapter` |
| `"connectors"` | коннекторы на терминалах |

---

## 3. Инициализация `Attenuation`

```python
Attenuation(
    cgraph=None,       # CGraph | list[CGraph] | NetworkTopology
    *,
    topology=None,     # явно NetworkTopology (приоритет)
    catalog=None,
    wavelength=1550,
    cache=None,
    client=None,
    use_max=False,
)
```

```python
att = Attenuation(cgraph=cg, wavelength=1490)
att = Attenuation(cgraph=[cg1, cg2], client=client)
att = Attenuation(topology=nt, wavelength=1490)
att = Attenuation(cgraph=nt)  # duck-type по .cgraphs
att = Attenuation(client=client, cache=cache, wavelength=1490)
```

При нескольких CGraph:

- `calculate(obj1, …)` — граф, где есть объекты (предпочтение: оба конца);
- `calculate()` — **все** cgraph → `MultiPathReport`.

---

## 4. `calculate(...)`

```python
res = att.calculate(
    obj1_type=None, obj1_id=None,
    obj2_type=None, obj2_id=None,
    *,
    wavelength=None,
    obj1_side=None, obj1_port=None,
    obj2_side=None, obj2_port=None,
    direction=None,
    use_max=None,
    max_paths=50,
)
# → PathReport | MultiPathReport
```

| Вызов | Поведение |
|-------|-----------|
| `calculate("customer", 17711, "olt", 11808, obj2_port=3)` | путь между объектами |
| `calculate("customer", 17711)` | obj2 авто (OLT/switch/…) |
| `calculate()` при cgraph/topology | все пути customer→olt |
| `calculate()` без графа и obj1 | `AttenuationError` |

Для **fiber** укажите `port` (номер ОВ) хотя бы с одной стороны.

### Как задавать объекты

| Тип | side | port |
|-----|------|------|
| customer / olt / switch / onu / radio | обычно не нужны | порт OLT желателен |
| splitter / cwdm | 1=вход, 2=выход | номер порта |
| cross | 1/2 | порт (uuid в id) |
| fiber | сторона узла | **номер ОВ** |

```python
res = att.calculate("customer", 17711, "olt", 11808, obj2_port=11, wavelength=1490)
res = att.calculate(
    "fiber", 13259, "fiber", 13235,
    obj1_side=2, obj1_port=1, obj2_side=2, obj2_port=1,
)
print(res.total_db, res.total_db_min, res.total_db_max)
print(res.to_table())
```

Если `self.g` уже содержит объекты — перестройки нет. Иначе (нужен `client`) строится CGraph по стратегии пары типов (fiber↔fiber через FNGraph-коридор, olt↔customer от устройства и т.д.).

---

## 5. Отчёты

### `EndpointInfo`

| Поле | Описание |
|------|----------|
| `obj_type`, `obj_id` | тип и id |
| `obj_name` | имя |
| `side`, `port` | сторона и порт |
| `port_name` | имя порта (PON0, «50%») |
| `host` | host/IP для olt/switch/onu/radio |
| `commutation_index` | индекс коммутации у абонента |

`format_sp()` → `"s1p0"`.  
`format_header()` → `"olt:11808 s0p3 host=10.1.2.3 name=OLT-Main port=PON0"`.

### `AttenuationSegment`

`kind`: fiber / splitter / splice / connector / adapter / force.  
`db`, `db_min`, `db_max`; для fiber — `length_m`, `length_source` (`opticalen` / `geo` / `cache` / `missing`).  
`source`: default / cable / name / ratio:… / force / estimated.

### `PathReport`

- `total_db`, `total_db_min`, `total_db_max`
- `from_endpoint`, `to_endpoint`, `device_endpoint`, `customer_endpoint`
- `by_kind()`, `fiber_length_m`, `fiber_db`, `splitter_db`, `joint_db`
- `to_table()`, `save()` / `load()`, `to_dict()` / `from_dict()`

Пример `to_table()`:

```text
Path  λ=1490 nm  calc=12.345  min=11.200  max=13.800 dB (fiber=1.2, splitter=10.5, joints=0.6)
  customer: customer:17711 s1p0 name=Иванов commutation=0
  olt: olt:11808 s0p3 host=10.1.2.3 name=OLT-Main port=PON0
------------------------------------------------------------------------
  1. fiber       0.234 dB  ... [fiber:42, name=ОКС-16, s0p1, L=1200.0m, Lsrc=opticalen, min=..., max=..., src=cable]
  ...
```

Оборудование: приоритет **olt → switch → onu → radio**.

### `MultiPathReport`

- `branches`, `count`, `total_db`/`avg`, `total_db_min`, `total_db_max`
- `branch_for(obj_type, obj_id)`
- `to_table()`, **`save(path)` / `load(path)`**

```python
res.save("/tmp/multi.json")
loaded = MultiPathReport.load("/tmp/multi.json")
```

---

## 6. Длина волокна (`length_source`)

| Источник | Откуда |
|----------|--------|
| `opticalen` | оптическая длина из модели fiber |
| `geo` / `geo_api` | геометрия × `geo_slack_k` |
| `cache` | DataCache |
| `missing` / `unknown` | длина неизвестна → db=0 + warning |

---

## 7. Алгоритм сегментов

По vertex-path:

1. fiber↔fiber (разные side, тот же id) → `fiber` (длина × dB/km triple)
2. splitter↔splitter (тот же id) → `splitter` (`splitter_port_db_triple`)
3. внутренний cross → `adapter` (`cross_loss_mode`)
4. внешние стыки → `splice` / `connector`
5. force по `connect_id` → `force`

Суммы min/calc/max по сегментам → `total_db_*`.

---

## 8. Связь с NetworkTopology

```python
nt = NetworkTopology(client, cache=DataCache())
nt.build_from_device("olt", 11808, port="1-8")

att = Attenuation(topology=nt, wavelength=1490)
res = att.calculate()
res = att.calculate("customer", 17711, "olt", 11808, obj2_port=3)

linear = nt.get_linear("customer", 17711, "olt", 11808)
att2 = Attenuation(topology=linear, wavelength=1490)
```

См. [topology.md](topology.md).

---

## 9. Типичные ошибки

| Ошибка | Что сделать |
|--------|-------------|
| `не указаны объекты и CGraph не задан` | `cgraph=` / `topology=` или obj1 |
| `для fiber укажите port` | номер ОВ |
| `нет пути в CGraph` | проверить коммутацию / компоненты |
| `src=estimated` | добавить сплиттер в JSON / `update_template` |
| `src=ratio:…` | ports пусты → ratio_defaults |

---

## 10. Полный пример

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import NetworkTopology, DataCache, Attenuation
from simpleworkernet.utils.topology.attenuation import (
    generate_template, update_template, MultiPathReport,
)

client = WorkerNetClient(...)
cache = DataCache()

generate_template(client, splitter_catalog_names=("PLC", "FBT"), cache=cache)
update_template(client, splitter_catalog_names=("PLC", "FBT"), cache=cache)

att = Attenuation(client=client, cache=cache, wavelength=1490)
res = att.calculate("customer", 17711, "olt", 11808, obj2_port=11)
print(res.to_table())
res.save("/tmp/att_17711.json")

nt = NetworkTopology(client, cache=cache)
nt.build_from_customer(17711)
att = Attenuation(topology=nt, wavelength=1490)
res = att.calculate()
if isinstance(res, MultiPathReport):
    print(res.count, res.total_db_avg, res.total_db_min, res.total_db_max)
    res.save("/tmp/multi.json")
else:
    print(res.to_table())
```
