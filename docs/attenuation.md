# Оптические затухания (Attenuation)

Модуль считает вносимое затухание вдоль пути коммутации (волокно, сплиттеры, сварки, коннекторы, адаптеры кросса).

```python
from simpleworkernet.utils.topology.attenuation import (
    Attenuation, AttenuationError,
    AttenuationCatalog, PathReport, MultiPathReport,
    generate_template, update_template, load_attenuation_catalog,
    save_path_report, load_path_report,
)
# или
from simpleworkernet.utils.topology import Attenuation, PathReport, MultiPathReport
```

---

## 1. Рабочий процесс (обязательно)

1. **Сгенерировать JSON-каталог** из дефолтов пакета + объектов БД.
2. **Проверить** значения (особенно сплиттеры и кабели), поправить вручную.
3. При появлении новых объектов в БД — **`update_template`** (не затирает ручные правки).
4. Считать затухания через **`Attenuation.calculate(...)`**.

Файл каталога (на хост):

```text
~/.config/simpleworkernet/attenuation_<hostname>.json
```

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology.attenuation import (
    generate_template, update_template, load_attenuation_catalog,
)

client = WorkerNetClient(...)

# первый раз — создать файл
cat = generate_template(
    client,
    splitter_catalog_names=("PLC", "FBT"),  # обязательно: имена каталогов в БД
    cache=None,
    overwrite=False,  # если файл есть → update_template
)

# позже — дописать новые сплиттеры/кабели из БД
cat = update_template(client, splitter_catalog_names=("PLC", "FBT"))

# загрузка при расчёте (делается и автоматически)
cat = load_attenuation_catalog(client)
```

`splitter_catalog_names` — **обязательный** параметр: имена каталогов сплиттеров в WorkerNet (как в БД).

---

## 2. Структура JSON-каталога

```json
{
  "defaults": {
    "fiber_db_per_km": { "1310": {"db": 0.34, "db_max": 0.4}, "1490": {...}, "1550": {...} },
    "splice_db": {"db": 0.05, "db_max": 0.1},
    "connector_db": {"db": 0.15, "db_max": 0.3},
    "adapter_db": {"db": 0.3, "db_max": 0.5},
    "cross_loss_mode": "adapter",
    "geo_slack_k": 1.03,
    "splitter_excess_db": 0.5
  },
  "cables": [
    { "id": "12", "name": "ОКС-16", "db_per_km": { "1550": {"db": 0.19, "db_max": 0.22} } }
  ],
  "splitters": [
    {
      "catalog_id": "15",
      "name": "FBT 1x2 50/50",
      "ratio": "1x2_50/50",
      "ports": {
        "1": { "name": "50%", "attenuation": { "1490": {"db": 3.61, "db_max": 4.31} } },
        "2": { "name": "50%", "attenuation": { "1490": {"db": 3.61, "db_max": 4.31} } }
      }
    }
  ],
  "cross_adapters": { "default": {"db": 0.3, "db_max": 0.5} },
  "force": { "splitters": {}, "edges": {} }
}
```

### Откуда берутся значения (приоритет)

| Приоритет | Источник | `source` в сегменте |
|-----------|----------|---------------------|
| 1 | `force.splitters[id]` / `force.edges` | `force` |
| 2 | запись в `splitters[]` по **имени** | `name` |
| 3 | запись по instance id | `instance` |
| 4 | запись по `catalog_id` | `catalog` |
| 5 | `ratio_defaults` / угаданный ratio | `ratio:1x2_50/50` |
| 6 | оценка `10·log10(N) + excess` | `estimated` |

Для кабеля: имя из модели → `cables[]` → `defaults.fiber_db_per_km`.

### Длина волны

В `calculate(wavelength=1490)` берётся карта затуханий на этой λ.  
Если точной нет — **ближайшая** указанная + сообщение в `log.info`.

### Порт сплиттера

- По номеру: `ports["2"]`.
- Имя порта (`port_name`) берётся из JSON: `ports["2"]["name"]` (например `"50%"`).
- Если номера нет — ключ `"all"` (равномерные PLC).

### Кросс / коннекторы

- `cross_loss_mode: "adapter"` — один раз `adapter_db` (вход+выход кросса).
- `"connectors"` — по `connector_db` на каждое ребро к кроссу.
- Сплиттер↔сплиттер (разные id) — только сварка, без коннекторов.
- OLT / абонент — `connector_db` (0.15 по умолчанию).

Меняйте значения в **своём** JSON (`defaults.adapter_db` и т.д.) — при расчёте читается он, не пакетные дефолты.

---

## 3. Создание `Attenuation`

```python
from simpleworkernet.utils.topology.attenuation import Attenuation

