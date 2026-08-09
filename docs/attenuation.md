# Оптические затухания (Attenuation)

Расчёт **по запросу**. CGraph можно передать готовый или он построится между двумя объектами.

```python
from simpleworkernet.utils.topology.attenuation import (
    Attenuation, AttenuationError,
    AttenuationCatalog, PathReport, MultiPathReport,
    generate_template, update_template, load_attenuation_catalog,
    save_path_report, load_path_report,
)
```

---

## 1. Рабочий процесс

1. `generate_template(client, splitter_catalog_names=(...))` — JSON с дефолтами + объекты из БД.
2. Проверить и поправить значения.
3. `update_template(...)` — дописать новое из БД без затирания правок.
4. `Attenuation.calculate(...)`.

Файл: `~/.config/simpleworkernet/attenuation_<host>.json`

---

## 2. Каталог JSON

```python
cat = generate_template(client, splitter_catalog_names=("PLC", "FBT"), cache=cache)
cat = update_template(client, splitter_catalog_names=("PLC", "FBT"), cache=cache)
cat = load_attenuation_catalog(client)
```

`splitter_catalog_names` — обязательный параметр.

Приоритет: force (id/uuid) → экземпляр JSON → catalog/ratio → пакетные дефолты.
Длина волны: точное совпадение → ближайшая указанная (`log.info`).
Порт сплиттера не найден → ключ `"all"`.
`use_max=True` → `db_max`.

---

## 3. `Attenuation.calculate`

```python
att = Attenuation(cgraph=None, catalog=cat, client=client, cache=cache, wavelength=1490)

r = att.calculate(
    obj1_type, obj1_id, obj2_type, obj2_id,
    wavelength=1490,
    obj1_side=None, obj1_port=None,
    obj2_side=None, obj2_port=None,
)
# PathReport или MultiPathReport (несколько ветвей)
```

### PathReport

`total_db`, `segments`, `to_table()`, `to_dict()`, `by_kind()`, `save_path_report` / `load_path_report`.

### MultiPathReport

`branches`, `total_db_min` / `max` / `avg`, `branch_for(...)`, `to_table()`.

---

## 4. Варианты пар объектов

### OLT ↔ customer / onu

```python
att.calculate("olt", 10, "customer", 1001, wavelength=1490, obj1_port=3)
```

### Fiber ↔ fiber

```python
att.calculate(
    "fiber", 13259, "fiber", 13235,
    obj1_side=2, obj1_port=1,  # side = сторона кабеля, port = номер ОВ
    obj2_side=2, obj2_port=1,
    wavelength=1490,
)
```

`port` (ОВ) обязателен хотя бы у одного конца.

### Cross / splitter

```python
att.calculate("cross", uuid, "customer", 1001, obj1_side=1, obj1_port=5)
att.calculate("splitter", 55, "customer", 1001, obj1_side=2, obj1_port=3)
```

---

## 5. Связь с NetworkTopology

```python
from simpleworkernet.utils.topology import NetworkTopology, Attenuation

nt = NetworkTopology(client, cache=cache)
nt.build_from_device("olt", 10, port=(1, 8))
linear = nt.get_linear("customer", 1001, "olt", 10)
att = Attenuation(linear.cgraphs[0], catalog=cat, client=client, cache=cache)
r = att.calculate("olt", 10, "customer", 1001, wavelength=1490)
```

Подробнее о графах: [topology.md](topology.md).
