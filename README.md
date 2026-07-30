# **SimpleWorkerNet**

Python-клиент для REST API [WorkerNet](https://workernet.ru) с типизацией ответов, SmartData и графовой топологией сети.

[![Tag](https://img.shields.io/github/v/tag/busy4beaver/simpleworkernet?color=00c2e8)](https://pypi.org/project/simpleworkernet/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/simpleworkernet.svg?logo=python&logoColor=FFE873)](https://www.python.org/downloads/)
[![Licence](https://img.shields.io/github/license/busy4beaver/simpleworkernet.svg)](LICENSE)

---

## Содержание

- [Особенности](#особенности)
- [Структура пакета](#структура-пакета)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Основные компоненты](#основные-компоненты)
- [Логирование](#логирование)
- [Кэширование](#кэширование)
- [Каталоги данных](#каталоги-данных)
- [Очистка данных](#очистка-данных)
- [Графика](#графика)
- [Координаты](#координаты)
- [Графовая топология](#графовая-топология)
- [Оптические затухания (Attenuation)](#оптические-затухания-attenuation)
- [Тесты](#тесты)
- [Поддержать проект](#-поддержать-проект)

---

## Особенности

| Область | Что даёт |
|---------|----------|
| **SmartData** | Автокастинг JSON → объекты, метаданные пути, fluent-фильтры |
| **BaseModel** | Рекурсивный кастинг Union / Optional / List / вложенных моделей |
| **WorkerNetClient** | Сессии, авто-GET/POST при длинном URL, ретраи |
| **Логирование** | Раздельные уровни console / file, сессионные логи, ротация |
| **Кэш полей** | LFU / LRU / FIFO, dirty-flag, предзагрузка из моделей |
| **Топология** | CGraph + FNGraph, фильтры, линейные цепочки, save/load |
| **Attenuation** | Расчёт оптических затуханий по CGraph (fiber / splitter / splice / adapter) |
| **Координаты** | WGS84 ↔ local ENU / UTM / Mercator, пакетная обработка |
| **Графика** | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |
| **Cleanup CLI** | `cleanup-simpleworkernet` — логи, кэш, конфиг |

---

## Структура пакета

```text
src/simpleworkernet/
├── core/                    # client, config, logger, field-cache
├── models/                  # BaseModel, primitives, categories/*
├── smartdata/               # SmartData, metadata
├── utils/
│   ├── graphics.py
│   └── topology/
│       ├── topology.py      # фасад Topology
│       ├── cache.py         # DataCache (инстанс)
│       ├── graphs/          # CGraph, FNGraph
│       ├── builders/        # GraphBuilder + handlers
│       └── attenuation/     # калькулятор затуханий
│           ├── calculator.py
│           ├── catalog.py
│           ├── models.py
│           ├── length.py
│           ├── template.py
│           └── defaults.json
└── scripts/uninstall.py
```

### Публичный импорт

```python
from simpleworkernet import (
    WorkerNetClient,
    SmartData, Where, Operator,
    BaseModel, smart_model, CollapsedField,
    vStr, GeoPoint, GeoPointArray, vMoney,
    config_manager, log, cache,
    Topology, CGraph, FNGraph,
    cleanup,
)
from simpleworkernet.utils.topology import (
    Attenuation, AttenuationCatalog, PathReport, DataCache,
)
```

---

## Установка

```bash
pip install simpleworkernet
# или
pip install git+https://github.com/busy4beaver/simpleworkernet.git

pip install python-igraph pyproj Wand   # topology / UTM / SVG→PNG
```

---

## Быстрый старт

```python
from simpleworkernet import WorkerNetClient, Where, Operator

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    customers = client.Module.get_user_list()
    active = customers.where("state_id", 2)
    print(active.count())
```

---

## Конфигурация

`config_manager` — единая точка настроек. Изменения сразу; persistence — `save()`.

```python
from simpleworkernet import config_manager

config_manager.console_level = "INFO"
config_manager.file_level = "DEBUG"
config_manager.cache_enabled = True
config_manager.cache_max_size = 200000
config_manager.cache_evict_strategy = "lfu"
config_manager.save()
```

---

## Каталоги данных

Пути совпадают с `core.config` и `scripts/uninstall`.

| ОС | Config | Cache | Logs |
|----|--------|-------|------|
| **Linux** | `~/.config/simpleworkernet/<app>/` | `~/.cache/simpleworkernet/<app>/` | `~/.local/share/simpleworkernet/<app>/logs/` |
| **Windows** | `%APPDATA%\simpleworkernet\<app>\` | `%LOCALAPPDATA%\simpleworkernet\<app>\` | `%APPDATA%\simpleworkernet\<app>\logs\` |
| **macOS** | `~/Library/Application Support/simpleworkernet/<app>/` | `~/Library/Caches/simpleworkernet/<app>/` | `~/Library/Logs/simpleworkernet/<app>/` |

`<app>` — имя приложения с хешем (`get_app_name`). Очистка: `cleanup-simpleworkernet`.

---

## Очистка данных

```bash
cleanup-simpleworkernet              # с подтверждением
cleanup-simpleworkernet --force
cleanup-simpleworkernet --dry-run
cleanup-simpleworkernet --list
cleanup-simpleworkernet --logs-only
cleanup-simpleworkernet --cache-only
cleanup-simpleworkernet --config-only
```

```python
from simpleworkernet import cleanup
cleanup(force=True, mode="cache")  # logs | cache | config | all
```

---

## Графовая топология

**Зависимость:** `pip install python-igraph`

```python
from simpleworkernet import WorkerNetClient, Topology
from simpleworkernet.utils.topology import DataCache

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()
topo = Topology(client, cache=cache)

topo.build_from_cross("98d9d368-…", port=7)
customers = topo.get_customers()
linear = topo.topology_from_commutation("customer", customers[0])
```

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | интерфейсы (obj + side + port) | коммутации |
| **FNGraph** | node_id | fiber_id |

Методы: `build_from_device/customer/cross/splitter/cwdm/fiber/cable/node`, фильтры `included_fibers` / `excluded_fibers` / `excluded_nodes`, `topology_from_commutation`, `save_to_file` / `load_from_file`.

---

## Оптические затухания (Attenuation)

Расчёт **по запросу** (не при `build`) по уже построенному CGraph.

```python
from simpleworkernet.utils.topology import (
    Topology, Attenuation, AttenuationCatalog,
)
from simpleworkernet.utils.topology.attenuation.template import generate_template

# 1) топология
topo = Topology(client)
topo.build_from_device("olt", 12345, port=1)
linear = topo.topology_from_commutation("customer", customer_id)

# 2) каталог профилей (defaults + overrides)
cat = AttenuationCatalog.with_defaults()
# cat = AttenuationCatalog.from_json("my_profiles.json")
# cat.force_fiber(23682, 0.20)
# cat.force_splitter_port(35196, port=3, db=10.5)

# 3) расчёт
att = Attenuation(
    linear.cgraphs[0],
    catalog=cat,
    wavelength=1550,
    cache=topo._cache,
    client=client,
)
report = att.olt_to_customer(customer_id)
# или: att.along_linear()
print(report.to_table())
print(report.total_db, report.by_kind())
```

### Сегменты пути

| kind | Источник |
|------|----------|
| `fiber` | α(дБ/км) × L(км); L: opticalen2 → opticalen → geo×k → geo_api |
| `splitter` | порт OUT (side=2): force → instance → catalog → ratio → estimate |
| `adapter` | internal-ребро кросса |
| `splice` / `connector` | внешние стыки |
| `force` | override на connect_id / fiber / splitter port |

### Каталог и шаблон

```python
# шаблон из live API (кабели + сплиттеры)
cat = generate_template(client, cache=topo._cache, path="attenuation.json")
# пользователь дозаполняет ports / db_per_km, затем:
cat = AttenuationCatalog.from_json("attenuation.json")
```

Defaults: `utils/topology/attenuation/defaults.json` (1310/1490/1550 nm, splice 0.05, connector 0.3, adapter 0.2, типовые 1xN ratios).

### Удобные запросы

| Метод | Назначение |
|-------|------------|
| `path(src, dst)` | shortest path + сумма сегментов |
| `along_linear()` | обход линейного CGraph |
| `olt_to_customer(id)` | downstream OLT→абонент |
| `customer_to_olt(id)` | upstream |
| `olt_to_splitter_out(id, port)` | до выхода сплиттера |
| `budget_summary()` / `worst_customer()` | по всем абонентам графа |

`PathReport`: `total_db`, `segments`, `to_table()`, `to_dict()`, `by_kind()`, `warnings`, `missing`.

---

## Тесты

```bash
pytest tests/ -m "not integration" -v          # offline
pytest tests/ -v --wn-host=… --wn-apikey=…     # + live
```

Env: `WORKERNET_HOST`, `WORKERNET_APIKEY`, `WORKERNET_TEST_NODE_ID`, `WORKERNET_TEST_CUSTOMER_ID`.

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
