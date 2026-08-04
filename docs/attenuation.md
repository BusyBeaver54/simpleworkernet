# Оптические затухания (Attenuation)

Расчёт **по запросу** (не при `build`) по уже построенному CGraph.

```python
from simpleworkernet.utils.topology import (
    Topology, Attenuation, AttenuationCatalog,
)
from simpleworkernet.utils.topology.attenuation.template import generate_template

# 1) топология
topo = Topology(client)
topo.build_from_device("olt", 12345, port=1)
linear = topo.topology_from_commutation("customer", customer_id)

# 2) каталог профилей (defaults + overrides)
cat = AttenuationCatalog.with_defaults()
# cat = AttenuationCatalog.from_json("my_profiles.json")
# cat.force_fiber(23682, 0.20)
# cat.force_splitter_port(35196, port=3, db=10.5)

# 3) расчёт
att = Attenuation(
    linear.cgraphs[0],
    catalog=cat,
    wavelength=1550,
    cache=topo._cache,
    client=client,
)
report = att.olt_to_customer(customer_id)
# или: att.along_linear()
print(report.to_table())
print(report.total_db, report.by_kind())
```

## Сегменты пути

| kind | Источник |
|------|----------|
| `fiber` | α(дБ/км) × L(км); L: opticalen2 → opticalen → geo×k → geo_api |
| `splitter` | порт OUT (side=2): force → instance → catalog → ratio → estimate |
| `adapter` | internal-ребро кросса |
| `splice` / `connector` | внешние стыки |
| `force` | override на connect_id / fiber / splitter port |

## Defaults (`defaults.json`)

| Параметр | 1310 nm | 1490 nm | 1550 nm |
|----------|---------|---------|----------|
| fiber дБ/км | 0.35 | 0.28 | 0.22 |
| splice | 0.05 дБ | | |
| connector | 0.30 дБ | | |
| adapter | 0.20 дБ | | |
| geo_slack_k | 1.03 | | |
| splitter_excess | 0.5 дБ | | |

Типовые ratio-профили сплиттеров: `1x2_50/50`, `1x2_5/95`, …, `1x4_equal`, `1x8_equal`.

## Каталог и шаблон

```python
# шаблон из live API (кабели + сплиттеры)
cat = generate_template(client, cache=topo._cache, path="attenuation.json")
# пользователь дозаполняет ports / db_per_km, затем:
cat = AttenuationCatalog.from_json("attenuation.json")
```

## Удобные запросы

| Метод | Назначение |
|-------|------------|
| `path(src, dst)` | shortest path + сумма сегментов |
| `along_linear()` | обход линейного CGraph |
| `olt_to_customer(id)` | downstream OLT→абонент |
| `customer_to_olt(id)` | upstream |
| `olt_to_splitter_out(id, port)` | до выхода сплиттера |
| `budget_summary()` / `worst_customer()` | по всем абонентам графа |

`PathReport`: `total_db`, `segments`, `to_table()`, `to_dict()`, `by_kind()`, `warnings`, `missing`.
