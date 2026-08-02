# **SimpleWorkerNet**

Python-клиент для REST API [WorkerNet](https://workernet.ru) с типизацией ответов, SmartData и графовой топологией сети.

[![Tag](https://img.shields.io/github/v/tag/busy4beaver/simpleworkernet?color=00c2e8)](https://pypi.org/project/simpleworkernet/)
[![Supported Python versions](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=FFE873)](https://www.python.org/downloads/)
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
| **Логирование** | Консольный вывод, включение из клиентского кода |
| **Кэш полей** | LFU / LRU / FIFO, dirty-flag, предзагрузка из моделей |
| **Топология** | CGraph + FNGraph, фильтры, линейные цепочки, save/load |
| **Attenuation** | Расчёт оптических затуханий по CGraph (fiber / splitter / splice / adapter) |
| **Координаты** | WGS84 ↔ Mercator (default) / local ENU / UTM |
| **Графика** | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |
| **Cleanup CLI** | `cleanup-simpleworkernet` — логи, кэш, конфиг |

---

## Структура пакета

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
│   ├── logger.py            # консольный логгер (без файлов)
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
    save_svg, load_svg, svg_to_png,
)
from simpleworkernet.utils.topology import (
    Attenuation, AttenuationCatalog, PathReport, DataCache,
)
```

---

## Установка

Базовый пакет:

```bash
pip install simpleworkernet
```

Или из GitHub:

```bash
pip install git+https://github.com/busy4beaver/simpleworkernet.git
```

Опциональные зависимости:

```bash
pip install python-igraph
```

```bash
pip install pyproj
```

```bash
pip install Wand
```

| Пакет | Зачем |
|-------|-------|
| `python-igraph` | графовая топология (CGraph / FNGraph) |
| `pyproj` | проекция UTM |
| `Wand` (ImageMagick) | SVG → PNG (один из бэкендов) |

---

## Быстрый старт

```python
from simpleworkernet import WorkerNetClient, Where, Operator

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    customers = client.Module.get_user_list()
    active = customers.where("state_id", 2)
    print(active.count())

    # fluent-фильтры
    rich = customers.where("balance", Operator.GE, 1000)
    moscow = customers.where("city", "Москва")
```

Контекстный менеджер открывает/закрывает сессию автоматически.
Без `with` — вызывайте `client.session()` / `client.closeSession()`.

---

## Конфигурация

`config_manager` — синглтон процесса. Изменения применяются сразу;
persistence — только через `save()`.

### Значения по умолчанию

| Параметр | Default | Описание |
|----------|---------|----------|
| `console_level` | `"INFO"` | уровень консольного логгера |
| `console_output` | `False` | вывод в stdout (включается из клиентского кода) |
| `cache.enabled` | `True` | SmartDataCache включён |
| `cache.max_size` | `200000` | макс. записей |
| `cache.evict_strategy` | `"lru"` | `lru` / `lfu` / `fifo` |
| `cache.evict_threshold` | `0.95` | порог заполнения для eviction |
| `cache.evict_percent` | `0.25` | доля удаляемых записей |
| `cache.auto_save` | `True` | автосохранение при выходе |
| `default_timeout` | `30` | таймаут HTTP (сек) |
| `max_retries` | `3` | число повторов |
| `user_agent` | `"SimpleWorkerNet/1.0"` | User-Agent |
| `smartdata_max_depth` | `100` | макс. глубина кастинга |

### Примеры

```python
from simpleworkernet import config_manager

config_manager.console_level = "INFO"
config_manager.console_output = True  # включить логи из клиентского кода

config_manager.cache_enabled = True
config_manager.cache_max_size = 200000
config_manager.cache_evict_strategy = "lfu"

config_manager.default_timeout = 60
config_manager.save()          # записать в config.json

config_manager.show_config()  # печать текущих значений
config_manager.reset(save=True)  # сброс на defaults
```

Массовое обновление:

```python
config_manager.update(
    console_level="WARNING",
    cache={"max_size": 100000, "evict_strategy": "fifo"},
    save=True,
)
```

---

## Основные компоненты

### WorkerNetClient

```python
from simpleworkernet import WorkerNetClient

client = WorkerNetClient(
    host="my.workernet.ru",
    apikey="key",
    protocol="https",   # default
    port=443,           # default
)
client.session()

# категории API — атрибуты клиента
users = client.Module.get_user_list()
nodes = client.Node.get()
fibers = client.Fiber.get_list(cable_line_type_id=1)

client.closeSession()
```

### SmartData

Ответы API автоматически оборачиваются в `SmartData`:

```python
users = client.Module.get_user_list()

users.count()
users.to_list()                    # list[model]
users.where("state_id", 2)
users.where("balance", Operator.GE, 500)
users.select("id", "name")
users.first()
users.map(lambda u: u.name)
```

### BaseModel / smart_model

```python
from simpleworkernet import BaseModel, smart_model, vStr

@smart_model
class DeviceInfo(BaseModel):
    id: int
    name: vStr
    parent_id: int | None = None
```

Рекурсивный кастинг Union / Optional / List / вложенных моделей из сырого JSON.

---

## Логирование

Логирование только в консоль. Файлы не создаются. Клиентский код включает вывод так:

```python
from simpleworkernet import log, config_manager

# включить логи библиотеки и свои сообщения через тот же log
config_manager.console_output = True
config_manager.console_level = "DEBUG"
# или: log.set_console_output(True)

log.info("старт")
log.debug("детали")
log.warning("внимание")
log.error("ошибка")

# доступ к стандартному logging.Logger при необходимости
# log.underlying_logger
```

По умолчанию `console_output=False` — библиотека молчит, пока клиент явно не включит логи.

---

## Кэширование

`cache` — синглтон SmartDataCache (метаданные полей моделей).

```python
from simpleworkernet import cache, config_manager

config_manager.cache_enabled = True
cache.stats()       # размер, hits/misses
cache.clear()
cache.save()
cache.load()
```

При старте пакета (если кэш включён) выполняется предзагрузка схем из всех category-моделей.

Для топологии используется отдельный **DataCache** (не синглтон) — см. ниже.

---

## Каталоги данных

Пути совпадают с `core.config` и `scripts/uninstall`.
`<app>` — имя приложения с хешем (`get_app_name(with_hash=True)`).

| ОС | Config | Cache | Logs |
|----|--------|-------|------|
| **Linux** | `~/.config/simpleworkernet/<app>/` | `~/.cache/simpleworkernet/<app>/` | `~/.local/share/simpleworkernet/<app>/logs/` (legacy) |
| **Windows** | `%APPDATA%\\simpleworkernet\\<app>\\` | `%LOCALAPPDATA%\\simpleworkernet\\<app>\\` | `%APPDATA%\\simpleworkernet\\<app>\\logs\\` (legacy) |
| **macOS** | `~/Library/Application Support/simpleworkernet/<app>/` | `~/Library/Caches/simpleworkernet/<app>/` | `~/Library/Logs/simpleworkernet/<app>/` (legacy) |

Файл конфигурации: `config.json` в Config-директории.

Директория Logs больше не используется для записи; `cleanup-simpleworkernet --logs-only` удаляет только старые (legacy) файлы.

---

## Очистка данных

CLI:

```bash
cleanup-simpleworkernet
```

```bash
cleanup-simpleworkernet --force
```

```bash
cleanup-simpleworkernet --dry-run
```

```bash
cleanup-simpleworkernet --list
```

```bash
cleanup-simpleworkernet --logs-only
```

```bash
cleanup-simpleworkernet --cache-only
```

```bash
cleanup-simpleworkernet --config-only
```

Из Python:

```python
from simpleworkernet import cleanup

cleanup(force=True, mode="all")    # logs | cache | config | all
cleanup(force=True, mode="cache")
```

---

## Графика

```python
from simpleworkernet import save_svg, load_svg, svg_to_png

save_svg(svg_string, "scheme.svg")
data = load_svg("scheme.svg")
svg_to_png("scheme.svg", "scheme.png", width=1200)
```

Бэкенды (первый доступный): Wand → Cairo → Inkscape → WeasyPrint.

---

## Координаты

`GeoPoint` / `GeoPointArray` — WGS84 и проекции в плоские метры.

**По умолчанию:** `projection="mercator"` (Web Mercator).

### Проекции

| `projection` | Описание | Зависимости |
|--------------|----------|-------------|
| `"mercator"` **(default)** | Web Mercator; relative → метры через × cos(lat) | нет |
| `"local"` | East/North относительно `center`; Y = истинный север | нет |
| `"utm"` | UTM-зона по долготе; опционально `correct_grid_north` | `pyproj` |

### Масштаб Mercator

Web Mercator завышает наземные расстояния в `1/cos(φ)`.

При **relative**-режиме (`center` задан, `absolute=False`) и
`auto_scale_mercator=True` (default):

1. считаются «сырые» mercator-координаты точки и центра;
2. берётся **разность** (delta);
3. delta умножается на `cos(center.lat)`.

Так центр остаётся точно `(0, 0)`, без фиктивного сдвига, а расстояния
на субкилометровых базисах совпадают с `projection="local"` (сфера R=6378137)
с точностью ≪ 0.1 %.

Для подложки тайлов OSM/Google используйте `absolute=True` и
`auto_scale_mercator=False` (сырые EPSG:3857-метры).

```python
from simpleworkernet import GeoPoint, GeoPointArray

origin = GeoPoint(55.75, 37.62)
p = GeoPoint(55.76, 37.63)

# default: mercator relative + metric scale
x, y = p.to_xy(center=origin)

# local ENU (строго East/North)
x, y = p.to_xy(center=origin, projection="local")

# сырой mercator (для тайлов), без ×cos
x, y = p.to_xy(center=origin, auto_scale_mercator=False)

# абсолютный mercator (EPSG:3857-like)
x, y = p.to_xy(absolute=True, auto_scale_mercator=False)

# UTM
x, y = p.to_xy(center=origin, projection="utm")  # нужен pyproj

back = GeoPoint.from_xy(x, y, center=origin)

arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
xy_list = arr.to_xy()          # center = centroid, mercator
sw, ne = arr.bounds()
print(p.distance_to(origin))   # км (haversine)
```

Доп. параметры: `scale`, `offset`, `rotation_deg`, `absolute`,
`correct_grid_north` (UTM).

---

## Графовая топология

**Зависимость:** `pip install python-igraph`

```python
from simpleworkernet import WorkerNetClient, Topology
from simpleworkernet.utils.topology import DataCache

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()          # можно шарить между Topology
topo = Topology(client, cache=cache)

topo.build_from_cross("98d9d368-…", port=7)
topo.build_from_device("olt", 12345, port=1)
topo.build_from_customer(customer_id)
topo.build_from_node(node_id)
topo.build_from_fiber(fiber_id)
topo.build_from_splitter(splitter_id)
topo.build_from_cwdm(cwdm_id)
topo.build_from_cable(cable_id)

customers = topo.get_customers()
linear = topo.topology_from_commutation("customer", customers[0])

topo.save_to_file("topo.json")
topo2 = Topology.load_from_file("topo.json", client=client, cache=cache)
```

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | интерфейсы (`obj_type` + `obj_id` + `side` + `port`) | коммутации |
| **FNGraph** | `node_id` | `fiber_id` |

Фильтры при build: `included_fibers`, `excluded_fibers`, `excluded_nodes`.

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

### Defaults (`defaults.json`)

| Параметр | 1310 nm | 1490 nm | 1550 nm |
|----------|---------|---------|----------|
| fiber дБ/км | 0.35 | 0.28 | 0.22 |
| splice | 0.05 дБ | | |
| connector | 0.30 дБ | | |
| adapter | 0.20 дБ | | |
| geo_slack_k | 1.03 | | |
| splitter_excess | 0.5 дБ | | |

Типовые ratio-профили сплиттеров: `1x2_50/50`, `1x2_5/95`, …, `1x4_equal`, `1x8_equal`.

### Каталог и шаблон

```python
# шаблон из live API (кабели + сплиттеры)
cat = generate_template(client, cache=topo._cache, path="attenuation.json")
# пользователь дозаполняет ports / db_per_km, затем:
cat = AttenuationCatalog.from_json("attenuation.json")
```

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

### Offline (unit)

Не требуют API. Покрывают примитивы, координаты, SmartData, operators,
topology (CGraph/FNGraph/handlers/linear/merge/attenuation/cache) на
синтетических данных.

```bash
pytest tests/ -m "not integration" -v
```

Только координаты:

```bash
pytest tests/test_coordinates.py -v
```

Только топология:

```bash
pytest tests/topology/ -v
```

### Integration (live API)

Нужны доступный WorkerNet и ключ.

```bash
pytest tests/ -v --wn-host=my.workernet.ru --wn-apikey=YOUR_KEY
```

Или через окружение:

```bash
export WORKERNET_HOST=my.workernet.ru
export WORKERNET_APIKEY=YOUR_KEY
export WORKERNET_PROTOCOL=https
export WORKERNET_PORT=443
export WORKERNET_TEST_NODE_ID=123
export WORKERNET_TEST_CUSTOMER_ID=456
pytest tests/ -v
```

CLI-опции pytest (см. `tests/conftest.py`):

| Опция | Env | Описание |
|-------|-----|----------|
| `--wn-host` | `WORKERNET_HOST` | хост API |
| `--wn-apikey` | `WORKERNET_APIKEY` | API-ключ |
| `--wn-protocol` | `WORKERNET_PROTOCOL` | `http` / `https` (default `https`) |
| `--wn-port` | `WORKERNET_PORT` | порт (default `443`) |
| `--nodeid` | `WORKERNET_TEST_NODE_ID` | ID узла для live topology |
| `--customerid` | `WORKERNET_TEST_CUSTOMER_ID` | ID абонента |

Без host/apikey integration-тесты автоматически `skip`.

Маркер: `@pytest.mark.integration`.

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
