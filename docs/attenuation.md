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
    # fiber ↔ fiber: port = номер ОВ (обязателен хотя бы у одного)
    r = att.calculate(
        "fiber", 13259,
        "fiber", 13235,
        obj1_port=1, obj2_port=1,   # номер ОВ
        # obj1_side / obj2_side опциональны — без них берутся ближайшие стороны
        wavelength=1490,
    )
    print(r.total_db)
    print(r.to_table())
except AttenuationError as e:
    print(e)
```

---

## 3. Кабели: side и port

| Параметр | Смысл |
|----------|--------|
| `side` | Сторона кабеля (1 или 2), **не** направление сигнала. Считать можно в любую сторону. |
| без `side` | Пара **ближайших** сторон (кратчайший путь в графе). |
| `port` | **Номер ОВ** в кабеле (`clps_mid`). |

Для **fiber↔fiber** укажите `port` (номер ОВ) **хотя бы у одного** конца — иначе по всем волокнам кабеля не получится один линейный CGraph.

---

## 4. API: calculate

```python
att = Attenuation(
    cgraph=None,
    catalog=cat,
    client=client,
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
    direction=None,  # только метка в отчёте, на сумму не влияет
    use_max=None,
)
```

**Построение графа:** если `cgraph` не задан — `CGraph.build` от obj1 / obj2, при необходимости merge.

**Исключения (`AttenuationError`):** нет client/графа; объект не найден; нет пути; fiber↔fiber без port.

`PathReport`: `total_db`, `segments`, `to_table()`, `by_kind()`, `warnings` / `missing`.

---

## 5. Приоритет значений

Сплиттер: force → instance → catalog → package ratio → estimated.

Волокно: force → кабель → defaults.fiber_db_per_km.

---

## 6. Рабочий процесс

1. `generate_template(client, ("PLC", "FBT"))`
2. Проверить JSON (для GPON downstream — λ **1490**).
3. `att.calculate("fiber", a, "fiber", b, obj1_port=1, obj2_port=1, wavelength=1490)`
4. `update_template(...)` при новых позициях в БД.
