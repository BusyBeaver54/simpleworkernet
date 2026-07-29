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
  - [WorkerNetClient](#workernetclient)
  - [Категории API](#категории-api)
  - [BaseModel и smart_model](#basemodel-и-smart_model)
  - [SmartData](#smartdata)
  - [Примитивные типы](#примитивные-типы)
  - [Операторы фильтрации](#операторы-фильтрации)
  - [Исключения](#исключения)
- [Логирование](#логирование)
- [Кэширование](#кэширование)
- [Очистка данных](#очистка-данных)
- [Графика (SVG/PNG)](#графика-svgpng)
- [Координаты](#координаты)
- [Графовая топология (Topology)](#графовая-топология-topology)
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
| **Topology** | CGraph + FNGraph, фильтры, линейные цепочки, save/load |
| **Graphics** | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |
| **Cleanup CLI** | `cleanup-simpleworkernet` — логи, кэш, конфиг |

---

## Структура пакета

```text
src/simpleworkernet/
├── __init__.py              # публичный API пакета
├── __version__.py
├── __main__.py
├── cli.py                   # entry point cleanup-simpleworkernet
│
├── core/
│   ├── client.py            # WorkerNetClient
│   ├── config.py            # config_manager
│   ├── logger.py            # log
│   ├── cache.py             # SmartData field cache
│   ├── constants.py         # DEBUG, INFO, …
│   ├── exceptions.py
│   └── typing.py
│
├── models/
│   ├── base.py              # BaseModel, BaseCategory, smart_model, CollapsedField
│   ├── primitives.py        # vStr, GeoPoint, vMoney, …
│   ├── operators.py         # Operator, Where
│   └── categories/          # 30+ категорий API (Customer, Fiber, Node, …)
│
├── smartdata/
│   ├── core.py              # SmartData
│   ├── processor.py
│   ├── helpers.py
│   └── metadata.py          # MetaData, PathSegment, SegmentType
│
├── utils/
│   ├── decorators.py        # api_method, timer, retry, …
│   ├── app_name.py
│   ├── graphics.py          # SVGHandler, ImageHandler
│   ├── coordinates.py       # geo_to_xy, geo_to_xyz, xy_to_geo
│   └── topology/            # графовая топология сети
│       ├── topology.py      # Topology
│       ├── cache.py         # DataCache
│       ├── keys.py          # ObjKey, Interface
│       ├── models.py        # CGraphVertex/Edge, FNGraphVertex/Edge
│       ├── constants.py
│       ├── context.py       # BuildContext
│       ├── merge.py
│       ├── linear.py        # LinearPathFinder
│       ├── graphs/          # BaseGraph, CGraph, FNGraph
│       └── builders/        # GraphBuilder + handlers
│
└── scripts/
    └── uninstall.py         # cleanup
```

### Публичный импорт (топ-уровень)

```python
from simpleworkernet import (
    WorkerNetClient,
    SmartData, Where, Operator,
    BaseModel, BaseCategory, smart_model, CollapsedField,
    vStr, GeoPoint, vMoney, vPhoneNumber,  # …
    config_manager, log, cache,
    Topology, CGraph, FNGraph,
    save_svg, load_svg, svg_to_png,
    cleanup,
)
```

---

## Установка

```bash
pip install simpleworkernet
# или
pip install git+https://github.com/busy4beaver/simpleworkernet.git
```

| Доп. возможность | Пакет |
|------------------|-------|
| Графовая топология | `python-igraph` |
| SVG → PNG (рекомендуется) | `Wand` (+ ImageMagick) |
| Альтернативы PNG | `cairosvg`, `weasyprint` |
| Dev / тесты | `pytest`, см. `requirements-dev.txt` |

```bash
pip install python-igraph Wand
pip install -r requirements-dev.txt   # pytest и др. для разработки
```

---

## Быстрый старт

### Минимальный пример

```python
from simpleworkernet import WorkerNetClient

client = WorkerNetClient(
    host="my.workernet.ru",
    apikey="your-secret-api-key",
)

cables = client.Fiber.catalog_cables_get()
print(f"Кабелей в каталоге: {len(cables)}")
```

### Контекстный менеджер (одна HTTP-сессия)

```python
from simpleworkernet import WorkerNetClient

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    customers = client.Module.get_user_list()
    cities = client.Address.get_city()
    print(f"Абонентов: {len(customers)}, городов: {len(cities)}")
```

### Фильтрация

```python
from simpleworkernet import WorkerNetClient, Where, Operator

client = WorkerNetClient("my.workernet.ru", "your-api-key")
customers = client.Module.get_user_list()

filtered = customers.filter(
    Where("state_id", 2),
    Where("balance", 1000, Operator.GT),
    Where("full_name", "Иван", Operator.LIKE),
    join="AND",
)
print(f"Найдено: {filtered.count()}")

active = customers.where("state_id", 2)
```

---

## Конфигурация

`config_manager` — единая точка настроек. Изменения применяются сразу; для persistence вызовите `save()`.

### Просмотр

```python
from simpleworkernet import config_manager

config_manager.show_config()
print(config_manager.show_config(return_string=True))
```

### Основные параметры

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `console_level` | — | Уровень логов в консоль |
| `file_level` | — | Уровень логов в файл |
| `console_output` | `True` | Писать в stdout |
| `log_to_file` | — | Писать в файл |
| `max_log_files` | — | Ротация файлов логов |
| `cache_enabled` | — | Кэш полей SmartData |
| `cache_max_size` | — | Макс. записей |
| `cache_evict_strategy` | `'lfu'` | `'lfu'` \| `'lru'` \| `'fifo'` |
| `cache_evict_threshold` | `0.9` | Порог запуска очистки |
| `cache_evict_percent` | `0.2` | Доля удаляемых за раз |
| `cache_auto_save` | — | Автосохранение при dirty |
| `default_timeout` | — | Таймаут HTTP, сек |
| `max_retries` | — | Повторы при ошибке |
| `user_agent` | — | User-Agent |
| `smartdata_max_depth` | — | Макс. глубина обработки |

### Пример

```python
from simpleworkernet import config_manager

config_manager.console_level = "INFO"
config_manager.file_level = "DEBUG"
config_manager.console_output = True
config_manager.log_to_file = True
config_manager.max_log_files = 30

config_manager.cache_enabled = True
config_manager.cache_max_size = 200000
config_manager.cache_evict_strategy = "lfu"
config_manager.cache_evict_threshold = 0.95
config_manager.cache_evict_percent = 0.3
config_manager.cache_auto_save = True

config_manager.default_timeout = 45
config_manager.max_retries = 3
config_manager.save()
```

### Массовое обновление / сброс

```python
config_manager.update(
    console_level="INFO",
    cache_enabled=True,
    cache_max_size=100000,
    save=True,
)

config_manager.reset(save=True)
```

**Как работает очистка кэша:** при заполнении ≥ `max_size * threshold` удаляется `evict_percent` записей по выбранной стратегии (LFU / LRU / FIFO). На диск кэш пишется только при реальных изменениях (dirty).

---

## Основные компоненты

### WorkerNetClient

```python
from simpleworkernet import WorkerNetClient

client = WorkerNetClient("my.workernet.ru", "your-api-key")

customers = client.Customer.get_data()
devices = client.Device.get_data(object_type="switch")
fibers = client.Fiber.get_list()
nodes = client.Node.get()
```

Категории доступны как атрибуты клиента (`client.Fiber`, `client.Module`, …) и соответствуют классам в `models.categories`.

### Категории API

| Атрибут клиента | Модуль |
|-----------------|--------|
| `Additional_data` | Доп. данные |
| `Address` | Адреса |
| `Advertising` | Реклама |
| `Attach` | Вложения |
| `Billing` | Биллинг |
| `Cable_route` | Кабельные трассы |
| `Call` | Звонки |
| `Commutation` | Коммутации |
| `Cross` | Кроссы |
| `Customer` | Абоненты |
| `Cwdm` | CWDM |
| `Device` | Устройства (OLT, switch, ONU, …) |
| `Employee` | Сотрудники |
| `Fiber` | Кабели / волокна |
| `Gps` | GPS |
| `Inventory` | Склад |
| `Key` | Ключи |
| `Map` | Карта |
| `Module` | Сводные списки / справочники |
| `Node` | Сооружения связи |
| `Notepad` | Блокнот |
| `Owner` | Владельцы |
| `Service` | Услуги |
| `Setting` | Настройки |
| `Sms` | SMS |
| `Splitter` | Сплиттеры |
| `System` | Система |
| `Tariff` | Тарифы |
| `Task` | Задачи |
| `Trader` | Трейдеры |
| `Vehicle` | Транспорт |
| `Vlan` | VLAN |

### BaseModel и smart_model

```python
from simpleworkernet import smart_model, BaseModel, CollapsedField, vStr, GeoPoint, vPhoneNumber
from simpleworkernet.smartdata.metadata import SegmentType
from typing import Optional

@smart_model
class Contact(BaseModel):
    email: Optional[str]
    phone: Optional[vPhoneNumber]
    telegram: Optional[str]

@smart_model
class Address(BaseModel):
    id: int
    city: vStr
    street: vStr
    house: str
    apartment: Optional[int]
    coordinates: GeoPoint
    contacts: Optional[Contact]
```

`CollapsedField` — доступ к «схлопнутым» ключам из метаданных пути в JSON.

`@api_method` (из `utils.decorators`) связывает метод категории с моделью ответа; опционально — `preprocessor` для нормализации ключей API.

### SmartData

Контейнер ответа API с fluent-API:

```python
customers = client.Module.get_user_list()  # уже SmartData

result = (
    customers
    .where("balance", 0, Operator.GT)
    .where("state_id", 2)
    .sort(key=lambda x: x.balance, reverse=True)
    .limit(10)
    .map(lambda x: x.full_name)
)

by_state = customers.group_by(lambda x: x.state_id)
for state, group in by_state.items():
    print(state, group.count(), group.avg(lambda x: x.balance))
```

| Метод | Назначение |
|-------|------------|
| `where` / `filter` | Условия (`Where`, `Operator`) |
| `sort` / `limit` | Сортировка и срез |
| `map` / `group_by` | Трансформация и группировка |
| `count` / `avg` / `max` / `min` | Агрегаты |
| `find_all` | Глубокий поиск по вложенности |
| `to_list` / `to_file` / `from_file` | Выгрузка / сериализация |

Метаданные:

```python
from simpleworkernet.smartdata.metadata import MetaData, SegmentType

for item in customers:
    if item.meta:
        print(item.meta.get_path_string())
        print(item.get_collapsed_keys())
```

### Примитивные типы

| Тип | Назначение |
|-----|------------|
| `vStr` | Строка с URL/HTML-декодированием |
| `vFlag` | Флаг |
| `GeoPoint` | Координаты, расстояние |
| `vPhoneNumber` | Телефон (`normalized`, `international`) |
| `vMoney` | Деньги + арифметика |
| `vPercent` | Проценты (`.of(base)`) |
| `vPeriod` | Период |
| `vINN` / `vKPP` / `vSNILS` / `vOGRN` | Реквизиты РФ |
| `additional_field` / `additional_data` | Доп. поля |

```python
from simpleworkernet import vStr, GeoPoint, vPhoneNumber, vMoney, vPercent

text = vStr("Hello%20World&amp;Co")
point = GeoPoint(55.75, 37.62)
phone = vPhoneNumber("+7 (123) 456-78-90")
money = vMoney(100.50, "RUB") + 50.25
p = vPercent(15.5)  # p.of(1000) → 155.0
```

### Операторы фильтрации

| `Operator` | Значение | Смысл |
|------------|----------|-------|
| `EQ` | `==` | Равно |
| `NE` | `!=` | Не равно |
| `GT` | `>` | Больше |
| `LT` | `<` | Меньше |
| `GTE` | `>=` | ≥ |
| `LTE` | `<=` | ≤ |
| `LIKE` | `LIKE` | Подстрока (case-insensitive) |
| `IN` | `IN` | Вхождение в список |
| `BETWEEN` | `BETWEEN` | Диапазон `[min, max]` |
| `REGEX` | `REGEX` | Регулярное выражение |

```python
from simpleworkernet import Where, Operator

Where("age", [25, 35], Operator.BETWEEN)
Where("city", ["Москва", "СПб"], Operator.IN)
Where("name", r"^Ив", Operator.REGEX)
```

### Исключения

| Класс | Когда |
|-------|-------|
| `WorkerNetError` | Базовый |
| `WorkerNetConfigError` | Конфиг |
| `WorkerNetConnectionError` | Сеть / таймаут |
| `WorkerNetAPIError` | Ответ API (status, body) |
| `WorkerNetCacheError` | Кэш |
| `WorkerNetValidationError` | Валидация |
| `WorkerNetSmartDataError` | SmartData |
| `WorkerNetRecursionError` | Глубина рекурсии |
| `GraphicsError` | Графика |
| `SVGValidationError` | Невалидный SVG |

---

## Логирование

```python
from simpleworkernet import config_manager, log

config_manager.console_level = "INFO"
config_manager.file_level = "DEBUG"
config_manager.console_output = True
config_manager.log_to_file = True

print(log.get_session_id(), log.get_log_file())
log.new_session()
```

Файлы логов:

```text
~/.local/share/simpleworkernet/<app>_<hash>/logs/
├── <app>_YYYYMMDD_HHMMSS.log
└── ...
```

---

## Кэширование

Кэш **имён полей** SmartData (не путать с `topology.DataCache`).

```python
from simpleworkernet import SmartData, cache

SmartData.save_cache(force=True)
stats = SmartData.get_cache_stats()
# hits, misses, hit_rate, field_cache_size, dirty, enabled

SmartData.preload_from_models(Customer.Get_data, recursive=True)

# при выходе — только если dirty
cache.ensure_saved()
```

---

## Очистка данных

### CLI

```bash
cleanup-simpleworkernet              # с подтверждением
cleanup-simpleworkernet --force
cleanup-simpleworkernet --dry-run
cleanup-simpleworkernet --list
cleanup-simpleworkernet --app myapp_abc123
cleanup-simpleworkernet --logs-only
cleanup-simpleworkernet --cache-only
cleanup-simpleworkernet --config-only
cleanup-simpleworkernet --version
```

### Программно

```python
from simpleworkernet import cleanup

cleanup()
cleanup(force=True)
cleanup(force=True, app_name="myapp_abc123")
cleanup(force=True, mode="cache")  # logs | cache | config
```

---

## Графика (SVG/PNG)

Модуль `simpleworkernet.utils.graphics` — схемы коммутаций и прочие SVG из API.

| Символ | Назначение |
|--------|------------|
| `SVGHandler` | Загрузка, метаданные, save, to_png |
| `ImageHandler` | Растровые изображения |
| `save_svg` / `load_svg` / `is_svg` | Быстрые функции |
| `svg_to_png` | Конвертация |
| `WAND_AVAILABLE`, `CAIRO_AVAILABLE`, … | Флаги бэкендов |

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.graphics import SVGHandler, svg_to_png, is_svg

client = WorkerNetClient("host", "apikey")
svg_data = client.Node.get_scheme(id=123)

svg = SVGHandler(svg_data)
if svg.is_svg():
    print(svg.size, svg.has_cyrillic, svg.metadata.get("element_count"))
    svg.save("scheme.svg")
    svg.to_png("scheme.png", method="auto", max_size=(1920, 1080))
    # svg.to_png_wand / to_png_cairo / to_png_inkscape / to_png_weasyprint

svg_to_png(svg_data, "out.png")
```

---

## Координаты

```python
from simpleworkernet.utils.coordinates import geo_to_xy, geo_to_xyz, xy_to_geo

# гео → локальная плоскость / 3D / обратно
```

---

## Графовая топология (Topology)

Пакет `simpleworkernet.utils.topology` — построение и анализ топологии сети.

| Граф | Вершины | Рёбра | Хранение |
|------|---------|-------|----------|
| **CGraph** | интерфейсы (объект + side + port) | коммутации | `List[CGraph]` связных компонент |
| **FNGraph** | сооружения (`node_id`) | кабели (`fiber_id`) | один связный `FNGraph` |

### Архитектура

```text
utils/topology/
├── __init__.py
├── constants.py         # TYPE_*, DEVICE/SIDE/TERMINAL_TYPES
├── keys.py              # ObjKey, Interface
├── models.py            # CGraphVertex/Edge, FNGraphVertex/Edge
├── cache.py             # DataCache (инстанс)
├── context.py           # BuildContext
├── merge.py             # merge_cgraphs, merge_fngraphs
├── linear.py            # LinearPathFinder
├── topology.py          # Topology
├── graphs/
│   ├── base.py          # composition над igraph
│   ├── cgraph.py
│   └── fngraph.py
└── builders/
    ├── base.py          # GraphBuilder
    └── handlers.py      # Terminal / Cross / Fiber / SplitterCwdm
```

```python
from simpleworkernet.utils.topology import (
    Topology, CGraph, FNGraph, DataCache,
    ObjKey, Interface,
    merge_cgraphs, merge_fngraphs,
)
# или
from simpleworkernet.utils import Topology, CGraph, FNGraph
from simpleworkernet import Topology, CGraph, FNGraph
```

**Зависимость:** `pip install python-igraph`

### DataCache

Кэш объектов и коммутаций API — **экземпляр**, не синглтон:

```python
from simpleworkernet.utils.topology import Topology, DataCache

cache = DataCache()
topo1 = Topology(client, cache=cache)
topo2 = Topology(client, cache=cache)  # общий кэш
cache.clear()
```

Не путать с глобальным `simpleworkernet.cache` (поля SmartData).

### Методы построения

| Метод | Старт |
|-------|-------|
| `build_from_device(object_type, object_id, port=None, …)` | OLT / switch / ONU |
| `build_from_customer(object_id, …)` | Абонент |
| `build_from_cross(object_id, port=None, side=None, …)` | Кросс (UUID) |
| `build_from_splitter(object_id, port=None, side=None, …)` | Сплиттер |
| `build_from_cwdm(object_id, port=None, side=None, …)` | CWDM |
| `build_from_fiber(object_id, port, side=None, …)` | Волокно (`object_id` = кабель, `port` = № волокна) |
| `build_from_cable(object_id, …)` | Все волокна кабеля |
| `build_from_node(object_id, …)` | Узел → FNGraph + CGraph по объектам в узлах |

Общие фильтры всех `build_from_*`:

| Параметр | Поведение |
|----------|-----------|
| `included_fibers` | Разрешённые кабели **только на стартовом узле** |
| `excluded_fibers` | Запрет кабелей (всегда) |
| `excluded_nodes` | Запрет узлов (всегда) |

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import Topology

client = WorkerNetClient("my.workernet.ru", "key")
topo = Topology(client)

topo.build_from_device("olt", 12345, port=1)
topo.build_from_cross("98d9d368-…", port=7)
topo.build_from_splitter(35196)  # все интерфейсы → merge
topo.build_from_fiber(23682, port=1, side=1)
topo.build_from_node(23779, excluded_nodes=[23780])
topo.build_from_cable(23682)
```

### Получение данных

```python
topo.get_customers()   # List[int]
topo.get_nodes()
topo.get_cables()
topo.get_fibers()
topo.get_devices()
topo.get_splitters()
topo.get_cwdms()
topo.get_crosses()     # List[str] UUID

topo.customer(68168)
topo.node(23779)
topo.cable(23682)
topo.fiber(23682)
topo.device(12345)
topo.splitter(35196)
topo.cwdm(12345)
topo.cross("98d9d368-…")

topo.get_finish_by_node(23779)
topo.get_finish_by_object("customer", 68168)
```

### Линейная цепочка

`topology_from_commutation` → новый `Topology` с одним линейным CGraph.

```python
linear = topo.topology_from_commutation("customer", customer_id)

linear = topo.topology_from_commutation(
    "customer", customer_id,
    first_object_type="olt",
    first_object_id=12345,
)

linear = topo.topology_from_commutation(
    "splitter", 35196, port=1, side=2,
)
```

| Правило | |
|---------|---|
| Сплиттер | `port` обязателен |
| Кросс / кабель | `port` + `side` |
| Абонент с несколькими коммутациями | нужен `first_object_*` |
| Без `first_object` | поиск OLT / switch |
| Ветвление | shortest path до `first_object` |
| CWDM на пути | не поддерживается |

### Сохранение / загрузка

```python
topo.save_to_file("topology.pkl")
loaded = Topology.load_from_file("topology.pkl")
```

Сохраняются `cgraphs`, `fngraph`, `DataCache`, параметры клиента.

### Хранение

```python
topo.cgraphs   # List[CGraph]
topo.fngraph   # Optional[FNGraph]

for v in topo.cgraphs[0].get_vertices():
    print(v.obj_type, v.obj_id, v.side, v.port)

for e in topo.cgraphs[0].get_edges():
    print(e.source, e.target, e.connect_id, e.is_internal)
```

Каждый `CGraph` связный; несвязные результаты не добавляются.

### Полный пример

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import Topology, DataCache

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()
topo = Topology(client, cache=cache)

topo.build_from_cross("98d9d368-43e9-4513-9ec7-4e076eea2bda", port=7)
customers = topo.get_customers()
print(f"Абонентов: {len(customers)}")

linear = topo.topology_from_commutation("customer", customers[0])
print(f"Цепочка: {linear.cgraphs[0].vcount()} вершин")
print("Устройства:", linear.get_devices())

topo.save_to_file("my_topo.pkl")
```

### Особенности реализации

| Идея | Деталь |
|------|--------|
| Composition | `CGraph` / `FNGraph` оборачивают `igraph.Graph` |
| Handlers | Правила terminal / cross / fiber / splitter+CWDM |
| BuildContext | Фильтры, очередь BFS, finish-данные |
| DataCache | Инстанс, шаринг между Topology |
| Merge | Пересекающиеся компоненты объединяются |
| Linear path | External-ребро важнее internal; иначе shortest path |

---

## Тесты

Тесты лежат в `tests/`. Настройка pytest — в `pyproject.toml` (`[tool.pytest.ini_options]`).

### Зависимости

```bash
pip install -r requirements-dev.txt
pip install python-igraph          # для topology
# опционально для UTM-координат:
# pip install pyproj
```

### Структура

| Путь | Тип | Сеть |
|------|-----|------|
| `tests/test_*.py` | unit: SmartData, primitives, operators, exceptions, coordinates | нет |
| `tests/topology/` | unit: CGraph, FNGraph, merge, linear, handlers, DataCache | нет |
| `tests/integration/` | live: smoke API, topology | **да** |

Маркер `@pytest.mark.integration` — тесты против реального WorkerNet.

### Unit (без API)

```bash
# всё, кроме live
pytest tests/ -m "not integration" -v

# только topology
pytest tests/topology/ -v

# только core (SmartData, primitives, …)
pytest tests/ --ignore=tests/topology --ignore=tests/integration -v
```

Без credentials integration-тесты **skip**, а не падают — можно запускать весь suite:

```bash
pytest tests/ -v
```

### Integration (реальный API)

Учётные данные передаются через CLI или переменные окружения. Приоритет: **CLI > env**.

| CLI | Env | Описание |
|-----|-----|----------|
| `--wn-host` | `WORKERNET_HOST` | хост API |
| `--wn-apikey` | `WORKERNET_APIKEY` | ключ API |
| `--wn-protocol` | `WORKERNET_PROTOCOL` | `http` \| `https` (по умолчанию `https`) |
| `--wn-port` | `WORKERNET_PORT` | порт (по умолчанию `443`) |

Дополнительно для topology-live:

| Env | Описание |
|-----|----------|
| `WORKERNET_TEST_NODE_ID` | ID узла для `build_from_node` |
| `WORKERNET_TEST_CUSTOMER_ID` | ID абонента для `build_from_customer` |

```bash
# CLI
pytest tests/integration/ -v \
  --wn-host=my.workernet.ru --wn-apikey=SECRET

# env
export WORKERNET_HOST=my.workernet.ru
export WORKERNET_APIKEY=SECRET
pytest tests/integration/ -v

# topology live
export WORKERNET_TEST_NODE_ID=23779
export WORKERNET_TEST_CUSTOMER_ID=68168
pytest tests/integration/test_topology_live.py -v

# только smoke API
pytest tests/integration/test_api_smoke.py -v --wn-host=... --wn-apikey=...
```

Фикстура `live_client` (session-scoped) создаёт `WorkerNetClient` и закрывает сессию после прогона. Ключ **не** коммитьте в репозиторий и не пишите в `pytest.ini`.

### Полезные команды

```bash
pytest tests/ -m "not integration" -q          # быстро, offline
pytest tests/integration/ -v --wn-host=...     # live
pytest tests/ -k "smartdata or topology" -v    # по имени
pytest tests/ --cov=simpleworkernet            # coverage (pytest-cov)
```

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
