# Графовая топология

**Зависимость:** `pip install python-igraph`

Модуль: `simpleworkernet.utils.topology`.

```python
from simpleworkernet import Topology, CGraph, FNGraph
from simpleworkernet.utils.topology import (
    DataCache, ObjKey, Interface,
    merge_cgraphs, merge_fngraphs,
    TYPE_OLT, TYPE_FIBER, TYPE_SPLITTER, TYPE_CUSTOMER,
)
```

## Типы графов

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | интерфейсы: `obj_type` + `obj_id` + `side` + `port` | коммутации |
| **FNGraph** | `node_id` | `fiber_id` |

Константы типов: `TYPE_CUSTOMER`, `TYPE_FIBER`, `TYPE_SPLITTER`, `TYPE_CROSS`, `TYPE_CWDM`, `TYPE_SWITCH`, `TYPE_OLT`, `TYPE_ONU`, `TYPE_RADIO`, плюс наборы `DEVICE_TYPES`, `SIDE_TYPES`, `TERMINAL_TYPES`.

## Topology — фасад

```python
from simpleworkernet import WorkerNetClient, Topology
from simpleworkernet.utils.topology import DataCache

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()   # можно шарить между несколькими Topology
topo = Topology(client, cache=cache)
```

### Построение

| Метод | Точка входа |
|-------|-------------|
| `build_from_device(dev_type, dev_id, port=...)` | OLT / switch / … |
| `build_from_cross(cross_id, port=...)` | Кросс |
| `build_from_customer(customer_id)` | Абонент |
| `build_from_node(node_id)` | Узел |
| `build_from_fiber(fiber_id)` | Кабель/волокно |
| `build_from_splitter(splitter_id)` | Сплиттер |
| `build_from_cwdm(cwdm_id)` | CWDM |
| `build_from_cable(cable_id)` | Кабель |

Фильтры при build (где поддерживаются): `included_fibers`, `excluded_fibers`, `excluded_nodes`.

### Выборки и линейные пути

| Метод | Описание |
|-------|----------|
| `get_customers()` | Список абонентов в построенной топологии |
| `topology_from_commutation(obj_type, obj_id, ...)` | Линейная цепочка коммутаций (CGraph) |

```python
topo.build_from_device("olt", 12345, port=1)
customers = topo.get_customers()
linear = topo.topology_from_commutation("customer", customers[0])
```

### Сохранение

```python
topo.save_to_file("topo.json")
topo2 = Topology.load_from_file("topo.json", client=client, cache=cache)
```

## DataCache

Экземплярный кэш (не синглтон) для инвентаря, длин волокон, geo и промежуточных данных build. Один `DataCache` можно передать нескольким `Topology`.

Отличается от глобального `simpleworkernet.cache` (SmartDataCache схем полей).

## CGraph / FNGraph

Низкоуровневые графы на python-igraph:

- **CGraph** — вершины-интерфейсы (`CGraphVertex`), рёбра-коммутации (`CGraphEdge`).
- **FNGraph** — узлы сети и волокна между ними.

Слияние:

```python
from simpleworkernet.utils.topology import merge_cgraphs, merge_fngraphs

cg = merge_cgraphs(cg1, cg2)
fg = merge_fngraphs(fg1, fg2)
```

## Связь с затуханиями

После build линейного CGraph считается attenuation **по запросу** (не во время build):

```python
from simpleworkernet.utils.topology import Attenuation, AttenuationCatalog

linear = topo.topology_from_commutation("customer", customer_id)
att = Attenuation(linear.cgraphs[0], catalog=AttenuationCatalog.with_defaults(),
                  wavelength=1550, cache=topo._cache, client=client)
report = att.olt_to_customer(customer_id)
```

Подробнее: [Затухания](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/attenuation.md).
