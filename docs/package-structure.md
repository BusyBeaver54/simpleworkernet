# Структура пакета

```text
src/simpleworkernet/
├── __init__.py                 # публичный API, предзагрузка кэша моделей
├── __main__.py                 # python -m simpleworkernet
├── __version__.py
├── cli.py                      # точка входа cleanup-simpleworkernet
├── py.typed
│
├── core/
│   ├── client.py               # WorkerNetClient (сессии, GET/POST, ретраи)
│   ├── config.py               # ConfigManager + пути XDG/AppData
│   ├── cache.py                # SmartDataCache (LFU/LRU/FIFO)
│   ├── logger.py               # фасад над stdlib logging
│   ├── constants.py            # уровни DEBUG/INFO/WARNING/ERROR/CRITICAL
│   ├── exceptions.py
│   └── typing.py
│
├── models/
│   ├── base.py                 # BaseModel, BaseCategory, smart_model, CollapsedField
│   ├── primitives.py           # GeoPoint, vStr, vMoney, vINN, …
│   ├── operators.py            # Operator, Where
│   └── categories/             # API-категории (Node, Customer, Fiber, …)
│       ├── __init__.py
│       ├── additional_data.py, address.py, advertising.py, attach.py
│       ├── billing.py, cable_route.py, call.py, commutation.py
│       ├── cross.py, customer.py, cwdm.py, device.py, employee.py
│       ├── fiber.py, gps.py, inventory.py, key.py, map.py, module.py
│       ├── node.py, notepad.py, owner.py, service.py, setting.py
│       ├── sms.py, splitter.py, system.py, tariff.py, task.py
│       ├── trader.py, vehicle.py, vlan.py
│
├── smartdata/
│   ├── core.py                 # SmartData, коллекции
│   ├── helpers.py
│   ├── metadata.py             # метаданные пути ответа API
│   └── processor.py            # кастинг JSON → модели
│
├── scripts/
│   └── uninstall.py            # очистка данных пользователя
│
└── utils/
    ├── app_name.py
    ├── constants.py            # TYPE_*, TERMINAL_TYPES, ALL_OBJECT_TYPES
    ├── decorators.py
    ├── graphics.py             # SVG → PNG
    └── topology/               # графовая топология + затухания
        ├── __init__.py         # NetworkTopology, CGraph, FNGraph, Attenuation, …
        ├── constants.py        # типы объектов топологии
        ├── keys.py             # ObjKey, Interface
        ├── models.py           # CGraphVertex/Edge, FNGraphVertex/Edge
        ├── errors.py           # TopologyBuildError
        ├── cache.py            # DataCache
        ├── context.py
        ├── ports_spec.py       # разбор port= int|str|list|tuple
        ├── linear.py
        ├── linear_extract.py   # вырезание линейного подграфа
        ├── merge.py            # merge_cgraphs, merge_fngraphs
        ├── paths.py            # simple_paths / shortest path
        ├── topology.py         # NetworkTopology
        ├── topology_build_methods.py   # build_from_* mixin
        ├── topology_build_params.py
        ├── topology_get_linear.py
        ├── builders/
        │   ├── base.py, handlers.py, handlers_splitter.py, handlers_util.py
        ├── graphs/
        │   ├── base.py, cgraph.py, cgraph_extra.py, fngraph.py
        └── attenuation/        # расчёт оптических затуханий
            ├── calculator.py           # Attenuation.calculate
            ├── calculator_build.py     # on-demand CGraph
            ├── calculator_edge.py      # сегменты по рёбрам
            ├── calculator_fiber.py, calculator_fn.py
            ├── calculator_pairs.py     # PairPlan, validate
            ├── calculator_path.py      # PathReport из vertex-path
            ├── calculator_paths.py     # find_paths / simple_paths
            ├── calculator_segments.py  # attrs, length, labels
            ├── catalog.py              # AttenuationCatalog
            ├── catalog_core.py         # defaults, fiber/cable triples
            ├── catalog_fill.py, catalog_force.py, catalog_helpers.py
            ├── catalog_io.py, catalog_merge.py
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

## Публичный API

| Импорт | Содержимое |
|--------|------------|
| `simpleworkernet` | `WorkerNetClient`, модели, `Where`, `Operator`, SmartData, … |
| `simpleworkernet.utils.topology` | `NetworkTopology`, `CGraph`, `FNGraph`, `DataCache`, `Attenuation`, `PathReport`, `MultiPathReport`, типы |
| `simpleworkernet.utils.topology.attenuation` | полный API затуханий: каталог, шаблоны, отчёты, `PairPlan`, `EndpointInfo` |
| `simpleworkernet.utils.constants` | `TYPE_*`, `TERMINAL_TYPES`, `ALL_OBJECT_TYPES` |

Устаревшее имя **`Topology`** удалено — используйте **`NetworkTopology`**.

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
