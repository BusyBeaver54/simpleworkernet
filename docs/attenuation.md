# Оптические затухания (Attenuation)

Расчёт **по запросу**. CGraph можно передать готовый или он построится автоматически между двумя объектами.

Модуль: `simpleworkernet.utils.topology.attenuation`.

```python
from simpleworkernet.utils.topology.attenuation import (
    Attenuation, AttenuationError,
    AttenuationCatalog, PathReport, MultiPathReport,
    generate_template, update_template, load_attenuation_catalog,
    save_path_report, load_path_report,
)
```

---

## 1. Рабочий процесс (обязательный порядок)

1. **Сгенерировать JSON-каталог** затуханий с дефолтами + объекты из БД.
2. **Проверить и при необходимости поправить** значения (особенно реальные IL сплиттеров).
3. При появлении новых кабелей/сплиттеров в БД — **`update_template`** (добавляет только отсутствующее).
4. Считать затухание через **`Attenuation.calculate`**.

Файл каталога (общий для приложений, не «рядом с проектом»):

```text
~/.config/simpleworkernet/attenuation_<host>.json
```

`<host>` берётся из `WorkerNetClient` (если не задано иное при генерации).

---

## 2. Каталог JSON

### 2.1. Генерация и обновление

```python
from simpleworkernet.utils.topology.attenuation import (
    generate_template, update_template, load_attenuation_catalog,
)

# splitter_catalog_names — обязательный параметр (имена каталогов в БД)
cat = generate_template(
    client,
    splitter_catalog_names=("PLC", "FBT"),  # как в вашей БД
    cache=cache,
    # host="other-host",  # опционально переопределить имя файла
)

# позже: дописать новые объекты из БД, не затирая ручные правки
cat = update_template(client, splitter_catalog_names=("PLC", "FBT"), cache=cache)

cat = load_attenuation_catalog(client)
```

### 2.2. Структура (упрощённо)

- **Сплиттеры** — плоский список элементов с полями идентификации (`id` / `uuid` / `name` / ratio) и портами.
- Порт с равномерным делением: ключ **`"all"`** (если конкретный номер порта не найден — берётся `all`).
- На каждом порте — затухания по длинам волн (`1310`, `1490`, `1550`) с `db` / `db_max`.
- **Кабели** — по `name` (без завода), `db_per_km` по длинам волн.
- **Force-overrides** — точечные значения по id/uuid конкретного экземпляра (высший приоритет).

Лишних ключей `by_id` / `by_name` / `by_ratio` / `items` / `wavelengths_nm` **нет** — поиск идёт по полям элемента.

### 2.3. Приоритет значений при расчёте

| Объект | Порядок |
|--------|---------|
| Сплиттер | force (id/uuid) → экземпляр в JSON → catalog/ratio → пакетные дефолты → оценка |
| Волокно | force → кабель по name → `defaults.fiber_db_per_km` |
| Длина волны | точное совпадение → **ближайшая** указанная λ (пишется в `log.info`) |

`use_max=True` — брать `db_max` вместо `db`.

---

## 3. `Attenuation.calculate`

Единый метод. Пары `olt_to_customer` и т.п. **удалены**.

```python
att = Attenuation(
    cgraph=None,          # необязателен
    catalog=cat,
    client=client,
    cache=cache,
    wavelength=1490,
    use_max=False,
)

r = att.calculate(
    obj1_type, obj1_id,
    obj2_type, obj2_id,
    wavelength=1490,      # перекрывает default
    obj1_side=None,
    obj1_port=None,
    obj2_side=None,
    obj2_port=None,
    direction=None,       # только метка в отчёте
    use_max=None,
)
```

**Возврат:**

- один путь → `PathReport`;
- несколько простых путей (нелинейный CGraph) → `MultiPathReport`.

**Исключения (`AttenuationError`):** нет client при необходимости build; объект не в графе; нет пути; для fiber↔fiber не указан port ни у одного конца.

### 3.1. Если CGraph не передан

`Attenuation` пытается построить граф по `obj1`/`obj2` (в т.ч. fiber-коридоры через узлы `node1_id`/`node2_id` со стороны кабеля).

### 3.2. PathReport

```python
r.total_db
r.segments          # list[AttenuationSegment]
r.to_table()
r.to_dict()
r.by_kind()         # суммы по kind: fiber / splitter / splice / ...
r.warnings / r.missing

# сохранение / загрузка
save_path_report(r, path="report.json")
r2 = load_path_report("report.json")
```

### 3.3. MultiPathReport (нелинейный граф)

