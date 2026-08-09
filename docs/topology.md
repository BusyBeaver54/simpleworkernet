# Графовая топология

**Зависимость:** `pip install python-igraph`

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
)
from simpleworkernet.utils.constants import ALL_OBJECT_TYPES
```

---

## 1. Типы графов

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | Интерфейсы `(type, id, side, port)` | Коммутации |
| **FNGraph** | Сооружения (`node_id`) | Кабели между узлами |

`NetworkTopology` хранит список CGraph и опционально один FNGraph.

---

## 2. Быстрый старт

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import NetworkTopology, DataCache

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()
nt = NetworkTopology(client, cache=cache)

nt.build_from_device("olt", 10, port="1-8")
```

---

## 3. Параметр `port`

| Формат | Пример |
|--------|--------|
| число | `port=5` |
| диапазон | `port=(1, 8)` |
| список | `port=[1, 2, (5, 8), 10]` |
| строка | `port="1-8,10,12-15"` |
| все | `port=None` |

---

## 4. Построение по типам объектов

### OLT / switch / onu / radio / customer

```python
nt.build_from_device("olt", 10)
nt.build_from_device("olt", 10, port=(1, 4), linear=True)
nt.build_from_customer(1001)
```

- `port=None` — все порты; иначе только указанные.
- На пути: сплиттер/CWDM — все порты; кросс — противоположная сторона; терминалы — стоп.

### Кросс

```python
nt.build_from_cross(cross_uuid, side=1, port="1-12")
```

### Сплиттер / CWDM

```python
nt.build_from_splitter(55, side=2, port=(1, 8))
nt.build_from_cwdm(7, side=1)
```

### Fiber

```python
nt.build_from_fiber(13259, side=2, port=1)  # port = номер ОВ
```

### Node

```python
nt.build_from_node(node_id)
```

### Параметры CGraph.build

```python
cg.build(
    object_type, object_id,
    port=None, side=None,
    included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    linear=False, linear_on_fail="raise",
)
```

---

## 5. Линейный режим

```python
cg.build("olt", 10, port=1, linear=True, linear_on_fail="raise")
cg.is_linear()
```

---

## 6. `get_linear`

```python
linear = nt.get_linear("customer", 100, "olt", 1)
linear = nt.get_linear("customer", 100, port=1)
linear = nt.get_linear(
    "node", 10, source="fngraph",
    start_node_id=10, end_node_id=20,
)
```

Ветвление (несколько simple paths) → `TopologyBuildError`.

---

## 7. Простые пути

```python
from simpleworkernet.utils.topology.paths import simple_paths, shortest_simple_path

paths = simple_paths(cg, v1, v2, cutoff=100, max_paths=50)
cg.simple_paths(v1, v2)
cg.shortest_path(v1, v2)
```

---

## 8. Методы NetworkTopology

| Метод | Назначение |
|-------|------------|
| `build_from_device` | OLT / switch / onu / radio |
| `build_from_customer` | абонент |
| `build_from_cross` | кросс |
| `build_from_splitter` / `build_from_cwdm` | сплиттер / CWDM |
| `build_from_fiber` / `build_from_cable` | кабель |
| `build_from_node` | сооружение |
| `get_linear` | линейный подграф |
| `get_customers` / `get_nodes` / … | выборки |
| `save_to_file` / `load_from_file` | сериализация |

---

## 9. DataCache и merge

```python
from simpleworkernet.utils.topology import merge_cgraphs, merge_fngraphs
cg = merge_cgraphs(cg1, cg2)
```

---

## 10. Затухания

См. [attenuation.md](attenuation.md).
