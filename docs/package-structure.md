# Структура пакета

Полное дерево исходников `src/simpleworkernet/` (и `src/assets/`).

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
            ├── topology.py                 # NetworkTopology
            ├── topology_build_methods.py   # build_from_*
            ├── topology_build_params.py
            ├── topology_get_linear.py
            ├── cache.py                    # DataCache
            ├── constants.py                # реэкспорт TYPE_*
            ├── context.py                  # BuildContext
            ├── errors.py                   # TopologyBuildError
            ├── keys.py                     # ObjKey, Interface
            ├── models.py                   # CGraphVertex, FNGraphVertex, …
            ├── ports_spec.py               # expand_ports
            ├── paths.py                    # simple paths
            ├── linear.py                   # LinearPathFinder
            ├── linear_extract.py           # extract_linear_cgraph / fngraph
            ├── merge.py                    # merge_cgraphs, merge_fngraphs
            │
            ├── builders/
            │   ├── __init__.py
            │   ├── base.py                 # GraphBuilder (BFS)
            │   ├── handlers.py
            │   ├── handlers_splitter.py
            │   └── handlers_util.py
            │
            ├── graphs/
            │   ├── __init__.py
            │   ├── base.py                 # BaseGraph (igraph wrapper)
            │   ├── cgraph.py               # CGraph — граф коммутаций
            │   ├── cgraph_extra.py
            │   └── fngraph.py              # FNGraph — граф сооружений
            │
            └── attenuation/                # оптические затухания
                ├── __init__.py
                ├── calculator.py           # Attenuation.calculate
                ├── calculator_build.py     # on-demand CGraph
                ├── calculator_edge.py      # сегменты по рёбрам
                ├── calculator_fiber.py
                ├── calculator_fn.py
                ├── calculator_pairs.py     # PairPlan, validate
                ├── calculator_path.py      # PathReport, port_name, fiber meta
                ├── calculator_paths.py     # find_paths / simple_paths
                ├── calculator_segments.py  # attrs, length, labels
                ├── catalog.py              # AttenuationCatalog
                ├── catalog_core.py         # defaults, fiber/cable triples
                ├── catalog_fill.py
                ├── catalog_force.py
                ├── catalog_helpers.py
                ├── catalog_io.py
                ├── catalog_merge.py
                ├── catalog_resolve.py      # splitter_port_db / _triple
                ├── catalog_splitters.py
                ├── defaults.json           # package defaults (ratio_defaults)
                ├── errors.py               # AttenuationError
                ├── length.py               # opticalen / geo length
                ├── models.py               # EndpointInfo, AttenuationSegment, PathReport
                ├── multipath.py            # MultiPathReport
                ├── report_io.py            # save/load PathReport
                ├── template.py             # generate/update/load JSON
                └── template_fetch.py
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
| `utils/topology/topology.py` | Оркестратор: CGraph + FNGraph |
| `utils/topology/graphs/cgraph.py` | Граф коммутаций (интерфейсы) |
| `utils/topology/graphs/fngraph.py` | Граф сооружений (node + fiber) |
| `utils/topology/cache.py` | DataCache объектов/коммутаций |
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
