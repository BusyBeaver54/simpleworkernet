# Графовая топология

**Зависимость:** `pip install python-igraph`  
(или `pip install "simpleworkernet[topology]"`)

Модуль: `simpleworkernet.utils.topology`.

```python
from simpleworkernet.utils.topology import (
    NetworkTopology,
    CGraph, FNGraph, DataCache,
    ObjKey, Interface,
    merge_cgraphs, merge_fngraphs,
    TopologyBuildError,
    TYPE_OLT, TYPE_FIBER, TYPE_SPLITTER, TYPE_CROSS,
    TYPE_CUSTOMER, TYPE_CWDM, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
    DEVICE_TYPES, SIDE_TYPES, TERMINAL_TYPES, ALL_OBJECT_TYPES,
    Attenuation, PathReport, MultiPathReport, AttenuationSegment,
)
```

Оркестратор — **`NetworkTopology`**.

---

## 1. Типы графов

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | Интерфейсы `(obj_type, obj_id, side, port)` | Коммутации (в т.ч. внутренние на кроссе/сплиттере) |
| **FNGraph** | Узлы (node) | Кабели (fiber) между узлами |

`NetworkTopology` хранит список CGraph и один FNGraph, строит их через `build_from_*`.

---

## 2. Быстрый старт

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import NetworkTopology, DataCache

client = WorkerNetClient(...)
cache = DataCache()
nt = NetworkTopology(client, cache=cache)

nt.build_from_customer(17711)
# или: build_from_device / build_from_node / build_from_fiber / …

print(nt.get_customers(), nt.get_devices(), nt.get_fibers())
linear = nt.get_linear("customer", 17711, port=0)
```

См. также [attenuation.md](attenuation.md) для расчёта затуханий по построенному CGraph.

---

## 3. Ключи и интерфейсы

- `ObjKey(obj_type, id)` — объект топологии
- `Interface(obj, side, port)` — порт/сторона объекта
- Единое поле **`port`**: у fiber — номер ОВ; у device — порт; у splitter — выходной порт

---

## 4. DataCache

Кэш объектов и коммутаций. Можно шарить между несколькими `NetworkTopology`.

```python
cache = DataCache(client, preload_types=["node", "device", "fiber"])
cache.wait_preload()
```

---

## 5. LinearPathFinder / get_linear

```python
from simpleworkernet.utils.topology.linear import LinearPathFinder

finder = LinearPathFinder(nt)
sub = finder.trace("customer", 17711, port=0)  # CGraph-цепочка

# или через оркестратор:
nt2 = nt.get_linear("customer", 17711, port=0)
```

---

Подробнее о структуре исходников: [package-structure.md](package-structure.md).
