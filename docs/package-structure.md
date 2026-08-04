# Структура пакета

```text
src/simpleworkernet/
├── __init__.py              # публичный API, предзагрузка кэша моделей
├── __main__.py
├── __version__.py
├── cli.py                   # точка входа cleanup-simpleworkernet
├── core/
│   ├── client.py            # WorkerNetClient (сессии, GET/POST, ретраи)
│   ├── config.py            # ConfigManager + пути XDG/AppData
│   ├── cache.py             # SmartDataCache (LFU/LRU/FIFO)
│   ├── logger.py            # фасад над stdlib logging
│   ├── constants.py         # DEBUG/INFO/WARNING/ERROR/CRITICAL
│   ├── exceptions.py
│   └── typing.py
├── models/
│   ├── base.py              # BaseModel, BaseCategory, smart_model, CollapsedField
│   ├── primitives.py        # GeoPoint, vStr, vMoney, vINN, …
│   ├── operators.py         # Operator, Where
│   └── categories/          # API-категории WorkerNet
│       ├── customer.py, device.py, fiber.py, node.py, …
│       └── (≈30 модулей)
├── smartdata/
│   ├── core.py              # SmartData — fluent filters/aggregates
│   ├── helpers.py
│   ├── metadata.py          # PathSegment, MetaData
│   └── processor.py         # кастинг JSON → модели
├── utils/
│   ├── app_name.py          # get_app_name (хеш процесса)
│   ├── decorators.py        # api_method, timer, retry, …
│   ├── graphics.py          # SVG/PNG
│   └── topology/
│       ├── topology.py      # фасад Topology
│       ├── cache.py         # DataCache (инстанс, не синглтон)
│       ├── constants.py     # TYPE_OLT, TYPE_FIBER, …
│       ├── keys.py          # ObjKey, Interface
│       ├── models.py        # CGraphVertex/Edge, FNGraphVertex/Edge
│       ├── context.py       # BuildContext
│       ├── linear.py        # LinearPathFinder
│       ├── merge.py         # merge_cgraphs / merge_fngraphs
│       ├── graphs/
│       │   ├── cgraph.py    # CGraph (интерфейсы + коммутации)
│       │   └── fngraph.py   # FNGraph (узлы + fiber_id)
│       ├── builders/
│       │   ├── base.py      # GraphBuilder
│       │   └── handlers.py  # Fiber/Splitter/Cross/… handlers
│       └── attenuation/
│           ├── calculator.py
│           ├── catalog.py
│           ├── models.py    # AttenuationSegment, PathReport
│           ├── length.py    # resolve_fiber_length_m
│           ├── template.py  # generate_template из live API
│           └── defaults.json
└── scripts/
    └── uninstall.py         # cleanup логики (OS-aware)
```

## Публичный импорт

```python
from simpleworkernet import (
    WorkerNetClient,
    SmartData, Where, Operator,
    BaseModel, smart_model, CollapsedField,
    vStr, GeoPoint, GeoPointArray, vMoney,
    config_manager, log, cache,
    Topology, CGraph, FNGraph,
    cleanup,
    save_svg, load_svg, svg_to_png,
)
from simpleworkernet.utils.topology import (
    Attenuation, AttenuationCatalog, PathReport, DataCache,
)
```
