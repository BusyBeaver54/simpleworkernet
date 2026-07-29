# **SimpleWorkerNet** 

Python клиент для REST API системы WorkerNet с интеллектуальной системой трансформации и типизации сложных JSON структур

[![Tag](https://img.shields.io/github/v/tag/busy4beaver/simpleworkernet?color=00c2e8)](https://pypi.org/project/simpleworkernet/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/simpleworkernet.svg?logo=python&logoColor=FFE873)](https://www.python.org/downloads/)
[![Licence](https://img.shields.io/github/license/busy4beaver/simpleworkernet.svg)](LICENSE)  

---

Содержание

  - [Особенности](#особенности)
    - [SmartData Framework](#smartdata-framework)
    - [BaseModel Engine](#basemodel-engine)
    - [Умный клиент API](#умный-клиент-api)
    - [Продвинутое логирование](#продвинутое-логирование)
    - [Умное кэширование](#умное-кэширование)
    - [Интеллектуальная очистка](#интеллектуальная-очистка)
  - [Установка](#установка)
  - [Быстрый старт](#быстрый-старт)
    - [Минимальный пример](#минимальный-пример)
    - [Использование с контекстным менеджером](#использование-с-контекстным-менеджером)
    - [Поиск и фильтрация](#поиск-и-фильтрация)
  - [Конфигурация](#конфигурация)
    - [Просмотр текущей конфигурации](#просмотр-текущей-конфигурации)
    - [Раздельные уровни логирования](#раздельные-уровни-логирования)
    - [Настройка кэширования](#настройка-кэширования)
    - [Пример настройки для высокой производительности](#пример-настройки-для-высокой-производительности)
    - [Настройка клиента API](#настройка-клиента-api)
    - [Настройки SmartData](#настройки-smartdata)
    - [Массовое обновление](#массовое-обновление)
    - [Сохранение и сброс](#сохранение-и-сброс)
    - [Пример полной настройки](#пример-полной-настройки)
  - [Основные компоненты](#основные-компоненты)
    - [WorkerNetClient](#workernetclient)
    - [BaseModel и smart\_model](#basemodel-и-smart_model)
    - [SmartData Framework](#smartdata-framework-1)
    - [Метаданные и CollapsedField](#метаданные-и-collapsedfield)
    - [Примитивные типы](#примитивные-типы)
  - [Логирование](#логирование)
    - [Настройка логирования](#настройка-логирования)
    - [Работа с сессионными логами](#работа-с-сессионными-логами)
    - [Структура файлов логов](#структура-файлов-логов)
  - [Кэширование](#кэширование)
    - [Управление кэшем через SmartData](#управление-кэшем-через-smartdata)
    - [Предзагрузка кэша из моделей](#предзагрузка-кэша-из-моделей)
    - [Умное сохранение](#умное-сохранение)
    - [Получение статистики кэша](#получение-статистики-кэша)
  - [Очистка данных](#очистка-данных)
    - [Консольная команда](#консольная-команда)
    - [Программная очистка](#программная-очистка)
  - [Примеры использования](#примеры-использования)
    - [Базовые операции с API](#базовые-операции-с-api)
    - [Фильтрация данных](#фильтрация-данных)
    - [Глубокий поиск по структуре](#глубокий-поиск-по-структуре)
    - [Создание пользовательских моделей](#создание-пользовательских-моделей)
    - [Получение ссылок на объекты](#получение-ссылок-на-объекты)
    - [Препроцессор данных API](#препроцессор-данных-api)
      - [Использование препроцессора](#использование-препроцессора)
      - [Как это работает](#как-это-работает)
      - [Примеры препроцессоров](#примеры-препроцессоров)
      - [Универсальный препроцессор для дефисов](#универсальный-препроцессор-для-дефисов)
      - [Препроцессор с нормализацией значений](#препроцессор-с-нормализацией-значений)
    - [Агрегация и статистика](#агрегация-и-статистика)
    - [Сериализация](#сериализация)
    - [Работа с графикой (SVG/PNG)](#работа-с-графикой-svgpng)
      - [Установка дополнительных зависимостей](#установка-дополнительных-зависимостей)
      - [Базовое использование](#базовое-использование)
      - [Быстрые функции](#быстрые-функции)
      - [Автоматическое сохранение](#автоматическое-сохранение)
      - [Отображение в Jupyter](#отображение-в-jupyter)
      - [Разные методы конвертации](#разные-методы-конвертации)
      - [Обработка ошибок](#обработка-ошибок)
      - [Пример полного рабочего процесса](#пример-полного-рабочего-процесса)
      - [Флаги доступности методов](#флаги-доступности-методов)
  - [Графовая топология (Topology)](#графовая-топология-topology)
    - [Архитектура пакета](#архитектура-пакета)
    - [Зависимости](#зависимости-topology)
    - [Основные возможности](#основные-возможности)
    - [Быстрый старт](#быстрый-старт-1)
    - [DataCache](#datacache)
    - [Методы построения](#методы-построения)
    - [Фильтрация при построении](#фильтрация-при-построении)
    - [Получение данных из графа](#получение-данных-из-графа)
    - [Построение линейного графа (topology\_from\_commutation)](#построение-линейного-графа-topology_from_commutation)
    - [Сохранение и загрузка](#сохранение-и-загрузка-топологии)
    - [Структура хранения графов](#структура-хранения-графов)
    - [Пример полного рабочего процесса](#пример-полного-рабочего-процесса-1)
    - [Особенности реализации](#особенности-реализации)
  - [☕ Поддержать проект](#-поддержать-проект)

---

## <a name="features"></a>Особенности

### SmartData Framework
Интеллектуальная обработка API-ответов с автоматическим приведением типов, сохранением метаданных и глубоким поиском по любым уровням вложенности.

### BaseModel Engine
Мощная система рекурсивного кастинга типов с поддержкой Union, Optional, List и вложенных моделей.

### Умный клиент API
- Автоматическое управление сессиями
- Интеллектуальный выбор метода (GET/POST) при превышении лимита URL
- Автоматические повторы при таймаутах

### Продвинутое логирование
- **Раздельные уровни** для консоли и файла
- Сессионные логи с временными метками
- Автоматическая ротация файлов
- Мгновенное применение настроек без перезапуска

### Умное кэширование
- Двухуровневое кэширование полей моделей
- Автоматическая очистка при достижении лимита (LRU, LFU, FIFO)
- **Сохранение только при реальных изменениях** (флаг dirty)
- Предзагрузка из моделей

### Интеллектуальная очистка
- Безопасное удаление данных приложения
- Режим `--dry-run` для просмотра что будет удалено
- Автоматическое отключение кэширования перед очисткой

## <a name="installation"></a>Установка

```bash
pip install simpleworkernet
```
```bash
pip install git+https://github.com/busy4beaver/simpleworkernet.git
```

Для модуля топологии дополнительно:

```bash
pip install python-igraph
```

## <a name="quick-start"></a>Быстрый старт

### Минимальный пример
```python
from simpleworkernet import WorkerNetClient

client = WorkerNetClient(
    host="my.workernet.ru",
    apikey="your-secret-api-key"
)

cables = client.Fiber.catalog_cables_get()
print(f"Найдено кабелей в каталоге: {len(cables)}")
```

### Использование с контекстным менеджером

Отправляет запросы внутри одной сессии requests.Session
```python
from simpleworkernet import WorkerNetClient

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    customers = client.Module.get_user_list()
    addresses = client.Address.get_city()
    
    print(f"Абонентов: {len(customers)}")
    print(f"Городов: {len(addresses)}")
```

### Поиск и фильтрация
```python
from simpleworkernet import WorkerNetClient, Where, Operator

client = WorkerNetClient("my.workernet.ru", "your-api-key")
customers = client.Module.get_user_list()

conditions = [
    Where('state_id', 2),
    Where('balance', 1000, Operator.GT),
    Where('full_name', 'Иван', Operator.LIKE)
]

filtered = customers.filter(*conditions, join='AND')
print(f"Найдено: {filtered.count()}")

active_customers = customers.where('state_id', 2)
```

## <a name="configuration"></a>Конфигурация

ConfigManager — центральный элемент управления всеми настройками библиотеки. Все изменения применяются немедленно к текущей сессии. Для сохранения настроек между запусками используйте метод save().

### Просмотр текущей конфигурации
```python
from simpleworkernet import config_manager

config_manager.show_config()
config_str = config_manager.show_config(return_string=True)
print(config_str)
```

### Раздельные уровни логирования
```python
from simpleworkernet import config_manager

config_manager.console_level = 'INFO'
config_manager.file_level = 'DEBUG'
config_manager.console_output = True
config_manager.log_to_file = True
config_manager.max_log_files = 20
```

### Настройка кэширования

SmartDataCache кэширует результаты проверок имён полей. Поддерживаются стратегии LFU, LRU и FIFO.
```python
from simpleworkernet import config_manager

config_manager.cache_enabled = True
config_manager.cache_max_size = 100000
config_manager.cache_evict_strategy = 'lfu'   # 'lfu' | 'lru' | 'fifo'
config_manager.cache_evict_threshold = 0.9
config_manager.cache_evict_percent = 0.2
config_manager.cache_auto_save = True
```

### Пример настройки для высокой производительности
```python
config_manager.cache_enabled = True
config_manager.cache_max_size = 300000
config_manager.cache_evict_strategy = 'lfu'
config_manager.cache_evict_threshold = 0.95
config_manager.cache_evict_percent = 0.3
config_manager.cache_auto_save = True
```

### Настройка клиента API
```python
config_manager.default_timeout = 60
config_manager.max_retries = 3
config_manager.user_agent = "MyApp/1.0"
```

### Настройки SmartData
```python
config_manager.smartdata_max_depth = 200
```

### Массовое обновление
```python
config_manager.update(
    console_level='INFO',
    file_level='DEBUG',
    console_output=True,
    log_to_file=True,
    cache_enabled=True,
    cache_max_size=100000,
    cache_evict_strategy='lru',
    cache_evict_threshold=0.9,
    cache_evict_percent=0.2,
    default_timeout=60,
    save=True
)
```

### Сохранение и сброс
```python
config_manager.save()
config_manager.reset(save=True)
```

### Пример полной настройки
```python
from simpleworkernet import config_manager

config_manager.console_level = 'INFO'
config_manager.file_level = 'DEBUG'
config_manager.console_output = True
config_manager.log_to_file = True
config_manager.max_log_files = 30

config_manager.cache_enabled = True
config_manager.cache_max_size = 200000
config_manager.cache_evict_strategy = 'lfu'
config_manager.cache_evict_threshold = 0.95
config_manager.cache_evict_percent = 0.3
config_manager.cache_auto_save = True

config_manager.default_timeout = 45
config_manager.max_retries = 3
config_manager.save()
```

## <a name="core-components"></a>Основные компоненты

### <a name="workernetclient"></a>WorkerNetClient

```python
from simpleworkernet import WorkerNetClient

client = WorkerNetClient("my.workernet.ru", "your-api-key")

customers = client.Customer.get_data()
addresses = client.Address.get_city()
devices = client.Device.get_data(object_type='switch')
fiber = client.Fiber.get_list()
```

### <a name="basemodel-and-smartmodel"></a>BaseModel и smart_model

```python
from simpleworkernet import smart_model, BaseModel, CollapsedField, vStr, GeoPoint, vPhoneNumber
from simpleworkernet.smartdata.metadata import SegmentType
from typing import List, Optional

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

### <a name="smartdata-framework"></a>SmartData Framework

```python
from simpleworkernet import SmartData, Where, Operator

customers = client.Module.get_user_list()

result = (customers
    .where('balance', 0, Operator.GT)
    .where('state_id', 2)
    .sort(key=lambda x: x.balance, reverse=True)
    .limit(10)
    .map(lambda x: x.full_name))
```

### <a name="metadata-and-collapsedfield"></a>Метаданные и CollapsedField

```python
from simpleworkernet import SmartData, CollapsedField
from simpleworkernet.smartdata.metadata import SegmentType

customers = client.Customer.get_data(customer_id='1,2')

for customer in customers:
    if customer.meta:
        print(f"Путь: {customer.meta.get_path_string()}")
        print(f"Схлопнутые ключи: {customer.get_collapsed_keys()}")
```

### <a name="primitive-types"></a>Примитивные типы

```python
from simpleworkernet import vStr, vFlag, GeoPoint, vPhoneNumber, vMoney, vPercent

text = vStr("Hello%20World&amp;Co")
point = GeoPoint(55.75, 37.62)
phone = vPhoneNumber("+7 (123) 456-78-90")
money = vMoney(100.50, "RUB")
p = vPercent(15.5)
```

## <a name="logging"></a>Логирование

### Настройка логирования
```python
from simpleworkernet import config_manager, log

config_manager.console_level = 'INFO'
config_manager.file_level = 'DEBUG'
config_manager.console_output = True
config_manager.log_to_file = True
```

### Работа с сессионными логами
```python
from simpleworkernet import log

session_id = log.get_session_id()
log_file = log.get_log_file()
new_session = log.new_session()
```

### Структура файлов логов
```text
~/.local/share/simpleworkernet/scriptname_hash/logs/
├── scriptname_20250305_091233.log
└── ...
```

## <a name="caching"></a>Кэширование

### Управление кэшем через SmartData
```python
from simpleworkernet import SmartData

SmartData.save_cache(force=True)
stats = SmartData.get_cache_stats()
print(f"Попаданий: {stats['hits']} ({stats['hit_rate']:.1f}%)")
```

### Предзагрузка кэша из моделей
```python
from simpleworkernet import SmartData
from simpleworkernet.models.categories.customer import Customer

SmartData.preload_from_models(
    Customer.Get_data,
    Customer.Get_data.Address,
    recursive=True
)
```

## <a name="cleanup"></a>Очистка данных

### Консольная команда
```bash
cleanup-simpleworkernet
cleanup-simpleworkernet --force
cleanup-simpleworkernet --dry-run
cleanup-simpleworkernet --list
cleanup-simpleworkernet --app myapp_abc123
cleanup-simpleworkernet --logs-only
cleanup-simpleworkernet --cache-only
cleanup-simpleworkernet --config-only
```

### Программная очистка
```python
from simpleworkernet import cleanup

cleanup()
cleanup(force=True)
cleanup(force=True, mode='cache')
```

## <a name="examples"></a>Примеры использования

### Базовые операции с API
```python
from simpleworkernet import WorkerNetClient, config_manager

config_manager.console_level = "DEBUG"
config_manager.save()

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    customers = client.Module.get_user_list()
    customer = client.Customer.get_data(customer_id=123)
    cables = client.Fiber.catalog_cables_get()
```

### Фильтрация данных
```python
from simpleworkernet import Where, Operator

customers = client.Customer.get_data()
active = customers.where('state_id', 2)
filtered = customers.filter(
    Where('state_id', 2),
    Where('balance', 1000, Operator.GT),
    join='AND'
)
```

### Работа с графикой (SVG/PNG)

```python
from simpleworkernet.utils.graphics import SVGHandler, svg_to_png
from simpleworkernet import WorkerNetClient

client = WorkerNetClient("host", "apikey")
svg_data = client.Node.get_scheme(id=123)
svg = SVGHandler(svg_data)

if svg.is_svg():
    svg.save("scheme.svg")
    svg.to_png("scheme.png", max_size=(1920, 1080))
```

Дополнительные зависимости для конвертации: `Wand`, `cairosvg`, `weasyprint` или Inkscape.

---

## <a name="topology"></a>Графовая топология (Topology)

Модуль `simpleworkernet.utils.topology` — пакет для построения и анализа топологии телеком-сети.

Два типа графов:

| Граф | Вершины | Рёбра | Хранение |
|------|---------|-------|----------|
| **CGraph** | интерфейсы (порт + сторона объекта) | коммутации | список связных компонент |
| **FNGraph** | сооружения (`node_id`) | кабели (`fiber_id`) | один связный граф |

### Архитектура пакета

```text
simpleworkernet/utils/topology/
├── __init__.py          # публичный API
├── constants.py         # TYPE_*, DEVICE/SIDE/TERMINAL_TYPES
├── keys.py              # ObjKey, Interface
├── models.py            # CGraphVertex/Edge, FNGraphVertex/Edge
├── cache.py             # DataCache (инстанс, не синглтон)
├── context.py           # BuildContext для BFS
├── merge.py             # merge_cgraphs / merge_fngraphs
├── linear.py            # LinearPathFinder
├── topology.py          # оркестратор Topology
├── graphs/
│   ├── base.py          # composition над igraph
│   ├── cgraph.py
│   └── fngraph.py
└── builders/
    ├── base.py          # GraphBuilder
    └── handlers.py      # strategy по типам объектов
```

Импорт:

```python
from simpleworkernet.utils.topology import (
    Topology, CGraph, FNGraph, DataCache,
    ObjKey, Interface,
    merge_cgraphs, merge_fngraphs,
)
# или короче:
from simpleworkernet.utils import Topology, CGraph, FNGraph
```

> `simpleworkernet.utils.graph` оставлен для совместимости и выдаёт `DeprecationWarning` — используйте `utils.topology`.

### <a name="зависимости-topology"></a>Зависимости

```bash
pip install python-igraph
```

### Основные возможности

- Построение от OLT, switch, кросса, сплиттера, CWDM, кабеля, волокна, абонента, узла
- Фильтры: `included_fibers`, `excluded_fibers`, `excluded_nodes`
- Автоматическое объединение связных компонент (`merge_cgraphs` / `merge_fngraphs`)
- Линейная цепочка до корня: `topology_from_commutation`
- Списки объектов и загрузка по ID через `DataCache`
- Сохранение / загрузка топологии на диск (`save_to_file` / `load_from_file`)
- Handlers по типам объектов (легко расширять новыми типами)

### Быстрый старт

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import Topology

client = WorkerNetClient("my.workernet.ru", "your-api-key")
topo = Topology(client)

topo.build_from_cross('98d9d368-43e9-4513-9ec7-4e076eea2bda', port=7)

customers = topo.get_customers()
print(f"Абонентов: {len(customers)}")

linear = topo.topology_from_commutation('customer', customers[0])
print(f"Линейный граф: {linear.cgraphs[0].vcount()} вершин")
```

### DataCache

`DataCache` — **экземпляр**, не глобальный синглтон. Можно шарить между несколькими `Topology`:

```python
from simpleworkernet.utils.topology import Topology, DataCache

cache = DataCache()
topo1 = Topology(client, cache=cache)
topo2 = Topology(client, cache=cache)  # тот же кэш объектов/коммутаций

# сброс
cache.clear()
```

Все запросы объектов и коммутаций к API проходят через кэш.

### Методы построения

**build_from_device** — OLT, switch, ONU:

```python
topo.build_from_device('olt', 12345)           # все PON-порты
topo.build_from_device('olt', 12345, port=1)
topo.build_from_device('switch', 67890, port=5)
topo.build_from_device(
    'olt', 12345,
    included_fibers=[23682, 23683],
    excluded_nodes=[23780, 23781]
)
```

**build_from_customer**:

```python
topo.build_from_customer(68168)
```

**build_from_cross**:

```python
topo.build_from_cross('98d9d368-...', port=7)
topo.build_from_cross('98d9d368-...', port=7, side=1)
topo.build_from_cross('98d9d368-...')  # все порты → отдельные CGraph
```

**build_from_splitter / build_from_cwdm**:

```python
topo.build_from_splitter(35196)                    # все интерфейсы, merge
topo.build_from_splitter(35196, port=1, side=1)
topo.build_from_cwdm(12345, port=1, side=2)
```

**build_from_fiber / build_from_cable**:

```python
topo.build_from_fiber(23682, port=1, side=1)  # port = порядковый № волокна
topo.build_from_cable(23682)                   # все волокна кабеля
```

**build_from_node** — FNGraph от узла + CGraph по всем объектам в узлах:

```python
topo.build_from_node(23779)
topo.build_from_node(23779, excluded_nodes=[23780, 23781])
```

### Фильтрация при построении

| Параметр | Действие |
|----------|----------|
| `included_fibers` | Разрешённые кабели **только на стартовом узле** |
| `excluded_fibers` | Запрещённые кабели (всегда) |
| `excluded_nodes` | Запрещённые узлы (всегда) |

```python
topo.build_from_cross(
    '98d9d368-...',
    port=7,
    excluded_fibers=[23685]
)
```

### Получение данных из графа

```python
customers = topo.get_customers()
nodes = topo.get_nodes()
cables = topo.get_cables()
fibers = topo.get_fibers()
devices = topo.get_devices()
splitters = topo.get_splitters()
cwdms = topo.get_cwdms()
crosses = topo.get_crosses()

customer = topo.customer(68168)
node = topo.node(23779)
cable = topo.cable(23682)
device = topo.device(12345)
splitter = topo.splitter(35196)
cwdm = topo.cwdm(12345)
cross = topo.cross('98d9d368-...')

# finish-данные конечных вершин
finish_list = topo.get_finish_by_node(23779)
finish_one = topo.get_finish_by_object('customer', 68168)
```

### Построение линейного графа (topology_from_commutation)

Строит цепочку от `last`-объекта к корню (OLT/switch) или к явно указанному `first_object`. Возвращает **новый** `Topology`.

```python
linear = topo.topology_from_commutation('customer', customer_id)

linear = topo.topology_from_commutation(
    'customer', customer_id,
    first_object_type='olt',
    first_object_id=12345
)

linear = topo.topology_from_commutation(
    'splitter', 35196,
    port=1, side=2
)
```

**Правила:**

- Сплиттер — порт обязателен (движение от выхода ко входу)
- Кросс / кабель — порт и сторона обязательны
- Абонент с несколькими коммутациями — нужен `first_object`
- Без `first_object` ищется OLT или switch; при ветвлении — shortest path
- CWDM на пути линейного графа не поддерживается

### Сохранение и загрузка топологии

```python
topo.save_to_file("topology.pkl")

loaded = Topology.load_from_file("topology.pkl")
print(loaded)  # Topology(CGraphs: N, FNGraph: ...)
```

Сохраняются CGraph’и, FNGraph, DataCache и параметры клиента.

### Структура хранения графов

```python
topo.cgraphs   # List[CGraph] — связные графы коммутаций
topo.fngraph   # Optional[FNGraph] — граф сооружений

# удобный доступ
for v in topo.cgraphs[0].get_vertices():
    print(v.obj_type, v.obj_id, v.port, v.side)

for e in topo.cgraphs[0].get_edges():
    print(e.source, e.target, e.connect_id, e.is_internal)
```

Каждый `CGraph` гарантированно связный. Несвязные результаты не добавляются.

### Пример полного рабочего процесса

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import Topology, DataCache

client = WorkerNetClient("my.workernet.ru", "your-api-key")
cache = DataCache()
topo = Topology(client, cache=cache)

# 1. Граф от кросса
topo.build_from_cross('98d9d368-43e9-4513-9ec7-4e076eea2bda', port=7)

# 2. Абоненты
customers = topo.get_customers()
print(f"Абонентов: {len(customers)}")

# 3. Линейная цепочка до корня
linear = topo.topology_from_commutation('customer', customers[0])
print(f"Цепочка: {linear.cgraphs[0].vcount()} вершин, "
      f"{linear.cgraphs[0].ecount()} рёбер")

# 4. Устройства на пути
print(f"Устройств: {linear.get_devices()}")

# 5. Сохранить
topo.save_to_file("my_topo.pkl")
```

### Особенности реализации

- **Composition над igraph** — `CGraph`/`FNGraph` оборачивают `igraph.Graph`, а не наследуют его
- **Handlers** — правила для terminal / cross / fiber / splitter+CWDM в отдельных классах (`builders/handlers.py`)
- **BuildContext** — единый контекст BFS (фильтры, очередь, finish-данные)
- **DataCache** — инстанс; объекты и коммутации кэшируются между построениями
- **Merge** — при пересечении компонент графы объединяются в связный
- **Линейный путь** — external-ребро предпочтительнее internal; при ветвлении — shortest path до `first_object`

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894) 
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
