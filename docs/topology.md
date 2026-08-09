# Графовая топология

**Зависимость:** `pip install python-igraph`

Модуль: `simpleworkernet.utils.topology`.

```python
from simpleworkernet.utils.topology import (
    NetworkTopology, Topology,  # Topology — alias NetworkTopology
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
| **CGraph** | Интерфейсы объектов `(type, id, side, port)` | Коммутации (external / internal) |
| **FNGraph** | Сооружения связи (`node_id`) | Кабели/участки между узлами |

- **CGraph** — детальная коммутация (для затуханий, линейных трасс).
- **FNGraph** — коридор сооружений (фильтры `included_fibers` / `excluded_fibers`).

`NetworkTopology` хранит список CGraph и опционально один FNGraph.

---

## 2. Быстрый старт

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import NetworkTopology, DataCache

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()  # можно шарить между NetworkTopology
nt = NetworkTopology(client, cache=cache)

# построение от OLT, порты 1–8
nt.build_from_device("olt", 10, port="1-8")
# или напрямую
cg = CGraph(client, cache=cache)
cg.build("olt", 10, port=(1, 8))
```

---

## 3. Параметр `port` (единый)

Во всех `build` / `build_from_*` / `get_linear` — **один** параметр `port`:

| Формат | Пример | Результат |
|--------|--------|-----------|
| число | `port=5` | `{5}` |
| кортеж-диапазон | `port=(1, 8)` | `{1..8}` |
| список смешанный | `port=[1, 2, (5, 8), 10]` | `{1,2,5,6,7,8,10}` |
| список из одного | `port=[5]` | `{5}` |
| строка | `port="1-8,10,12-15"` | `{1..8,10,12..15}` |
| `None` | `port=None` | все порты |

```python
cg.build("olt", 1, port="1-8,16")
cg.build("cross", uuid, side=1, port=[1, 2, (10, 12)])
cg.build("splitter", 55, side=2, port=(1, 8), linear=True)
```

---

## 4. Построение CGraph: правила по типам объектов

### 4.1. Общие параметры `CGraph.build` / `GraphBuilder.build`

```python
cg.build(
    object_type,      # "olt" | "cross" | "splitter" | "fiber" | ...
    object_id,
    port=None,        # см. §3
    side=None,        # 1|2 для cross/splitter/fiber
    included_fibers=None,
    excluded_fibers=None,
    excluded_nodes=None,
    linear=False,           # требовать линейность на сплиттерах/CWDM
    linear_on_fail="raise", # "raise" | "continue"
)
```

Фильтры (`included_fibers` / `excluded_fibers` / `excluded_nodes`) работают как раньше.

### 4.2. От OLT / switch / onu / radio / customer (терминалы и актив)

| Параметр | Поведение |
|----------|-----------|
| `side` | не используется (у устройств сторона условно 1) |
| `port=None` | старт со **всех** портов объекта |
| `port=...` | только указанные порты |

На пути:

- **сплиттер / CWDM** — в граф попадают все входы и выходы, обход по всем;
- **кросс** — проход только по порту прихода на **противоположную** сторону;
- конечные объекты: абонент, OLT, switch, radio, ONU и любой объект без продолжения коммутации → `terminate_vertex`.

```python
nt.build_from_device("olt", 10)                    # все порты
nt.build_from_device("olt", 10, port=(1, 4))       # 1..4
nt.build_from_device("switch", 3, port=[1, 2, 8])
nt.build_from_customer(1001)
```

### 4.3. От кросса

| Параметр | Поведение |
|----------|-----------|
| `side=1` или `2` | старт с этой стороны, движение на **противоположную** |
| `side=None` | обе стороны |
| `port=...` | только эти порты; без `port` — все порты стороны |

```python
nt.build_from_cross(cross_uuid, side=1, port="1-12")
nt.build_from_cross(cross_uuid)  # обе стороны, все порты
```

### 4.4. От сплиттера / CWDM

| Параметр | Поведение |
|----------|-----------|
| `side` | если задана — старт с этой стороны, дальше в противоположную |
| `side=None` | обе стороны |
| `port=None` | все порты стороны |
| `port=...` | только указанные |

```python
nt.build_from_splitter(55, side=2, port=(1, 8))
nt.build_from_cwdm(7, side=1)
```

### 4.5. От кабеля (fiber)

| Параметр | Поведение |
|----------|-----------|
| `side` | сторона кабеля (1 → `node1_id`, 2 → `node2_id`) |
| `port` | **номер ОВ** (`clps_mid`); желательно указывать |

