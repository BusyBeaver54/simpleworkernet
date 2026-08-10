# Оптические затухания

Расчёт **по запросу** (не при `build` топологии) по уже построенному **CGraph**.

```python
from simpleworkernet.utils.topology import (
    Topology, Attenuation, AttenuationCatalog, PathReport,
)
from simpleworkernet.utils.topology.attenuation.template import generate_template
```

## Типичный сценарий

```python
topo = Topology(client)
topo.build_from_device("olt", 12345, port=1)
linear = topo.topology_from_commutation("customer", customer_id)

cat = AttenuationCatalog.with_defaults()
# cat = AttenuationCatalog.from_json("my_profiles.json")
# cat.force_fiber(23682, 0.20)
# cat.force_splitter_port(35196, port=3, db=10.5)

att = Attenuation(
    linear.cgraphs[0],
    catalog=cat,
    wavelength=1550,
    cache=topo._cache,
    client=client,
)
report = att.olt_to_customer(customer_id)
print(report.to_table())
print(report.total_db, report.by_kind())
```

## Attenuation — методы расчёта

| Метод | Назначение |
|-------|------------|
| `path(src, dst)` | Shortest path + сумма сегментов |
| `along_linear()` | Обход линейного CGraph по порядку |
| `olt_to_customer(id)` | Downstream OLT → абонент |
| `customer_to_olt(id)` | Upstream |
| `olt_to_splitter_out(id, port)` | До выхода сплиттера |
| `budget_summary()` | Сводка по абонентам графа |
| `worst_customer()` | Худший бюджет |

## PathReport

| Атрибут / метод | Описание |
|-----------------|----------|
| `total_db` | Суммарное затухание, дБ |
| `segments` | Список `AttenuationSegment` |
| `warnings` / `missing` | Предупреждения и отсутствующие данные |
| `to_table()` | Текстовая таблица сегментов |
| `to_dict()` | Сериализация |
| `by_kind()` | Суммы по типам сегментов |

## Сегменты пути (`kind`)

| kind | Источник |
|------|----------|
| `fiber` | α(дБ/км) × L(км); L: opticalen2 → opticalen → geo×k → geo_api |
| `splitter` | порт OUT (side=2): force → instance → catalog → ratio → estimate |
| `adapter` | internal-ребро кросса |
| `splice` / `connector` | внешние стыки |
| `force` | override на connect_id / fiber / splitter port |

Эвристика сплиттера: side1 ≈ in, side2 ≈ out; путь идёт вдоль линейного CGraph.

## AttenuationCatalog

| Метод | Описание |
|-------|----------|
| `with_defaults()` | Каталог из встроенного `defaults.json` |
| `from_json(path)` | Загрузка пользовательского JSON |
| `force_fiber(id, db_per_km)` | Жёсткий α для волокна |
| `force_splitter_port(id, port, db)` | Жёсткое затухание порта |

### Defaults (`defaults.json`)

| Параметр | 1310 nm | 1490 nm | 1550 nm |
|----------|---------|---------|----------|
| fiber дБ/км | 0.35 | 0.28 | 0.22 |
| splice | 0.05 дБ | | |
| connector | 0.30 дБ | | |
| adapter | 0.20 дБ | | |
| geo_slack_k | 1.03 | | |
| splitter_excess | 0.5 дБ | | |

Типовые ratio-профили: `1x2_50/50`, `1x2_5/95`, …, `1x4_equal`, `1x8_equal`.

## Шаблон из live API

```python
cat = generate_template(client, cache=topo._cache, path="attenuation.json")
# дозаполнить ports / db_per_km вручную, затем:
cat = AttenuationCatalog.from_json("attenuation.json")
```
