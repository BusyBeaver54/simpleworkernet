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

---

## Кэширование

Кэш **имён полей** SmartData (не путать с `topology.DataCache`).

```python
from simpleworkernet import SmartData, cache

SmartData.save_cache(force=True)
stats = SmartData.get_cache_stats()
cache.ensure_saved()
```

---

## Очистка данных

```bash
cleanup-simpleworkernet --force
cleanup-simpleworkernet --logs-only
cleanup-simpleworkernet --cache-only
```

```python
from simpleworkernet import cleanup
cleanup(force=True, mode="cache")  # logs | cache | config
```

---

## Графика (SVG/PNG)

Модуль `simpleworkernet.utils.graphics` — SVG из API → PNG.

```python
from simpleworkernet.utils.graphics import SVGHandler, svg_to_png

svg = SVGHandler(client.Node.get_scheme(id=123))
svg.save("scheme.svg")
svg.to_png("scheme.png", method="auto")
```

---

## Координаты

```python
from simpleworkernet.utils.coordinates import geo_to_xy, geo_to_xyz, xy_to_geo
```

---

## Графовая топология (Topology)

Пакет `simpleworkernet.utils.topology` — CGraph + FNGraph.

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | интерфейсы (объект + side + port) | коммутации |
| **FNGraph** | сооружения (`node_id`) | кабели (`fiber_id`) |

```python
from simpleworkernet.utils.topology import Topology, DataCache

topo = Topology(client, cache=DataCache())
topo.build_from_node(23779)
topo.build_from_customer(68168)
linear = topo.topology_from_commutation("customer", 68168)
topo.save_to_file("my_topo.pkl")
```

**Зависимость:** `pip install python-igraph`

---

## Тесты

Тесты в `tests/`. Pytest: `[tool.pytest.ini_options]` в `pyproject.toml`.

### Структура

| Путь | Тип | Сеть |
|------|-----|------|
| `tests/test_*.py` | unit: SmartData, primitives, operators, … | нет |
| `tests/topology/` | unit: CGraph, FNGraph, merge, linear, … | нет |
| `tests/integration/` | live: smoke API, topology | **да** |

### Unit (без API)

```bash
pytest tests/ -m "not integration" -v
pytest tests/topology/ -v
```

Без credentials integration **skip** (не падают):

```bash
pytest tests/ -v
```

### Integration (реальный API)

Приоритет: **CLI > env**.

| CLI | Env | Описание |
|-----|-----|----------|
| `--wn-host` | `WORKERNET_HOST` | хост API |
| `--wn-apikey` | `WORKERNET_APIKEY` | ключ API |
| `--wn-protocol` | `WORKERNET_PROTOCOL` | `http` \| `https` (default `https`) |
| `--wn-port` | `WORKERNET_PORT` | порт (default `443`) |
| `--nodeid` | `WORKERNET_TEST_NODE_ID` | ID узла (`build_from_node`) |
| `--customerid` | `WORKERNET_TEST_CUSTOMER_ID` | ID абонента (`build_from_customer`) |

```bash
# все тесты: unit + smoke + topology live
pytest tests/ -v \
  --wn-host=my.workernet.ru --wn-apikey=SECRET \
  --nodeid=23779 --customerid=68168

# только integration
pytest tests/integration/ -v \
  --wn-host=my.workernet.ru --wn-apikey=SECRET \
  --nodeid=23779 --customerid=68168

# через env
export WORKERNET_HOST=my.workernet.ru
export WORKERNET_APIKEY=SECRET
export WORKERNET_TEST_NODE_ID=23779
export WORKERNET_TEST_CUSTOMER_ID=68168
pytest tests/ -v
```

Фикстуры session-scoped: `live_client`, `node_id`, `customer_id`.

- нет host/apikey → skip всех integration
- нет `--nodeid` → skip `test_topology_build_from_node_*`
- нет `--customerid` → skip `test_topology_build_from_customer_*`

Ключ **не** коммитить и не писать в `pytest.ini`.

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
