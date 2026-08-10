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

Оркестратор — **`NetworkTopology`** (устаревшее имя `Topology` **удалено**).

---

## 1. Типы графов

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | Интерфейсы `(obj_type, obj_id, side, port)` | Коммутации (в т.ч. внутренние на кроссе/сплиттере) |
| **FNGraph** | Сооружения (`node_id`) | Кабели между узлами |

`NetworkTopology` хранит:

- `cgraphs: List[CGraph]` — одна или несколько связных компонент коммутации;
- `fngraph: Optional[FNGraph]` — обобщённый граф сооружений;
- `client`, `cache: DataCache`.

Несвязный CGraph **не** добавляется в список (проверка `is_connected()`).

Константы типов — в `simpleworkernet.utils.constants` и реэкспорт из `topology`.

### Ключи и интерфейсы

```python
from simpleworkernet.utils.topology import ObjKey, Interface

key = ObjKey("olt", 11808)
iface = Interface("fiber", 13259, side=2, port=1)
```

Вершина CGraph: атрибуты `obj_type`, `obj_id`, `side`, `port`, часто `api_obj`.

---

## 2. Быстрый старт

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import NetworkTopology, DataCache

client = WorkerNetClient(...)
cache = DataCache()
nt = NetworkTopology(client, cache=cache)

# от OLT, порты 1–8
nt.build_from_device("olt", 11808, port="1-8")

# от абонента вверх до OLT
nt.build_from_customer(17711)

print(len(nt.cgraphs), nt.cgraphs[0].vcount(), nt.cgraphs[0].ecount())
print(nt.get_customers(), nt.get_splitters(), nt.get_fibers())
```

---

## 3. Параметр `port`

Один аргумент `port` принимает разные форматы (модуль `ports_spec`):

| Формат | Пример | Результат |
|--------|--------|-----------|
| число | `port=5` | `{5}` |
| диапазон (tuple) | `port=(1, 8)` | `{1…8}` |
| список | `port=[1, 2, (5, 8), 10]` | `{1,2,5,6,7,8,10}` |
| строка | `port="1-8,10,12-15"` | диапазоны и одиночные |
| все порты | `port=None` | без ограничения |

```python
nt.build_from_device("olt", 10, port=5)
nt.build_from_device("olt", 10, port=(1, 4))
nt.build_from_device("olt", 10, port=[1, 2, (5, 8)])
nt.build_from_device("olt", 10, port="1-8,11")
nt.build_from_cross(uuid, port="1-12", side=1)
```

---

## 4. Построение по типам объектов

Общая идея: BFS по коммутациям от стартового интерфейса (`builders/`).

| Встреченный объект | Поведение |
|--------------------|-----------|
| **Сплиттер** | раскрываются все входы/выходы (стороны), обход по всем портам |
| **CWDM** | аналогично, с учётом направления (вход/выход) |
| **Кросс** | только переход на **противоположную** сторону того же порта |
| **OLT / switch / onu / radio / customer** | терминал — обход останавливается |
| **Fiber** | ребро вдоль кабеля (side1 ↔ side2) |

Фильтры (где поддерживаются):

- `included_fibers` — только эти id кабелей;
- `excluded_fibers` — не заходить в эти кабели;
- `excluded_nodes` — не заходить в сооружения.

### 4.1. OLT / switch / onu / radio

```python
nt.build_from_device("olt", 11808)
nt.build_from_device("olt", 11808, port=11)
nt.build_from_device("olt", 11808, port="1-8", linear=True)
nt.build_from_device("switch", 50, port=(1, 4))
```

- `port=None` — все порты устройства (несколько стартов → merge).
- `linear=True` — пытаться строить только линейные ветви (см. §5).

### 4.2. Абонент

```python
nt.build_from_customer(17711)
```

Сторона/порт не нужны: обход от интерфейса абонента до терминалов (OLT и т.д.).

### 4.3. Кросс

```python
nt.build_from_cross(cross_uuid, side=1, port="1-12")
nt.build_from_cross(cross_uuid)  # все порты / обе стороны по коммутациям
```

### 4.4. Сплиттер / CWDM

```python
nt.build_from_splitter(16926, side=2, port=(1, 8))
nt.build_from_splitter(16926)
nt.build_from_cwdm(7, side=1, port=2)
```

### 4.5. Кабель (fiber)

```python
nt.build_from_fiber(13259, side=2, port=1)  # port = номер ОВ
```

Для однозначного линейного графа **нужен номер ОВ** (`port`).  
`side` — сторона сооружения (node1 / node2).

### 4.6. Сооружение (node) / кабель

```python
nt.build_from_node(node_id)
nt.build_from_cable(cable_id)
```

### 4.7. Низкоуровневый CGraph.build

```python
from simpleworkernet.utils.topology import CGraph, DataCache

cg = CGraph(client, cache=DataCache())
cg.build(
    object_type, object_id,
    port=None, side=None,
    included_fibers=None,
    excluded_fibers=None,
    excluded_nodes=None,
)
print(cg.vcount(), cg.ecount(), cg.is_connected())
```

---

## 5. Линейный режим

Линейный CGraph — без ветвлений (нет «лишних» выходов сплиттера/CWDM на пути).

```python
nt.build_from_device("olt", 10, port=1, linear=True, linear_on_fail="raise")
# linear_on_fail: "raise" | "continue"

cg = nt.cgraphs[0]
if hasattr(cg, "is_linear"):
    print(cg.is_linear())