# каталог подтянется из ~/.config/.../attenuation_<host>.json при наличии client
att = Attenuation(
    cgraph=None,          # готовый CGraph или None (построится в calculate)
    catalog=None,         # AttenuationCatalog или None → load / defaults
    client=client,
    cache=cache,          # DataCache топологии, желательно
    wavelength=1490,      # дефолтная λ
    use_max=False,        # True → db_max
)
```

---

## 4. `calculate` — три режима

### 4.1. Весь CGraph (без точек)

Если при создании передан `cgraph`, можно не указывать объекты:

```python
from simpleworkernet.utils.topology import NetworkTopology, Attenuation

nt = NetworkTopology(client)
nt.build_from_customer(17711)
cg = nt.cgraphs[0]

att = Attenuation(cgraph=cg, client=client, wavelength=1490)
res = att.calculate()   # PathReport или MultiPathReport
print(res.to_table())
```

Ищутся пути customer → olt/switch/onu/radio (или листья графа).  
Одна ветвь → `PathReport`, несколько → `MultiPathReport`.

**Без CGraph и без obj1** → `AttenuationError`.

### 4.2. От одной точки (obj2 не обязателен)

```python
# абонент → ближайший/все OLT в построенном графе
res = att.calculate("customer", 17711, wavelength=1490)

# OLT → абоненты/ветви
res = att.calculate("olt", 11808, obj1_port=11, wavelength=1490)
```

Для `customer` / `olt` / `switch` **side и port не обязательны**.

### 4.3. Между двумя объектами

```python
res = att.calculate(
    obj1_type, obj1_id,
    obj2_type, obj2_id,
    wavelength=1490,
    obj1_side=None, obj1_port=None,
    obj2_side=None, obj2_port=None,
    direction=None,   # "downstream" / "upstream" / None (авто)
    use_max=False,
    max_paths=50,
)
```

Если CGraph не передан — строится по стратегии пары типов (см. ниже).

---

## 5. Как задавать объекты

| Тип | `obj*_type` | id | side | port |
|-----|-------------|-----|------|------|
| Абонент | `"customer"` | int | не нужен | не нужен |
| OLT | `"olt"` | int | не нужен | желателен (порт GPON) |
| Switch / ONU / Radio | `"switch"` / `"onu"` / `"radio"` | int | не нужен | по ситуации |
| Сплиттер | `"splitter"` | int | 1=вход, 2=выход | номер порта |
| CWDM | `"cwdm"` | int | сторона | порт |
| Кросс | `"cross"` | **uuid** (str) | 1/2 | порт |
| Волокно/кабель | `"fiber"` | int (id кабеля) | 1/2 сторона узла | **номер ОВ** |

### Примеры

```python
# Абонент → OLT
res = att.calculate(
    "customer", 17711,
    "olt", 11808,
    obj2_port=11,
    wavelength=1490,
)

# OLT → абонент (явные порты)
res = att.calculate(
    "olt", 11808, "customer", 17711,
    obj1_port=11,
    wavelength=1490,
)

# Участок между двумя кабелями (коридор по FNGraph)
res = att.calculate(
    "fiber", 13259, "fiber", 13235,
    obj1_side=2, obj1_port=1,   # side = сторона сооружения, port = ОВ
    obj2_side=2, obj2_port=1,
    wavelength=1490,
)
# Для fiber↔fiber port обязателен хотя бы у одного конца.

# От сплиттера
res = att.calculate(
    "splitter", 16926, "customer", 17711,
    obj1_side=2, obj1_port=4,
    wavelength=1490,
)

# От кросса
res = att.calculate(
    "cross", "8a23d025-940e-4a54-884f-2d305e873f12",
    "customer", 17711,
    obj1_side=1, obj1_port=4,
    wavelength=1490,
)
```

---

## 6. Логика построения CGraph внутри calculate

Если `self.g` уже содержит оба объекта — перестройки нет.

Иначе (нужен `client`):

| Пара типов | Стратегия |
|------------|-----------|
| fiber ↔ fiber | FNGraph-коридор: узлы кабелей → included/excluded fibers → CGraph |
| olt → customer | build от OLT |
| customer → olt/switch | build от устройства (или от customer) |
| splitter/cwdm ↔ customer | от сплиттера/CWDM |
| с участием cross | от любого конца, merge при необходимости |
| только obj1 | build от obj1, цели — терминалы в графе |

Фильтры `included_fibers` / `excluded_fibers` для fiber-коридора выставляются автоматически.

Недостаточно данных (например fiber без port) → `AttenuationError` с понятным текстом.

---

## 7. Результат: PathReport и MultiPathReport

### PathReport (один путь)

```python
print(res.total_db)
print(res.to_table())
print(res.by_kind())          # {'fiber': ..., 'splitter': ..., 'adapter': ...}
print(res.fiber_db, res.splitter_db, res.joint_db)
print(res.fiber_length_m)