```python
nt.build_from_fiber(13259, side=2, port=1)
```

### 4.6. От сооружения связи (node)

Строим по **всем коммутациям** в этом узле.

```python
nt.build_from_node(node_id)
```

---

## 5. Линейный режим (`linear=True`)

Линейный CGraph — без ветвлений (степени вершин ≤ 2, связный).

- На **сплиттере** допустим приход только на OUT (side=2) при движении «от OLT».
- На **CWDM** — приход на IN.
- Если ветвление неизбежно:
  - `linear_on_fail="raise"` → `TopologyBuildError` / исключение;
  - `linear_on_fail="continue"` → строить дальше, флаг нарушения.

Проверка:

```python
cg.is_linear()  # True / False
```

```python
cg.build("olt", 10, port=1, linear=True, linear_on_fail="raise")
```

---

## 6. `get_linear` — линейный подграф из уже построенного

Заменяет устаревший `topology_from_commutation`.

### 6.1. Из CGraph

```python
# start + end: единственный simple path, иначе TopologyBuildError
linear = nt.get_linear("customer", 100, "olt", 1)

# только start (например абонент): однозначный обход до терминала/тупика
linear = nt.get_linear("customer", 100, port=1)

# с портом/стороной
linear = nt.get_linear("fiber", 13259, "fiber", 13235, port=1, side=2)
```

Правила:

- несколько путей между start и end → **исключение** (ветвление);
- только start: на каждом шаге ровно один «вперёд»-сосед; иначе исключение;
- результат — новый `NetworkTopology` с одним линейным CGraph (и FNGraph, если удалось).

### 6.2. Из FNGraph

```python
linear = nt.get_linear(
    "node", start_node_id,
    source="fngraph",
    start_node_id=10,
    end_node_id=20,
)
# end_node_id=None — только если в FNGraph ровно один «лист»
```

### 6.3. Устаревший API

```python
# работает, но предпочтителен get_linear
nt.topology_from_commutation("customer", 100, first_object_type="olt", first_object_id=1)
```

---

## 7. Поиск простых путей

Модуль `simpleworkernet.utils.topology.paths`:

```python
from simpleworkernet.utils.topology.paths import (
    simple_paths, shortest_simple_path, has_unique_simple_path,
)

paths = simple_paths(cg, v1, v2, cutoff=100, max_paths=50)
one = shortest_simple_path(cg, v1, v2)

# методы на CGraph
cg.simple_paths(v1, v2)
cg.shortest_path(v1, v2)
```

Алгоритм: **итеративный DFS** (без рекурсии), путь без повторов вершин.

- `cutoff` — макс. число рёбер;
- `max_paths` — ранний выход после N путей.

---

## 8. Методы NetworkTopology

| Метод | Назначение |
|-------|------------|
| `build_from_device(type, id, port=...)` | OLT / switch / onu / radio |
| `build_from_customer(id)` | абонент |
| `build_from_cross(id, side=..., port=...)` | кросс |
| `build_from_splitter(id, side=..., port=...)` | сплиттер |
| `build_from_cwdm(id, side=..., port=...)` | CWDM |
| `build_from_fiber(id, side=..., port=...)` | кабель |
| `build_from_node(id)` | сооружение |
| `build_from_cable(id)` | кабель (alias) |
| `get_linear(...)` | линейный подграф |
| `get_customers()` | абоненты в топологии |
| `save_to_file` / `load_from_file` | сериализация |

---

## 9. DataCache

Экземплярный кэш инвентаря, длин волокон, geo. Один `DataCache` можно передать нескольким `NetworkTopology` / `CGraph`.

Не путать с глобальным `simpleworkernet.cache` (схемы SmartData).

---

## 10. Слияние графов

```python
from simpleworkernet.utils.topology import merge_cgraphs, merge_fngraphs

cg = merge_cgraphs(cg1, cg2)
fg = merge_fngraphs(fg1, fg2)
```

---

## 11. Связь с затуханиями

```python
from simpleworkernet.utils.topology import Attenuation, load_attenuation_catalog

cat = load_attenuation_catalog(client)
att = Attenuation(nt.cgraphs[0], catalog=cat, client=client, cache=cache)
r = att.calculate("olt", 10, "customer", 100, wavelength=1490)
```

Либо без готового CGraph — `Attenuation` построит его сам (см. [attenuation.md](attenuation.md)).