```

---

## 6. `get_linear` — вырезать линейный подграф

Из **уже построенной** топологии:

```python
linear = nt.get_linear("customer", 17711, "olt", 11808)
linear = nt.get_linear("customer", 17711)  # если путь однозначен

linear = nt.get_linear(
    "node", 10,
    source="fngraph",
    start_node_id=10,
    end_node_id=20,
)
```

| Параметр | Смысл |
|----------|--------|
| `start_type`, `start_id` | начало |
| `end_type`, `end_id` | конец (необязателен, если путь однозначен) |
| `port`, `side` | уточнение интерфейса |
| `source` | `"cgraph"` (по умолчанию) или `"fngraph"` |
| `cgraph_index` | какой CGraph из списка |

Если между концами несколько simple paths (ветвление) → `TopologyBuildError`.

---

## 7. Простые пути

```python
from simpleworkernet.utils.topology.paths import simple_paths, shortest_simple_path

cg = nt.cgraphs[0]
paths = simple_paths(cg, v_from, v_to, cutoff=100, max_paths=50)
shortest = shortest_simple_path(cg, v_from, v_to)
```

Алгоритм — итеративный DFS без повторов вершин, с `cutoff` и `max_paths`.

---

## 8. Методы NetworkTopology

| Метод | Назначение |
|-------|------------|
| `build_from_device` | OLT / switch / onu / radio |
| `build_from_customer` | абонент |
| `build_from_cross` | кросс (uuid) |
| `build_from_splitter` / `build_from_cwdm` | сплиттер / CWDM |
| `build_from_fiber` / `build_from_cable` | кабель |
| `build_from_node` | сооружение |
| `get_linear` | линейный подграф |
| `get_customers` / `get_nodes` / `get_fibers` / `get_cables` | id объектов в графах |
| `get_devices` / `get_splitters` / `get_cwdms` / `get_crosses` | выборки |
| `get_finish_by_node` / `get_finish_by_object` | finish-данные |
| `customer` / `node` / `fiber` / … | доступ к закэшированным моделям |
| `save_to_file` / `load_from_file` | сериализация топологии |

---

## 9. DataCache и merge

```python
from simpleworkernet.utils.topology import DataCache, merge_cgraphs, merge_fngraphs

cache = DataCache()
cg = merge_cgraphs([cg1, cg2], client, cache)
fn = merge_fngraphs([fn1, fn2], client, cache)
```

`DataCache` общий для topology и attenuation — меньше запросов к API.

---

## 10. Примеры сценариев

### От OLT вниз по дереву PON

```python
nt = NetworkTopology(client)
nt.build_from_device("olt", 11808, port="1-16")
print("абоненты:", nt.get_customers())
print("сплиттеры:", nt.get_splitters())
```

### От абонента до OLT + затухание

```python
nt = NetworkTopology(client)
nt.build_from_customer(17711)

from simpleworkernet.utils.topology import Attenuation
att = Attenuation(topology=nt, wavelength=1490)
res = att.calculate()  # все cgraph топологии
res = att.calculate("customer", 17711, "olt", 11808, wavelength=1490)
print(res.to_table())
print(res.total_db, res.total_db_min, res.total_db_max)
```

### Линейный участок fiber ↔ fiber

```python
nt = NetworkTopology(client)
nt.build_from_fiber(13259, side=2, port=1)

linear = nt.get_linear("fiber", 13259, "fiber", 13235, port=1)
att = Attenuation(topology=linear, wavelength=1490)
res = att.calculate(
    "fiber", 13259, "fiber", 13235,
    obj1_side=2, obj1_port=1, obj2_side=2, obj2_port=1,
)
```

### Несколько портов OLT → несколько CGraph

```python
nt = NetworkTopology(client)
nt.build_from_device("olt", 10, port=[1, 2, 3, (8, 12)])
for i, cg in enumerate(nt.cgraphs):
    print(i, cg.vcount(), cg.ecount())

att = Attenuation(topology=nt, wavelength=1550)
multi = att.calculate()  # ветви по всем компонентам
```

### Сохранение / загрузка

```python
nt.save_to_file("/tmp/topo.json")
nt2 = NetworkTopology.load_from_file("/tmp/topo.json")
```

---

## 11. Затухания

Подробно: [attenuation.md](attenuation.md).

```python
att = Attenuation(topology=nt, wavelength=1490)
# также: Attenuation(cgraph=cg) или Attenuation(cgraph=[cg1, cg2])
res = att.calculate()
res = att.calculate("customer", 17711)
res = att.calculate("customer", 17711, "olt", 11808, obj2_port=11)
print(res.to_table())  # sNpM, host, name, port_name
```

---

## 12. Структура подмодулей

| Путь | Назначение |
|------|------------|
| `topology.py` | `NetworkTopology` |
| `topology_build_methods.py` | `build_from_*` |
| `ports_spec.py` | разбор `port=` |
| `linear.py` / `linear_extract.py` | линейный режим и вырезание |
| `graphs/cgraph.py`, `fngraph.py` | CGraph, FNGraph |
| `builders/` | BFS-обработчики объектов |
| `cache.py` | `DataCache` |
| `merge.py` | `merge_cgraphs` / `merge_fngraphs` |
| `paths.py` | `simple_paths`, shortest path |
| `attenuation/` | расчёт оптических затуханий |

Полное дерево: [package-structure.md](package-structure.md).

---

## 13. Ошибки

| Исключение | Когда |
|------------|--------|
| `TopologyBuildError` | не удалось построить/вырезать линейный граф, неоднозначное ветвление в `get_linear` |
| пустой `cgraphs` | нет коммутаций / фильтры отрезали всё / граф несвязный (не добавляется) |
