# Структура пакета

```text
src/simpleworkernet/
├── __init__.py
├── __main__.py / cli.py
├── core/                   # client, config, cache, logger, exceptions
├── models/                 # BaseModel, categories, primitives, operators
├── smartdata/              # SmartData processor
├── scripts/
└── utils/
    ├── decorators.py, app_name.py, constants.py, graphics.py
    └── topology/
        ├── __init__.py             # публичный API
        ├── topology.py             # NetworkTopology
        ├── topology_build_methods.py / topology_build_params.py
        ├── cache.py                # DataCache
        ├── constants.py, keys.py, models.py, errors.py, context.py
        ├── ports_spec.py, paths.py, linear.py, linear_extract.py, merge.py
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