```python
r = att.calculate("olt", 1, "customer", 100, wavelength=1490)
if isinstance(r, MultiPathReport):
    print(r.count, r.total_db_min, r.total_db_max, r.total_db_avg)
    for b in r.branches:          # PathReport по каждой ветви
        print(b.total_db, b.to_label)
    print(r.branch_for("customer", 100))
    print(r.to_table())
```

Логика: все **простые пути** между endpoints (`topology.paths.simple_paths`); по каждому — полный расчёт сегментов; агрегат min/max/avg для бюджета.

---

## 4. Варианты исходных данных (obj1 / obj2)

Ниже — типичные пары и обязательные поля.

### 4.1. OLT ↔ абонент / ONU / radio

```python
r = att.calculate("olt", 10, "customer", 1001, wavelength=1490)
r = att.calculate("olt", 10, "onu", 55, obj1_port=3)  # порт OLT
```

- `side` для OLT/customer обычно не нужен;
- `obj1_port` — порт OLT (сужает старт при авто-build).

### 4.2. Fiber ↔ fiber (точки сварки / границы участка)

```python
r = att.calculate(
    "fiber", 13259, "fiber", 13235,
    obj1_side=2, obj1_port=1,   # side = сторона кабеля, port = номер ОВ
    obj2_side=2, obj2_port=1,
    wavelength=1490,
)
```

| Параметр | Смысл |
|----------|--------|
| `side` | Сторона кабеля **1 или 2** (не направление сигнала). 1 → `node1_id`, 2 → `node2_id` из `Fiber.get_list(object_id=...)`. |
| без `side` | Берутся ближайшие стороны (кратчайший путь). |
| `port` | **Номер оптического волокна**. Хотя бы у **одного** конца обязателен, иначе нельзя собрать один линейный CGraph. |

Направление сигнала для суммы dB не важно — считаем цепочку сегментов между точками.

### 4.3. Кросс ↔ что угодно

```python
r = att.calculate("cross", cross_uuid, "customer", 1001, obj1_side=1, obj1_port=5)
```

- `side` + `port` задают интерфейс на кроссе.

### 4.4. Сплиттер ↔ …

```python
r = att.calculate("splitter", 55, "customer", 1001, obj1_side=2, obj1_port=3)
```

- IL берётся для порта выхода; если порта нет в JSON — fallback на **`all`**.

### 4.5. Смешанные пары

Любая комбинация типов из `ALL_OBJECT_TYPES`, если в CGraph есть путь:

```python
att.calculate("node", node_id, "olt", 10)          # при поддержке build
att.calculate("switch", 3, "fiber", 13259, obj2_port=1, obj2_side=1)
```

Если связи нет — `AttenuationError`.

---

## 5. Как считается сумма

По вершинному пути CGraph:

1. **Волокно** — длина × dB/км (λ с nearest-fallback).
2. **Сплиттер** — insertion loss на порту (internal-ребро / пара вершин одного splitter id).
3. **Сварка / кросс / разъём** — по правилам сегментов (defaults + JSON).
4. Прочее — из каталога или 0 с warning в `missing`.

Сплиттер с равномерным делением: порт не найден → ключ `"all"`.

---

## 6. Связь с топологией

```python
from simpleworkernet.utils.topology import NetworkTopology, Attenuation

nt = NetworkTopology(client, cache=cache)
nt.build_from_device("olt", 10, port=(1, 8))

# линейный участок до абонента
linear = nt.get_linear("customer", 1001, "olt", 10)
att = Attenuation(linear.cgraphs[0], catalog=cat, client=client, cache=cache)
r = att.calculate("olt", 10, "customer", 1001, wavelength=1490)
```

Или без предварительного build — только `calculate` (граф соберётся внутри).

Подробнее про построение графов, `port`, `linear`, `get_linear`: [topology.md](topology.md).

---

## 7. Краткая шпаргалка

| Задача | Вызов |
|--------|-------|
| Создать JSON | `generate_template(client, splitter_catalog_names=(...))` |
| Дописать новое из БД | `update_template(client, splitter_catalog_names=(...))` |
| Загрузить каталог | `load_attenuation_catalog(client)` |
| Считать затухание | `att.calculate(t1, id1, t2, id2, wavelength=1490, ...)` |
| Fiber↔fiber | обязательно `port` (ОВ) хотя бы с одной стороны; `side` = сторона кабеля |
| Нелинейный граф | `MultiPathReport` с `branches`, min/max/avg |
| Сохранить отчёт | `save_path_report(r)` / `load_path_report(path)` |
