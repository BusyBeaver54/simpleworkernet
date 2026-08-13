# Структура пакета

Полное дерево исходников `src/simpleworkernet/`.

```text
src/
└── simpleworkernet/
    ├── __init__.py
    ├── __main__.py
    ├── __version__.py
    ├── cli.py
    ├── py.typed
    │
    ├── core/
    │   ├── __init__.py
    │   ├── cache.py              # SmartDataCache (LFU/LRU/FIFO)
    │   ├── client.py             # WorkerNetClient
    │   ├── config.py             # config_manager, defaults
    │   ├── constants.py
    │   ├── exceptions.py
    │   ├── logger.py
    │   └── typing.py             # ApiRetSData, ApiRetBool
    │
    ├── models/
    │   ├── __init__.py
    │   ├── base.py               # BaseModel, BaseCategory, smart_model
    │   ├── operators.py          # Operator, Where
    │   ├── primitives.py         # vStr, vFlag, GeoPoint, …
    │   └── categories/
    │       ├── __init__.py
    │       ├── additional_data.py
    │       ├── address.py
    │       ├── advertising.py
    │       ├── attach.py
    │       ├── billing.py
    │       ├── cable_route.py
    │       ├── call.py
    │       ├── commutation.py
    │       ├── cross.py
    │       ├── customer.py
    │       ├── cwdm.py
    │       ├── device.py         # Device.Get_data, ifaces.ifName
    │       ├── employee.py
    │       ├── fiber.py          # Fiber.Get_list, fibers.color
    │       ├── gps.py
    │       ├── inventory.py
    │       ├── key.py
    │       ├── map.py
    │       ├── module.py
    │       ├── node.py
    │       ├── notepad.py
    │       ├── owner.py
    │       ├── service.py
    │       ├── setting.py
    │       ├── sms.py
    │       ├── splitter.py
    │       ├── system.py
    │       ├── tariff.py
    │       ├── task.py
    │       ├── trassa.py
    │       ├── vehicle.py
    │       └── vlan.py
    │
    ├── smartdata/
    │   ├── __init__.py
    │   ├── core.py
    │   ├── helpers.py
    │   ├── metadata.py
    │   └── processor.py          # SmartData processor
    │
    ├── scripts/
    │   ├── __init__.py
    │   └── uninstall.py          # cleanup-simpleworkernet
    │
    └── utils/
        ├── __init__.py
        ├── app_name.py
        ├── constants.py          # TYPE_*, DEVICE_TYPES, …
        ├── decorators.py         # @api_method
        ├── graphics.py           # SVGHandler, PNG backends
        │
        └── topology/
            ├── __init__.py                 # публичный API топологии
            ├── topology.py                 # NetworkTopology + build_from_*
            ├── cache.py                    # DataCache (device dual-index, object_type=all)
            ├── constants.py                # реэкспорт TYPE_*
            ├── context.py                  # BuildContext
            ├── errors.py                   # TopologyBuildError
            ├── keys.py                     # ObjKey, Interface
            ├── models.py                   # CGraphVertex, FNGraphVertex, …
            ├── ports_spec.py               # expand_ports
            ├── paths.py                    # simple / shortest paths
            ├── linear.py                   # LinearPathFinder + extract_linear_*
            ├── merge.py                    # merge_cgraphs, merge_fngraphs
            │
            ├── builders/
            │   ├── __init__.py
            │   ├── base.py                 # GraphBuilder (BFS)
            │   └── handlers.py             # terminal / fiber / cross / splitter+cwdm
            │
            ├── graphs/
            │   ├── __init__.py             # CGraph.build binding
            │   ├── base.py                 # BaseGraph (igraph wrapper)
            │   ├── cgraph.py               # CGraph — граф коммутаций (+ is_linear)
            │   └── fngraph.py              # FNGraph — граф сооружений
            │
            └── attenuation/                # оптические затухания
                ├── __init__.py
                ├── calculator.py           # Attenuation.calculate
                ├── calculator_core.py      # mixins: path, edge, fiber, graph, …
                ├── calculator_pairs.py     # PairPlan, validate
                ├── catalog.py              # AttenuationCatalog (+ helpers)
                ├── catalog_helpers.py      # ratio keys, db triples (legacy helper)
                ├── defaults.json           # package defaults (ratio_defaults)
                ├── errors.py               # AttenuationError
                ├── length.py               # opticalen / geo length
                ├── models.py               # EndpointInfo, AttenuationSegment, PathReport
                ├── multipath.py            # MultiPathReport
                ├── report_io.py            # save/load PathReport
                ├── splitter_load.py        # загрузка сплиттеров для отчёта
                └── template.py             # generate/update/load JSON (+ fetch)
```

## Назначение основных модулей

| Путь | Роль |
|------|------|
| `core/client.py` | HTTP-клиент WorkerNet API, сессии, ретраи |
| `core/config.py` | Конфигурация, таймауты, preload |
| `core/cache.py` | Кэш полей SmartData |
| `models/base.py` | Рекурсивный кастинг JSON → модели |
| `models/categories/*` | API-категории (Device, Fiber, Customer, …) |
| `smartdata/` | Fluent-фильтры, метаданные пути |
| `utils/graphics.py` | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |
| `utils/topology/topology.py` | Оркестратор: CGraph + FNGraph, `build_from_*` |
| `utils/topology/graphs/cgraph.py` | Граф коммутаций (интерфейсы), `is_linear` |
| `utils/topology/graphs/fngraph.py` | Граф сооружений (node + fiber) |
| `utils/topology/builders/` | BFS GraphBuilder и handlers объектов |
| `utils/topology/cache.py` | DataCache объектов/коммутаций |
| `utils/topology/linear.py` | Линейные пути и extract_linear_* |
| `utils/topology/attenuation/` | Расчёт затуханий, каталог, PathReport |

## Публичный API

| Импорт | Содержимое |
|--------|------------|
| `simpleworkernet` | `WorkerNetClient`, модели, `Where`, `Operator`, SmartData, … |
| `simpleworkernet.utils.topology` | `NetworkTopology`, `CGraph`, `FNGraph`, `DataCache`, `Attenuation`, `PathReport`, `MultiPathReport`, типы |
| `simpleworkernet.utils.topology.attenuation` | полный API затуханий: каталог, шаблоны, отчёты, `PairPlan`, `EndpointInfo` |
| `simpleworkernet.utils.constants` | `TYPE_*`, `TERMINAL_TYPES`, `ALL_OBJECT_TYPES` |

```python
from simpleworkernet.utils.topology import (
    NetworkTopology, CGraph, FNGraph, DataCache,
    Attenuation, PathReport, MultiPathReport,
    TYPE_OLT, TYPE_CUSTOMER, TYPE_FIBER,
)
```

Подробнее:

- [topology.md](topology.md) — построение графов, `port`, `get_linear`
- [attenuation.md](attenuation.md) — каталог JSON, `calculate`, PathReport
- [graphics.md](graphics.md) — SVG / PNG