for s in res.segments:
    print(s.kind, s.db, s.obj_name, s.port, s.port_name, s.source)

# сериализация
from simpleworkernet.utils.topology.attenuation import save_path_report, load_path_report
save_path_report(res, "report.json")
res2 = load_path_report("report.json")
# или
res.save("report.json")
res2 = PathReport.load("report.json")
```

Сегменты:

| kind | Смысл |
|------|--------|
| `fiber` | кабель, dB = L_km × dB/km |
| `splitter` | IL порта сплиттера |
| `splice` | сварка |
| `adapter` | адаптер кросса (вход+выход) |
| `connector` | коннектор (OLT, абонент, режим connectors) |
| `force` | ручное значение из JSON |

В `description` / `obj_name` / `port_name` / `meta.host` — имена из **моделей API** и JSON-каталога (не `str(Interface)`).

### MultiPathReport (несколько ветвей)

```python
if isinstance(res, MultiPathReport):
    print(res.count, res.total_db_min, res.total_db_max, res.total_db_avg)
    print(res.to_table())
    for b in res.branches:
        print(b.from_label, "→", b.to_label, b.total_db)
    branch = res.branch_for("customer", 17711)
```

Появляется при ветвлении на сплиттерах/CWDM или при нескольких путях между объектами.

---

## 8. Связь с NetworkTopology

```python
from simpleworkernet.utils.topology import NetworkTopology, Attenuation

nt = NetworkTopology(client)
nt.build_from_device("olt", 11808, port=11)
# или
nt.build_from_customer(17711)

att = Attenuation(cgraph=nt.cgraphs[0], client=client, cache=nt.cache, wavelength=1490)

# по уже построенному графу
res = att.calculate()
# или уточнить концы
res = att.calculate("customer", 17711, "olt", 11808, wavelength=1490)
```

Линейный кусок:

```python
linear_nt = nt.get_linear("customer", 17711, "olt", 11808)
att = Attenuation(cgraph=linear_nt.cgraphs[0], client=client, wavelength=1490)
res = att.calculate()
```

Подробнее про построение графов — [topology.md](topology.md).

---

## 9. Типичные ошибки

| Ошибка | Причина / что сделать |
|--------|------------------------|
| `не указаны объекты и CGraph не задан` | Передать `cgraph=` или `obj1_type/id` |
| `для fiber укажите port` | Номер ОВ хотя бы с одной стороны |
| `объект не найден в графе` | Проверить id/side/port или построить граф вручную |
| `нет пути в CGraph` | Объекты в разных компонентах; проверить коммутацию |
| `src=estimated` у сплиттера | Нет записи в JSON — добавить имя/ports или `update_template` |
| `src=ratio:...` | Имя есть, но ports в JSON пусты → взяты ratio_defaults |
| adapter всегда 0.2 | Править `defaults.adapter_db` в **пользовательском** JSON |

---

## 10. Полный пример

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import NetworkTopology, DataCache
from simpleworkernet.utils.topology.attenuation import (
    Attenuation, generate_template, update_template, PathReport, MultiPathReport,
)

client = WorkerNetClient(base_url="https://wn.example", token="...")
cache = DataCache()

# каталог затуханий (один раз / периодически)
generate_template(client, splitter_catalog_names=("PLC", "FBT"), cache=cache)
# …правка JSON…
update_template(client, splitter_catalog_names=("PLC", "FBT"), cache=cache)

# вариант A: от абонента до OLT
att = Attenuation(client=client, cache=cache, wavelength=1490)
res = att.calculate(
    "customer", 17711,
    "olt", 11808,
    obj2_port=11,
    wavelength=1490,
)
print(res.to_table())
res.save("/tmp/att_17711.json")

# вариант B: сначала топология, потом весь граф
nt = NetworkTopology(client, cache=cache)
nt.build_from_customer(17711)
att = Attenuation(cgraph=nt.cgraphs[0], client=client, cache=cache, wavelength=1490)
res = att.calculate()
if isinstance(res, MultiPathReport):
    print("ветвей:", res.count, "min/max:", res.total_db_min, res.total_db_max)
else:
    print(res.to_table())
```
