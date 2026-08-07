# Оптические затухания (Attenuation)

Расчёт **по запросу**. CGraph можно передать готовый или он построится сам.

---

## 1. Общая идея

1. Сгенерировать и проверить JSON-каталог затуханий.
2. Вызвать `Attenuation.calculate(obj1_type, obj1_id, obj2_type, obj2_id, ...)`.
3. Если пути нет — `AttenuationError`.

Файл каталога: `~/.config/simpleworkernet/attenuation_<host>.json`

---

## 2. Быстрый старт

```python
from simpleworkernet.utils.topology.attenuation import (
    generate_template, load_attenuation_catalog,
    Attenuation, AttenuationError,
)

cat = generate_template(client, ("PLC", "FBT"), cache=cache)
cat = load_attenuation_catalog(client)

att = Attenuation(catalog=cat, client=client, cache=cache)
try:
    r = att.calculate("olt", 1, "customer", 100, wavelength=1490)
    print(r.total_db)
    print(r.to_table())
except AttenuationError as e:
    print(e)

# с готовым графом:
att = Attenuation(cgraph, catalog=cat)
r = att.calculate("cross", "12", "splitter", 5, wavelength=1490)
```

---

## 3. Каталог JSON

См. `generate_template` / `update_template` / `load_attenuation_catalog`.

Секции `cables` и `splitters` — **списки**. Порт equal — ключ `"all"`.

---

## 4. API: calculate

```python
att = Attenuation(
    cgraph=None,       # опционально
    catalog=cat,
    client=client,     # обязателен, если cgraph нет
    cache=cache,
    wavelength=1490,
    use_max=False,
)

r = att.calculate(
    obj1_type, obj1_id,
    obj2_type, obj2_id,
    wavelength=1490,
    obj1_side=None, obj1_port=None,
    obj2_side=None, obj2_port=None,
    direction=None,    # downstream / upstream / auto
    use_max=None,
)
```

**Построение графа:** если `cgraph` не задан или в нём нет обоих объектов — `CGraph.build` от obj1, при необходимости от obj2.

**Исключения (`AttenuationError`):**
- нет `client` и нет графа;
- объект не найден в графе;
- нет пути между объектами.

Низкоуровнево: `att.path(source, target)` при уже заданном `cgraph`.

`PathReport`: `total_db`, `segments`, `to_table()`, `by_kind()`, `warnings` / `missing`.

---

## 5. Приоритет значений

Сплиттер: force → instance → catalog → package ratio → estimated.

Волокно: force → кабель → defaults.fiber_db_per_km.

---

## 6. Рабочий процесс

1. `generate_template(client, ("PLC", "FBT"))`
2. Проверить/поправить JSON (1490 для GPON downstream).
3. `att.calculate("olt", olt_id, "customer", cid, wavelength=1490)`
4. `update_template(...)` при появлении новых позиций в БД.
