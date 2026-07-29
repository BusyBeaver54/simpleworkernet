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
  - [Клиент API](#клиент-api)
  - [Категории API](#категории-api)
  - [Модели и smart_model](#модели-и-smart_model)
  - [SmartData](#smartdata)
  - [Примитивные типы](#примитивные-типы)
  - [Операторы фильтрации](#операторы-фильтрации)
  - [Исключения](#исключения)
- [Логирование](#логирование)
- [Кэширование](#кэширование)
- [Очистка данных](#очистка-данных)
- [Графика](#графика)
- [Координаты](#координаты)
- [Графовая топология](#графовая-топология)
- [Оптические затухания](#оптические-затухания)
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
| **Затухания** | Бюджет линии по CGraph: кабель, сплиттер, кросс, сварка; JSON-профили |
| **Координаты** | WGS84 ↔ local ENU / UTM / Mercator, пакетная обработка |
| **Графика** | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |
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
│   ├── primitives.py        # vStr, GeoPoint, GeoPointArray, vMoney, …
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
│   └── topology/            # графовая топология сети
│       ├── topology.py      # фасад Topology
│       ├── cache.py         # DataCache (инстанс)
│       ├── keys.py          # ObjKey, Interface
│       ├── models.py        # вершины и рёбра CGraph / FNGraph
│       ├── constants.py     # TYPE_*, DEVICE/SIDE/TERMINAL_TYPES
│       ├── context.py       # BuildContext
│       ├── merge.py         # merge_cgraphs, merge_fngraphs
│       ├── linear.py        # LinearPathFinder
│       ├── graphs/          # BaseGraph, CGraph, FNGraph
│       ├── builders/        # GraphBuilder + handlers
│       └── attenuation/     # расчёт оптических затуханий
│           ├── calculator.py    # Attenuation
│           ├── catalog.py       # AttenuationCatalog
│           ├── models.py        # PathReport, AttenuationSegment
│           ├── length.py        # длина кабеля
│           ├── template.py      # генерация JSON из live API
│           └── defaults.json    # типовые α и сплиттеры
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
    vStr, GeoPoint, GeoPointArray, vMoney, vPhoneNumber,
    config_manager, log, cache,
    Topology, CGraph, FNGraph,
    save_svg, load_svg, svg_to_png,
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
# или из git
pip install git+https://github.com/busy4beaver/simpleworkernet.git
```

| Доп. возможность | Пакет |
|------------------|-------|
| Графовая топология и затухания | `python-igraph` |
| UTM-проекция координат | `pyproj` |
| SVG → PNG (рекомендуется) | `Wand` (+ ImageMagick) |
| Альтернативы PNG | `cairosvg`, `weasyprint` |
| Dev / тесты | `pytest`, см. `requirements-dev.txt` |

```bash
pip install python-igraph pyproj Wand
pip install -r requirements-dev.txt
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

**Очистка кэша:** при заполнении ≥ `max_size * threshold` удаляется `evict_percent` записей по выбранной стратегии (LFU / LRU / FIFO). На диск кэш пишется только при реальных изменениях (dirty-flag).

---

## Основные компоненты

### Клиент API

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

### Модели и smart_model

```python
from simpleworkernet import smart_model, BaseModel, CollapsedField, vStr, GeoPoint, vPhoneNumber
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
| `to_list` / `to_dict` / `to_file` / `from_file` | Выгрузка / сериализация |

Метаданные пути:

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
| `GeoPoint` | Координаты WGS84 + проекции XY |
| `GeoPointArray` | Список точек, пакетные проекции |
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
money = vMoney(amount=100.50, currency="RUB") + 50.25
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

## Графика

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

svg_to_png(svg_data, "out.png")
```

---

## Координаты

Всё сосредоточено в `GeoPoint` / `GeoPointArray` (`models.primitives`). Отдельного модуля `coordinates` нет.

### Проекции

| `projection` | Описание | Зависимость |
|--------------|----------|-------------|
| `local` (**по умолчанию**) | Локальная плоскость East/North относительно `center`. Ось **Y = истинный север** — удобно для CAD и картографической подложки | нет |
| `utm` | UTM-зона по долготе. При наличии `center` по умолчанию выравнивается к true north | `pyproj` |
| `mercator` | Web Mercator (EPSG:3857) | нет |

### Одна точка

```python
from simpleworkernet import GeoPoint

pt = GeoPoint(55.75, 37.62)
# также: GeoPoint([55.75, 37.62]), GeoPoint("55.75,37.62"), GeoPoint(lat=…, lon=…)

origin = GeoPoint(55.75, 37.60)

# локальные метры относительно origin (X — восток, Y — север)
x, y = pt.to_xy(center=origin)

# обратно
back = GeoPoint.from_xy(x, y, center=origin)

# UTM / Mercator при необходимости
x, y = pt.to_xy(center=origin, projection="utm")
x, y = pt.to_xy(projection="mercator", absolute=True)

pt.utm_zone
pt.meridian_convergence()   # угол схождения меридианов, °
pt.distance_to(origin)      # км, гаверсинус
```

Доп. параметры: `scale`, `offset`, `rotation_deg`, `absolute`, `auto_scale_mercator`, `correct_grid_north`.

### Массив точек

```python
from simpleworkernet import GeoPointArray

arr = GeoPointArray([(55.75, 37.62), (55.76, 37.63), "55.77,37.64"])
center = arr.center()
xy = arr.to_xy(center=center)
restored = GeoPointArray.from_xy(xy, center=center)
sw, ne = arr.bounds()
```

---

## Графовая топология

Пакет `simpleworkernet.utils.topology` — построение и анализ топологии сети по данным WorkerNet.

**Зависимость:** `pip install python-igraph`

### Два графа

| Граф | Вершины | Рёбра | Хранение |
|------|---------|-------|----------|
| **CGraph** | интерфейсы (объект + side + port) | коммутации (в т.ч. internal) | `List[CGraph]` — связные компоненты |
| **FNGraph** | сооружения (`node_id`) | кабели (`fiber_id`) | один связный `FNGraph` |

### Архитектура

```text
utils/topology/
├── topology.py
├── cache.py
├── keys.py / models.py / constants.py / context.py
├── merge.py / linear.py
├── graphs/          # CGraph, FNGraph
├── builders/        # handlers
└── attenuation/     # см. раздел «Оптические затухания»
```

Импорт:

```python
from simpleworkernet.utils.topology import (
    Topology, CGraph, FNGraph, DataCache,
    ObjKey, Interface,
    Attenuation, AttenuationCatalog, PathReport,
    merge_cgraphs, merge_fngraphs,
)
from simpleworkernet import Topology, CGraph, FNGraph
```

### DataCache

Кэш объектов и коммутаций API — **экземпляр**, можно шарить между несколькими Topology.

Дополнительно для затуханий:

| Метод / хранилище | Назначение |
|-------------------|------------|
| `get_inventory` / `get_inventory_catalog_item` | ТМЦ сплиттера → catalog_id / имя |
| `preload_splitter_inventory` | массовая подгрузка |
| `get_fiber_length_m` / `set_fiber_length_m` | кэш длин |
| `get_geo_length` | `Fiber.get_geo_length` |
| `get_cable_catalog` | `catalog_cables_get` |

```python
from simpleworkernet.utils.topology import Topology, DataCache

cache = DataCache()
topo = Topology(client, cache=cache)
cache.preload_splitter_inventory(client)
```

Не путать с глобальным `simpleworkernet.cache` (имена полей SmartData).

### Методы построения

| Метод | Старт |
|-------|-------|
| `build_from_device(object_type, object_id, port=None, …)` | OLT / switch / ONU |
| `build_from_customer(object_id, …)` | Абонент |
| `build_from_cross(object_id, port=None, side=None, …)` | Кросс (UUID) |
| `build_from_splitter(object_id, port=None, side=None, …)` | Сплиттер |
| `build_from_cwdm(object_id, port=None, side=None, …)` | CWDM |
| `build_from_fiber(object_id, port, side=None, …)` | Волокно |
| `build_from_cable(object_id, …)` | Все волокна кабеля |
| `build_from_node(object_id, …)` | Узел |

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
topo.build_from_splitter(35196)
topo.build_from_fiber(23682, port=1, side=1)
topo.build_from_node(23779, excluded_nodes=[23780])
```

### Получение данных

```python
topo.get_customers()
topo.get_nodes()
topo.get_cables()
topo.get_fibers()
topo.get_devices()
topo.get_splitters()
topo.get_cwdms()
topo.get_crosses()

topo.customer(68168)
topo.node(23779)
topo.cable(23682)
topo.fiber(23682)
topo.device(12345)
topo.splitter(35196)
topo.cross("98d9d368-…")

topo.get_finish_by_node(23779)
topo.get_finish_by_object("customer", 68168)
```

### Линейная цепочка

`topology_from_commutation` → Topology с одним линейным CGraph.

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
| CWDM на пути | **не поддерживается** |

### Сохранение / загрузка

```python
topo.save_to_file("topology.pkl")
loaded = Topology.load_from_file("topology.pkl")
```

### Обход вершин и рёбер

```python
for v in topo.cgraphs[0].get_vertices():
    print(v.obj_type, v.obj_id, v.side, v.port)

for e in topo.cgraphs[0].get_edges():
    print(e.source, e.target, e.connect_id, e.is_internal)
```

### Особенности реализации

| Идея | Деталь |
|------|--------|
| Composition | CGraph / FNGraph оборачивают `igraph.Graph` |
| Handlers | terminal / cross / fiber / splitter+CWDM |
| BuildContext | фильтры, BFS, finish-данные |
| DataCache | инстанс + inventory / длины |
| Linear path | external важнее internal |

---

## Оптические затухания

Модуль `simpleworkernet.utils.topology.attenuation` считает **бюджет оптического тракта** по уже построенному **CGraph**.

Важные свойства:

- расчёт **только по запросу** — не замедляет `build_from_*`;
- CWDM **не поддерживается** (как и в линейной цепочке);
- затухание сплиттера **симметрично** (OLT→клиент и клиент→OLT — одни и те же dB на out-порт);
- профили задаются JSON / кодом / defaults; есть **force**-переопределения.

### Установка зависимости

Тот же `python-igraph`, что и для топологии.

### Быстрый старт

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import (
    Topology, DataCache,
    Attenuation, AttenuationCatalog,
)

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()
topo = Topology(client, cache=cache)

topo.build_from_customer(68168)
linear = topo.topology_from_commutation("customer", 68168)
cg = linear.cgraphs[0]

cat = AttenuationCatalog.with_defaults()
# или: AttenuationCatalog.from_json("my_attenuation.json")

att = Attenuation(cg, catalog=cat, wavelength=1550, cache=cache, client=client)

report = att.along_linear()                 # по линейной цепочке
# report = att.olt_to_customer(68168)       # shortest path OLT→абонент
# report = att.customer_to_olt(68168)       # upstream, те же dB

print(report.total_db)
print(report.to_table())
print(report.by_kind())   # {'fiber': …, 'splitter': …, 'splice': …}
```

### Каталог профилей

```python
from simpleworkernet.utils.topology import AttenuationCatalog

cat = AttenuationCatalog.with_defaults()

# кабель по id типа из WorkerNet
cat.set_cable(12, name="ОКЛ-…", db_per_km={1310: 0.36, 1550: 0.21})

# сплиттер 5/95 по ключу ratio
cat.set_splitter_by_ratio("1x2_5/95", ports={1: 13.7, 2: 0.8}, wavelength_nm=1550)

# конкретный экземпляр в топологии
cat.set_splitter_instance(35196, ports={1: 13.5, 2: 0.9})

# по inventory catalog_id
cat.set_splitter_by_catalog(1042, ports={1: 13.7, 2: 0.8}, ratio="5/95")

# принудительно
cat.force_fiber(23682, 0.40)                 # dB/km
cat.force_splitter_port(35196, port=2, db=0.7)
cat.force_object("cross", "uuid-…", 0.15)
cat.force_edge(connect_id=12345, db=0.5)

cat.save("my_attenuation.json")
cat2 = AttenuationCatalog.from_json("my_attenuation.json")
```

**Приоритет (сильный → слабый):**

1. `force_*`
2. профиль экземпляра / catalog_id / ratio
3. defaults (`defaults.json`: G.652, типовые 1×2 5/95, 50/50, 1×8, …)

Для неизвестного сплиттера — оценка `10·log10(N) + excess` (`source="estimated"`).

### Длина кабеля

Цепочка источников:

```text
opticalen2 (по волокну)
  → opticalen (по кабелю)
  → сумма path (GeoPoint) × geo_slack_k
  → Fiber.get_geo_length (через DataCache)
```

| Источник | `length_source` |
|----------|-----------------|
| `opticalen2` | `opticalen2` |
| `opticalen` | `opticalen` |
| гео-маршрут | `geo` |
| API geo length | `geo_api` |
| нет данных | `none` (dB волокна = 0, в `missing`) |

`geo_slack_k` (по умолчанию `1.03`) — в `defaults` каталога.

### Что учитывается на пути

| Элемент CGraph | kind | Как считается |
|----------------|------|----------------|
| Кабель (internal side1↔side2) | `fiber` | α(λ)·L_км |
| Сплиттер (internal IN↔OUT) | `splitter` | dB **out-порта** (side=2) |
| Кросс (internal side1↔side2) | `adapter` | default / тип адаптера |
| Внешний стык с волокном | `splice` | `splice_db` |
| Прочий внешний стык | `connector` | `connector_db` |
| `force_edge` | `force` | фиксированное dB |

**Сплиттер (как в handlers):** side **1 = IN**, side **2 = OUT**; internal — полный бипартный граф портов. Затухание берётся с OUT-порта и **не зависит от направления** обхода.

**CWDM:** на пути не моделируется (линейный обход тоже запрещает CWDM).

### Удобные методы Attenuation

| Метод | Смысл |
|-------|--------|
| `path(src, dst)` | shortest path между вершинами / Interface / `"olt:1"` |
| `along(vpath)` | явный список индексов вершин |
| `along_linear()` | обход линейного CGraph (после `topology_from_commutation`) |
| `along_linear(reverse=True)` | client → OLT |
| `olt_to_customer(id)` | OLT → абонент, downstream |
| `customer_to_olt(id)` | upstream, те же сегменты в обратном порядке |
| `olt_to_splitter_out(id, port)` | до OUT-порта сплиттера |
| `olt_to_splitter_in(id)` | до IN |
| `olt_to_cross(uuid, port=…)` | до кросса |
| `cross_to_customer(uuid, cid)` | кросс → абонент |
| `first_in_node(node_id)` | от OLT (или `from_ref`) до первого iface в узле |
| `from_cross_to_node(uuid, node_id)` | кросс → первая коммутация в сооружении |
| `between(type, id, to_type=…, to_id=…)` | произвольная пара |
| `budget_summary()` | OLT → каждый абонент в графе |
| `worst_customer()` | максимальный total_db |
| `path_db(…)` | только число dB |
| `describe_interface(ref)` | attrs вершины |

### PathReport

```python
report.total_db
report.length_m          # сумма длин fiber-сегментов
report.fiber_db
report.splitter_db
report.passive_db        # splice + adapter + connector
report.by_kind()
report.segments          # List[AttenuationSegment]
report.warnings
report.missing           # нет длины / estimated splitter
report.to_table()        # текстовая таблица
report.to_dict()         # JSON-совместимый dict
```

Пример таблицы:

```text
Path: olt:1 s1p2 → customer:68168 s1p0  [downstream]  λ=1550 nm
Total: 18.420 dB  (fiber=2.100, splitter=15.700, passive=0.620)  L=9500.0 m
------------------------------------------------------------------------
  # kind              dB      L,m  description
  1 fiber          2.100   9500.0  fiber:23682 L=9500.0m α=0.220 dB/km (opticalen2)
  2 splice         0.050        -  splice at fiber joint
  3 splitter      13.700        -  splitter:10 out port=1 side=2 (1x2) [downstream]
  …
```

### Шаблон JSON из live WorkerNet

```python
from simpleworkernet.utils.topology.attenuation.template import generate_template

cat = generate_template(
    client,
    cache=cache,
    path="attenuation_template.json",
    fill_defaults=False,   # True — подставить G.652 в пустые db_per_km
)
print(cat.unset_profiles())  # что ещё нужно заполнить вручную
```

Шаблон заполняет:

- `cables` из `Fiber.catalog_cables_get` (слоты `db_per_km`: null);
- `splitters.by_catalog_id` / `by_topology` из `Splitter.get` + inventory (слоты `ports`: {}).

Пользователь дописывает dB и сохраняет файл для повторного `from_json`.

Фрагмент структуры:

```json
{
  "wavelengths_nm": [1310, 1490, 1550],
  "defaults": {
    "fiber_db_per_km": {"1310": 0.35, "1550": 0.22},
    "splice_db": 0.05,
    "connector_db": 0.3,
    "adapter_db": 0.2,
    "geo_slack_k": 1.03,
    "splitter_excess_db": 0.5
  },
  "cables": {
    "12": {"name": "…", "db_per_km": {"1550": 0.21}}
  },
  "splitters": {
    "by_catalog_id": {},
    "by_ratio": {
      "1x2_5/95": {"ports": {"1": 13.7, "2": 0.8}, "wavelength_nm": 1550}
    },
    "by_topology": {}
  },
  "cross_adapters": {"default": 0.2},
  "force": {"fibers": {}, "splitters": {}, "objects": {}, "edges": {}}
}
```

### Полный сценарий: бюджет абонента

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import (
    Topology, DataCache, Attenuation, AttenuationCatalog,
)
from simpleworkernet.utils.topology.attenuation.template import generate_template

client = WorkerNetClient("my.workernet.ru", "key")
cache = DataCache()

# один раз: выгрузить шаблон и заполнить ports / db_per_km
# generate_template(client, cache=cache, path="att.json")

cat = AttenuationCatalog.from_json("att.json")  # или with_defaults()

topo = Topology(client, cache=cache)
topo.build_from_node(23779)

for cid in topo.get_customers()[:20]:
    try:
        lin = topo.topology_from_commutation("customer", cid)
    except ValueError:
        continue
    att = Attenuation(
        lin.cgraphs[0], catalog=cat, wavelength=1550,
        cache=cache, client=client,
    )
    r = att.along_linear()
    print(f"customer {cid}: {r.total_db:.2f} dB  L={r.length_m:.0f} m")
    if r.missing:
        print("  missing:", r.missing)

worst = att.worst_customer()  # на полном графе, не на linear
```

### Связь с длиной волны

`Attenuation(..., wavelength=1310|1490|1550)` выбирает строку из `db_per_km` и из профилей сплиттера (если задан `wavelength_nm`). При отсутствии точного ключа берётся **ближайшая** λ из таблицы.

---

## Тесты

Тесты лежат в `tests/`. Настройка pytest — в `pyproject.toml` (`[tool.pytest.ini_options]`).

### Зависимости

```bash
pip install -r requirements-dev.txt
pip install python-igraph
pip install pyproj                 # опционально
```

### Структура

| Путь | Тип | Сеть |
|------|-----|------|
| `tests/test_*.py` | unit: SmartData, primitives, operators, exceptions, coordinates | нет |
| `tests/topology/` | unit: CGraph, FNGraph, merge, linear, handlers, DataCache, **attenuation** | нет |
| `tests/integration/` | live: smoke API, topology | **да** |

Маркер `@pytest.mark.integration` — тесты против реального WorkerNet. Без credentials они **skip**, а не падают.

### Unit (без API)

```bash
pytest tests/ -m "not integration" -v
pytest tests/topology/ -v
pytest tests/topology/test_attenuation.py tests/topology/test_attenuation_splitter.py -v
pytest tests/ --ignore=tests/topology --ignore=tests/integration -v
pytest tests/ -v
```

### Integration (реальный API)

Учётные данные: **CLI > переменные окружения**.

| CLI | Env | Описание |
|-----|-----|----------|
| `--wn-host` | `WORKERNET_HOST` | хост API |
| `--wn-apikey` | `WORKERNET_APIKEY` | ключ API |
| `--wn-protocol` | `WORKERNET_PROTOCOL` | `http` \| `https` (по умолчанию `https`) |
| `--wn-port` | `WORKERNET_PORT` | порт (по умолчанию `443`) |
| `--nodeid` | `WORKERNET_TEST_NODE_ID` | ID узла для `build_from_node` |
| `--customerid` | `WORKERNET_TEST_CUSTOMER_ID` | ID абонента для `build_from_customer` |

```bash
pytest tests/ -v \
  --wn-host=my.workernet.ru --wn-apikey=SECRET \
  --nodeid=23779 --customerid=68168

pytest tests/integration/ -v \
  --wn-host=my.workernet.ru --wn-apikey=SECRET \
  --nodeid=23779 --customerid=68168

export WORKERNET_HOST=my.workernet.ru
export WORKERNET_APIKEY=SECRET
export WORKERNET_TEST_NODE_ID=23779
export WORKERNET_TEST_CUSTOMER_ID=68168
pytest tests/ -v
```

Фикстуры (session-scoped):

| Фикстура | Назначение |
|----------|------------|
| `live_client` | `WorkerNetClient` |
| `node_id` | из `--nodeid` / env |
| `customer_id` | из `--customerid` / env |
| `wn_credentials` | dict host/apikey/protocol/port |

Поведение skip:

- нет host/apikey → все integration skip
- нет `--nodeid` → skip `test_topology_build_from_node_*`
- нет `--customerid` → skip `test_topology_build_from_customer_*`

Ключ API **не** коммитьте и не пишите в `pytest.ini`.

### Полезные команды

```bash
pytest tests/ -m "not integration" -q
pytest tests/ -k "smartdata or topology or attenuation" -v
pytest tests/ --cov=simpleworkernet
pytest tests/test_coordinates.py -v
```

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
