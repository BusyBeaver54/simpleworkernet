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
    - [Основные возможности](#основные-возможности)
    - [Быстрый старт](#быстрый-старт-1)
    - [Методы построения](#методы-построения)
    - [Фильтрация при построении](#фильтрация-при-построении)
    - [Получение данных из графа](#получение-данных-из-графа)
    - [Построение линейного графа (topology\_from\_commutation)](#построение-линейного-графа-topology_from_commutation)
      - [Правила работы метода:](#правила-работы-метода)
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

## <a name="quick-start"></a>Быстрый старт

### Минимальный пример
```python

from simpleworkernet import WorkerNetClient

# Создаем клиент
client = WorkerNetClient(
    host="my.workernet.ru",
    apikey="your-secret-api-key"
)

# Получаем данные
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

# Получаем данные
customers = client.Module.get_user_list()

# Создаем условия поиска
conditions = [
    Where('state_id', 2),                    # активные абоненты
    Where('balance', 1000, Operator.GT),     # с балансом > 1000
    Where('full_name', 'Иван', Operator.LIKE) # имя содержит 'Иван'
]

# Фильтруем
filtered = customers.filter(*conditions, join='AND')
print(f"Найдено: {filtered.count()}")

# Или через where для простых условий
active_customers = customers.where('state_id', 2)
```

## <a name="configuration"></a>Конфигурация

ConfigManager — центральный элемент управления всеми настройками библиотеки. Все изменения применяются немедленно к текущей сессии. Для сохранения настроек между запусками используйте метод save().

### Просмотр текущей конфигурации
```python

from simpleworkernet import config_manager

# Вывод в лог
config_manager.show_config()

# Получение как строки
config_str = config_manager.show_config(return_string=True)
print(config_str)
```

### Раздельные уровни логирования
```python

from simpleworkernet import config_manager

### Разные уровни для консоли и файла
config_manager.console_level = 'INFO'      # В консоль: INFO и выше
config_manager.file_level = 'DEBUG'        # В файл: DEBUG и выше

# Включение/отключение вывода
config_manager.console_output = True       # Вывод в консоль
config_manager.log_to_file = True          # Запись в файл
config_manager.max_log_files = 20          # Максимальное количество файлов логов
```

### Настройка кэширования

SmartDataCache кэширует результаты проверок имён полей, что значительно ускоряет работу SmartData при обработке больших объёмов данных. Поддерживаются три стратегии очистки: LFU, LRU и FIFO.
```python

from simpleworkernet import config_manager

# Включение/отключение кэша
config_manager.cache_enabled = True

# Максимальный размер кэша (количество записей)
config_manager.cache_max_size = 100000

# Стратегия очистки:
#   'lfu'  – удалять наименее часто используемые (по умолчанию)
#   'lru'  – удалять давно не использовавшиеся
#   'fifo' – удалять самые старые (по времени добавления)
config_manager.cache_evict_strategy = 'lfu'

# Порог заполнения (доля от max_size), при превышении которого запускается очистка.
# По умолчанию 0.9 (очистка при заполнении ≥ 90% от max_size).
config_manager.cache_evict_threshold = 0.9

# Процент записей, удаляемых за одну очистку (от текущего размера).
# По умолчанию 0.2 (удаляется 20% записей).
config_manager.cache_evict_percent = 0.2

# Автосохранение кэша (сохраняет только при реальных изменениях)
config_manager.cache_auto_save = True
```

Как работает очистка кэша

    Кэш заполняется до тех пор, пока общее количество записей не достигнет max_size * evict_threshold (по умолчанию 90% от максимума).

    При добавлении новой записи, если порог превышен, запускается очистка.

    За один раз удаляется evict_percent (по умолчанию 20%) от текущего размера кэша (а не от максимума), чтобы очистка была массовой и редкой.

    Какая именно часть записей удаляется, зависит от выбранной стратегии:

        LFU (Least Frequently Used) – удаляются записи с наименьшей частотой обращений.

        LRU (Least Recently Used) – удаляются записи, к которым дольше всего не обращались.

        FIFO (First In, First Out) – удаляются самые старые записи (по времени добавления).

Рекомендации по настройке для больших данных

    Увеличьте cache_max_size – если вы обрабатываете десятки тысяч уникальных полей, установите размер 200 000–500 000 (при достаточной памяти).

    Повысьте cache_evict_threshold до 0.95 – очистка будет запускаться реже, только при 95% заполнении.

    Увеличьте cache_evict_percent до 0.3–0.4 – за одну очистку будет удаляться больше записей, что снизит общее число очисток.

    Выберите стратегию под свой сценарий:

        Для данных с «горячими» полями, которые часто используются, лучше подходит LFU.

        Для потоковых данных, где важна свежесть, используйте LRU.

        Для простого предсказуемого поведения – FIFO.

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

# Таймауты и повторы
config_manager.default_timeout = 60        # Таймаут запроса в секундах
config_manager.max_retries = 3             # Количество повторов при ошибке
config_manager.user_agent = "MyApp/1.0"    # User-Agent для запросов
```

### Настройки SmartData
```python

# Максимальная глубина обработки вложенных структур
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
    save=True   # сразу сохранить в файл
)
```

### Сохранение и сброс
```python

# Сохранение текущей конфигурации в файл (для использования в следующих запусках)
config_manager.save()

# Сброс на значения по умолчанию (не сохраняется, если save=False)
config_manager.reset(save=True)
```

### Пример полной настройки
```python

from simpleworkernet import config_manager

# ----- Логирование (разные уровни) -----
config_manager.console_level = 'INFO'      # В консоль – только INFO и выше
config_manager.file_level = 'DEBUG'        # В файл – всё, включая DEBUG
config_manager.console_output = True
config_manager.log_to_file = True
config_manager.max_log_files = 30

# ----- Кэш (оптимизация для большого объёма данных) -----
config_manager.cache_enabled = True
config_manager.cache_max_size = 200000          # Увеличенный размер
config_manager.cache_evict_strategy = 'lfu'     # LFU для часто используемых полей
config_manager.cache_evict_threshold = 0.95     # Очистка при заполнении на 95%
config_manager.cache_evict_percent = 0.3        # Удалять 30% записей за раз
config_manager.cache_auto_save = True

# ----- Клиент API -----
config_manager.default_timeout = 45
config_manager.max_retries = 3

# Сохраняем настройки для будущих запусков
config_manager.save()
```

Примечания

    Все изменения применяются немедленно – перезапуск не требуется.

    Для постоянного сохранения настроек вызовите config_manager.save().

    Если вы изменяете настройки кэша во время работы, они будут применены к текущему экземпляру кэша автоматически.

    Кэш сохраняется на диск только при наличии реальных изменений (флаг _dirty), что экономит ресурсы.

    Параметр cache_evict_strategy теперь полностью работоспособен и влияет на поведение очистки кэша.

## <a name="core-components"></a>Основные компоненты

### <a name="workernetclient"></a>WorkerNetClient

Основной класс для взаимодействия с API WorkerNet. Поддерживает все категории API:
```python

from simpleworkernet import WorkerNetClient

client = WorkerNetClient("my.workernet.ru", "your-api-key")

# Доступные категории
customers = client.Customer.get_data()
addresses = client.Address.get_city()
devices = client.Device.get_data(object_type='switch')
fiber = client.Fiber.get_list()
```

### <a name="basemodel-and-smartmodel"></a>BaseModel и smart_model

Базовый класс для всех моделей с автоматическим кастингом типов:
```python

from simpleworkernet import smart_model, BaseModel, CollapsedField, vStr, GeoPoint, vPhoneNumber
from simpleworkernet.smartdata.metadata import SegmentType
from typing import List, Optional

@smart_model
class Contact(BaseModel):
    """Контактная информация"""
    email: Optional[str]
    phone: Optional[vPhoneNumber]
    telegram: Optional[str]

@smart_model
class Address(BaseModel):
    """Модель адреса"""
    id: int
    city: vStr
    street: vStr
    house: str
    apartment: Optional[int]
    coordinates: GeoPoint
    contacts: Optional[Contact]

@smart_model
class Traffic(BaseModel):
    """Трафик абонента"""
    up: int
    down: int
    # Доступ к схлопнутому ключу 'month' из метаданных
    period = CollapsedField(type_filter=SegmentType.FLD)

# Автоматическое создание из словаря
addr = Address(
    id=1,
    city="Москва",
    street="Ленина",
    house="10",
    apartment=42,
    coordinates=[55.75, 37.62],
    contacts={"phone": "+7-999-123-45-67"}
)
```

### <a name="smartdata-framework"></a>SmartData Framework

Контейнер для интеллектуальной обработки JSON-структур с fluent-интерфейсом:
```python

from simpleworkernet import SmartData, Where, Operator

# Из ответа API (автоматически)
customers = client.Module.get_user_list()  # уже SmartData

# Цепочка операций
result = (customers
    .where('balance', 0, Operator.GT)
    .where('state_id', 2)
    .sort(key=lambda x: x.balance, reverse=True)
    .limit(10)
    .map(lambda x: x.full_name))

# Группировка и агрегация
by_state = customers.group_by(lambda x: x.state_id)
for state, group in by_state.items():
    avg_balance = group.avg(lambda x: x.balance)
    print(f"Статус {state}: {group.count()} абонентов, средний баланс {avg_balance}")
```

### <a name="metadata-and-collapsedfield"></a>Метаданные и CollapsedField

Каждый объект хранит метаданные о своем положении в исходной структуре:
```python

from simpleworkernet import SmartData, CollapsedField
from simpleworkernet.smartdata.metadata import SegmentType

# Получение данных от API
customers = client.Customer.get_data(customer_id='1,2')

for customer in customers:
    # Доступ к метаданным
    if customer.meta:
        print(f"Путь к объекту: {customer.meta.get_path_string()}")
        print(f"Схлопнутые ключи: {customer.get_collapsed_keys()}")
    
    # Доступ к схлопнутым полям через CollapsedField
    if customer.tariff:
        print(f"container_name: {customer.tariff.container_name}")  # 'current'
```

### <a name="primitive-types"></a>Примитивные типы

Богатый набор примитивных типов с дополнительной логикой:
```python

from simpleworkernet import vStr, vFlag, GeoPoint, vPhoneNumber, vMoney, vPercent, vINN, vKPP, vSNILS, vOGRN

# Декодирование строк
text = vStr("Hello%20World&amp;Co")  # "Hello World&Co"

# Геокоординаты
point = GeoPoint(55.75, 37.62)
print(point)  # "55.75,37.62"
print(point.distance_to(GeoPoint("55.76,37.63")))  # расстояние в км

# Телефонные номера
phone = vPhoneNumber("+7 (123) 456-78-90")
print(phone.normalized)  # "71234567890"
print(phone.international)  # "+71234567890"

# Денежные суммы
money = vMoney(100.50, "RUB")
money2 = money + 50.25
print(money2)  # "150.75 RUB"

# Проценты
p = vPercent(15.5)
print(p.of(1000))  # 155.0
```

## <a name="logging"></a>Логирование

### Настройка логирования
```python

from simpleworkernet import config_manager, log

# Раздельные уровни для консоли и файла
config_manager.console_level = 'INFO'     # В консоль: INFO и выше
config_manager.file_level = 'DEBUG'       # В файл: DEBUG и выше
config_manager.console_output = True
config_manager.log_to_file = True
config_manager.max_log_files = 20

# Применение происходит автоматически при изменении свойств
```

### Работа с сессионными логами
```python

from simpleworkernet import log

# Информация о текущей сессии
session_id = log.get_session_id()
log_file = log.get_log_file()
print(f"Сессия: {session_id}, лог: {log_file}")

# Начать новую сессию
new_session = log.new_session()
```

### Структура файлов логов
```text

~/.local/share/simpleworkernet/scriptname_hash/logs/
├── scriptname_20250305_091233.log
├── scriptname_20250305_143022.log
└── scriptname_20250305_163502.log
```

## <a name="caching"></a>Кэширование

### Управление кэшем через SmartData
```python

from simpleworkernet import SmartData

# Принудительное сохранение (только если были изменения)
SmartData.save_cache(force=True)

# Статистика
stats = SmartData.get_cache_stats()
print(f"Попаданий: {stats['hits']} ({stats['hit_rate']:.1f}%)")
print(f"Размер кэша: {stats['field_cache_size']} полей")
print(f"Были изменения: {stats['dirty']}")  # Флаг изменений
```

### Предзагрузка кэша из моделей
```python

from simpleworkernet import SmartData
from simpleworkernet.models.categories.customer import Customer

# Предварительная загрузка полей моделей
SmartData.preload_from_models(
    Customer.Get_data,
    Customer.Get_data.Address,
    Customer.Get_data.Tariff,
    recursive=True
)
```

### Умное сохранение

Кэш сохраняется на диск только при реальных изменениях, что экономит дисковые операции:
```python

from simpleworkernet import cache

# При выходе из программы
atexit.register(cache.ensure_saved)  # Сохраняет только если есть изменения
```

### Получение статистики кэша
```python

from simpleworkernet import SmartData

stats = SmartData.get_cache_stats()
print(f"Кэш включён: {stats['enabled']}")
print(f"Попаданий: {stats['hits']}")
print(f"Промахов: {stats['misses']}")
print(f"Процент попаданий: {stats['hit_rate']:.1f}%")
print(f"Размер кэша полей: {stats['field_cache_size']}")
print(f"Есть несохранённые изменения: {stats['dirty']}")
```

## <a name="cleanup"></a>Очистка данных

### Консольная команда
```bash

# Запуск очистки с подтверждением
cleanup-simpleworkernet

# Принудительная очистка без подтверждения
cleanup-simpleworkernet --force

# Просмотр того, что будет удалено (без удаления)
cleanup-simpleworkernet --dry-run

# Просмотр установленных приложений
cleanup-simpleworkernet --list

# Очистка конкретного приложения
cleanup-simpleworkernet --app myapp_abc123

# Очистка только логов
cleanup-simpleworkernet --logs-only

# Очистка только кэша
cleanup-simpleworkernet --cache-only

# Очистка только конфигурации
cleanup-simpleworkernet --config-only

# Показать версию
cleanup-simpleworkernet --version
```

### Программная очистка
```python

from simpleworkernet import cleanup

# С подтверждением
cleanup()

# Без подтверждения
cleanup(force=True)

# Очистка конкретного приложения
cleanup(force=True, app_name="myapp_abc123")

# Очистка только кэша
cleanup(force=True, mode='cache')
```

## <a name="examples"></a>Примеры использования

### Базовые операции с API
```python

from simpleworkernet import WorkerNetClient, config_manager

# Настройка через ConfigManager
config_manager.console_level = "DEBUG"
config_manager.console_output = True
config_manager.log_to_file = True
config_manager.save()

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    # Различные запросы
    customers = client.Module.get_user_list()
    customer = client.Customer.get_data(customer_id=123)
    addresses = client.Address.get(city_id=1)
    cables = client.Fiber.catalog_cables_get()
```

### Фильтрация данных
```python

from simpleworkernet import SmartData, Where, Operator

customers = client.Customer.get_data()

# Простая фильтрация
active = customers.where('state_id', 2)
positive_balance = customers.where('balance', 0, Operator.GT)

# Составные условия
filtered = customers.filter(
    Where('state_id', 2),
    Where('balance', 1000, Operator.GT),
    Where('city', 'Москва', Operator.LIKE),
    join='AND'
)

# Диапазон и вхождение
middle_age = customers.where('age', [25, 35], Operator.BETWEEN)
cities = customers.where('city', ['Москва', 'СПб'], Operator.IN)
```

### Глубокий поиск по структуре
```python

complex_data = [{
    "id": 1,
    "name": "Иван",
    "contacts": {
        "email": "ivan@example.com",
        "phone": "+7-999-123-45-67"
    }
}]

sd = SmartData(complex_data)

# Поиск по email в любой вложенности
results = sd.find_all('email', 'ivan@example.com')
print(f"Найдено объектов: {len(results)}")
```

### Создание пользовательских моделей
```python

from simpleworkernet import smart_model, BaseModel, vStr, vMoney
from typing import List, Optional

@smart_model
class Service(BaseModel):
    id: int
    name: vStr
    price: vMoney
    active: bool

@smart_model
class User(BaseModel):
    id: int
    login: str
    full_name: vStr
    balance: vMoney
    services: List[Service]

# Использование
user = User(**api_response)
```

### Получение ссылок на объекты
```python

from simpleworkernet import WorkerNetClient

client = WorkerNetClient('host','port')

customer_ref = client.Customer.get_link(123)
```

### Препроцессор данных API

Некоторые методы API могут возвращать данные с ключами, содержащими недопустимые для Python символы (например, дефисы в `z-position`). Для таких случаев предусмотрен механизм препроцессора.

#### Использование препроцессора

```python
from simpleworkernet import smart_model, BaseModel, vStr, api_method
from typing import List

@smart_model
class NodeType(BaseModel):
    """Модель типа узла"""
    id: int
    name: vStr
    order: int
    z_position: int  # В API приходит как 'z-position'
    map_ico: vStr
    # ... другие поля

    @staticmethod
    def preprocess_response(data: Any) -> Any:
        """
        Предобработчик для данных, возвращаемых API.
        Рекурсивно заменяет 'z-position' на 'z_position'.
        """
        if isinstance(data, dict):
            return {
                (key.replace('-', '_') if key == 'z-position' else key): 
                NodeType.preprocess_response(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [NodeType.preprocess_response(item) for item in data]
        else:
            return data

class Node(BaseCategory):
    @api_method(NodeType, preprocessor=NodeType.preprocess_response)
    def get_type_list(self) -> ApiRetSData[NodeType]:
        """Получение списка типов узлов"""
        ...
```

#### Как это работает

    Препроцессор передаётся в декоратор @api_method через параметр preprocessor

    Функция вызывается сразу после получения ответа от API, до преобразования в SmartData

    Можно реализовать любую логику трансформации данных:

        Замена символов в ключах

        Переименование полей

        Фильтрация данных

        Нормализация значений

#### Примеры препроцессоров

Замена нескольких ключей
```python

@staticmethod
def preprocess_response(data: Any) -> Any:
    KEY_MAPPING = {
        'z-position': 'z_position',
        'map-ico': 'map_ico',
        'map-color': 'map_color',
    }
    
    if isinstance(data, dict):
        return {
            KEY_MAPPING.get(key, key): NodeType.preprocess_response(value)
            for key, value in data.items()
        }
    # ... обработка списков и примитивов
```

#### Универсальный препроцессор для дефисов
```python

@staticmethod
def preprocess_response(data: Any) -> Any:
    """Заменяет дефисы на подчёркивания во всех строковых ключах"""
    if isinstance(data, dict):
        return {
            key.replace('-', '_'): NodeType.preprocess_response(value)
            for key, value in data.items()
        }
    # ... обработка списков и примитивов
```

#### Препроцессор с нормализацией значений
```python

@staticmethod
def preprocess_response(data: Any) -> Any:
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Заменяем ключ
            new_key = key.replace('-', '_')
            # Нормализуем значение если нужно
            if key == 'status' and isinstance(value, str):
                value = value.lower().strip()
            result[new_key] = NodeType.preprocess_response(value)
        return result
    # ... обработка списков и примитивов
```

### Агрегация и статистика
```python

data = [
    {"name": "Иван", "age": 30, "salary": 50000, "dept": "IT"},
    {"name": "Петр", "age": 25, "salary": 45000, "dept": "IT"},
]

sd = SmartData(data)

# Статистика
total = sd.count()  # 2
avg_age = sd.avg(lambda x: x['age'])  # 27.5
max_salary = sd.max(lambda x: x['salary'])  # 50000

# Группировка
by_dept = sd.group_by(lambda x: x['dept'])
for dept, employees in by_dept.items():
    print(f"{dept}: {employees.count()} сотрудников")

# Трансформация
names = sd.map(lambda x: x['name'].upper())
```

### Сериализация
```python

from simpleworkernet import SmartData

sd = SmartData(data)

# Сохранение в различных форматах
sd.to_file("data.json")           # JSON
sd.to_file("data.pkl", format="pkl")  # Pickle
sd.to_file("data.gz", format="gz")    # Gzip

# Загрузка
loaded = SmartData.from_file("data.json")
```

### Работа с графикой (SVG/PNG)

Модуль graphics предоставляет мощные инструменты для работы с SVG-изображениями, получаемыми из API (например, схемы коммутаций сооружений связи).

Основные возможности

    Загрузка SVG из байтов, строк или файлов

    Сохранение в файл с автоматическим именованием

    Конвертация в PNG с поддержкой кириллицы

    Извлечение метаданных (размеры, количество элементов, ID узлов)

    Отображение в Jupyter notebooks

    Валидация SVG-формата

    Автовыбор метода конвертации

#### Установка дополнительных зависимостей

Для конвертации SVG в PNG рекомендуется установить один из конвертеров:
```bash

# Wand (ImageMagick) - рекомендуется для Windows
# 1. Скачайте ImageMagick: https://imagemagick.org/script/download.php#windows
# 2. Установите, отметив "Install development headers"
# 3. Установите Wand:
pip install Wand

# CairoSVG (требует системную библиотеку Cairo)
pip install cairosvg

# WeasyPrint (требует системные библиотеки)
pip install weasyprint

# Inkscape (внешняя программа)
# Скачайте с: https://inkscape.org/

# Matplotlib (только для заглушек, не конвертирует)
pip install matplotlib
```

#### Базовое использование
```python

from simpleworkernet.utils.graphics import SVGHandler, svg_to_png
from simpleworkernet import WorkerNetClient

# Создаем клиент
client = WorkerNetClient("host", "apikey")

# Получаем схему узла (SVG)
svg_data = client.Node.get_scheme(id=123)

# Создаем обработчик
svg = SVGHandler(svg_data)

# Проверяем валидность
if svg.is_svg():
    print(f"✓ SVG валиден, размер: {svg.size[0]}x{svg.size[1]}px")
    print(f"  Есть кириллица: {svg.has_cyrillic}")
    print(f"  Элементов: {svg.metadata['element_count']}")

# Сохраняем оригинальный SVG
svg.save("scheme.svg")

# Конвертируем в PNG (автовыбор метода)
svg.to_png("scheme.png")

# Конвертируем с явным указанием метода
svg.to_png("scheme_wand.png", method='wand', dpi=300)

# С ограничением размера
svg.to_png("scheme_small.png", max_size=(1920, 1080))
```

#### Быстрые функции
```python

from simpleworkernet.utils.graphics import save_svg, load_svg, svg_to_png, is_svg

# Быстрая проверка
if is_svg(svg_data):
    print("Это SVG!")

# Быстрое сохранение
save_svg(svg_data, "quick.svg")

# Быстрая загрузка
loaded = load_svg("quick.svg")

# Быстрая конвертация
svg_to_png(svg_data, "output.png", method='auto', max_size=(1920, 1080))

# Конвертация из файла
svg_to_png("scheme.svg", "scheme.png")
```

Работа с метаданными
```python

svg = SVGHandler(svg_data)

# Размеры
width, height = svg.size
print(f"Размер: {width}x{height}px")

# Все метаданные
meta = svg.metadata
print(f"Элементов: {meta.get('element_count')}")
print(f"Кириллица: {meta.get('has_cyrillic')}")
print(f"ViewBox: {meta.get('viewbox')}")

# Извлечение текстов
texts = svg.extract_texts()
for text in texts[:5]:  # Первые 5 текстов
    print(f"Текст: {text}")

# Извлечение ID узлов (для схем)
node_ids = svg.extract_node_ids()
print(f"ID узлов: {node_ids}")
```

#### Автоматическое сохранение
```python

svg = SVGHandler(svg_data)

# Автосохранение с уникальным именем
saved_path = svg.save_auto(prefix="node_scheme")
print(f"Сохранено в: {saved_path}")

# В указанную директорию
svg.save_auto(prefix="scheme", directory="./output")
```

#### Отображение в Jupyter
```python

from simpleworkernet.utils.graphics import display_svg

# Прямое отображение
display_svg(svg_data, width=800, height=600)

# Или через обработчик
svg = SVGHandler(svg_data)
svg.display(width=800)
```

#### Разные методы конвертации
```python

# Wand (ImageMagick) - лучший для Windows
svg.to_png_wand("output.png", dpi=300, scale=2.0)

# CairoSVG
svg.to_png_cairo("output.png", dpi=300)

# Inkscape (если установлен)
svg.to_png_inkscape("output.png", dpi=300)

# WeasyPrint
svg.to_png_weasyprint("output.png", scale=2.0)

# Matplotlib (заглушка)
svg.to_png_matplotlib("output.png")
```

#### Обработка ошибок
```python

from simpleworkernet.utils.graphics import SVGHandler, SVGValidationError

try:
    svg = SVGHandler(unknown_data, validate=True)
    svg.to_png("output.png")
except SVGValidationError as e:
    print(f"Ошибка валидации SVG: {e}")
except GraphicsError as e:
    print(f"Ошибка конвертации: {e}")
```

#### Пример полного рабочего процесса
```python

from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.graphics import SVGHandler
import os

# Создаем директорию для выходных файлов
os.makedirs("output", exist_ok=True)

# Подключаемся к API
client = WorkerNetClient("my.workernet.ru", "api-key")

# Получаем схему узла
print("Запрос схемы узла...")
svg_data = client.Node.get_scheme(id=16283)

# Создаем обработчик
svg = SVGHandler(svg_data)

# Выводим информацию
print(f"✓ SVG загружен: {len(svg)} байт")
print(f"  Размер: {svg.size[0]}x{svg.size[1]}px")
print(f"  Кириллица: {'есть' if svg.has_cyrillic else 'нет'}")
print(f"  Элементов: {svg.metadata.get('element_count', 0)}")

# Сохраняем оригинал
svg.save("output/original.svg")
print("✓ Оригинал сохранён")

# Конвертируем в PNG (автовыбор метода)
try:
    png_path = svg.to_png("output/scheme.png", max_size=(1920, 1080))
    print(f"✓ PNG сохранён: {png_path}")
    
    # Если есть кириллица, проверяем что она отобразилась
    if svg.has_cyrillic:
        print("  (текст на кириллице должен отображаться корректно)")
        
except Exception as e:
    print(f"✗ Ошибка конвертации: {e}")

# Извлекаем информацию из схемы
node_ids = svg.extract_node_ids()
if node_ids:
    print(f"Найдены ID узлов: {node_ids[:10]}...")

texts = svg.extract_texts()
if texts:
    print(f"Найдены тексты: {texts[:3]}...")
```

#### Флаги доступности методов
```python

from simpleworkernet.utils.graphics import (
    WAND_AVAILABLE, CAIRO_AVAILABLE, 
    WEASYPRINT_AVAILABLE, INKSCAPE_AVAILABLE,
    MATPLOTLIB_AVAILABLE
)

print(f"Wand: {'✓' if WAND_AVAILABLE else '✗'}")
print(f"Cairo: {'✓' if CAIRO_AVAILABLE else '✗'}")
print(f"WeasyPrint: {'✓' if WEASYPRINT_AVAILABLE else '✗'}")
print(f"Inkscape: {'✓' if INKSCAPE_AVAILABLE else '✗'}")
print(f"Matplotlib: {'✓' if MATPLOTLIB_AVAILABLE else '✗'}")
```

## <a name="topology"></a>Графовая топология (Topology)

Класс `Topology` предоставляет высокоуровневый API для построения и анализа графов телекоммуникационной сети. Он объединяет два типа графов:

- **CGraph** — граф коммутаций, где вершины — интерфейсы объектов (порты, стороны), а рёбра — коммутации между ними. Хранится в виде списка связных графов (каждый компонент связности — отдельный CGraph).
- **FNGraph** — граф сооружений связи, где вершины — узлы (node_id), а рёбра — кабели (fiber_id). Всегда один связный граф.

Класс использует общий глобальный кэш `DataCache` для хранения объектов API, что обеспечивает высокую производительность при повторных запросах.

### Основные возможности

- **Построение графов от любых объектов сети** (OLT, switch, кросс, сплиттер, CWDM, кабель, волокно, абонент, узел)
- **Гибкая фильтрация** при построении:
  - `included_fibers` — разрешённые кабели (только для стартового узла)
  - `excluded_fibers` — запрещённые кабели (применяется всегда)
  - `excluded_nodes` — запрещённые узлы (применяется всегда)
- **Автоматическое объединение графов** в связные компоненты
- **Построение линейного графа** (`topology_from_commutation`) — цепочка от последнего объекта к корневому (OLT или коммутатор)
- **Получение списков объектов** из построенных графов: абоненты, узлы, кабели, волокна, устройства, сплиттеры, CWDM, кроссы
- **Загрузка объектов по ID** с использованием общего кэша

### Быстрый старт

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import Topology

# Создаем клиент и топологию
client = WorkerNetClient("my.workernet.ru", "your-api-key")
topo = Topology(client)

# Построение графа от кросса (порт 7)
topo.build_from_cross('98d9d368-43e9-4513-9ec7-4e076eea2bda', port=7)

# Получаем список абонентов в топологии
customers = topo.get_customers()
print(f"Найдено абонентов: {len(customers)}")

# Получаем линейную цепочку от абонента до корневого устройства
linear_topology = topo.topology_from_commutation('customer', customers[0])
print(f"Линейный граф: {len(linear_topology.cgraphs[0].vs)} вершин")
```

### Методы построения
build_from_device

Строит граф от устройства (OLT, switch, ONU).
```python
# От OLT (все PON-порты)
topo.build_from_device('olt', 12345)

# От OLT (конкретный порт)
topo.build_from_device('olt', 12345, port=1)

# От switch
topo.build_from_device('switch', 67890, port=5)

# С фильтрацией
topo.build_from_device(
    'olt', 12345,
    included_fibers=[23682, 23683],
    excluded_nodes=[23780, 23781]
)
```
build_from_customer

Строит граф от абонента (все его коммутации).
```python
topo.build_from_customer(68168)
```

build_from_cross

Строит граф от кросса. Порт указывается обязательно, сторона опционально.
```python
# От конкретного порта (все стороны)
topo.build_from_cross('98d9d368-43e9-4513-9ec7-4e076eea2bda', port=7)

# От порта с указанием стороны
topo.build_from_cross('98d9d368-43e9-4513-9ec7-4e076eea2bda', port=7, side=1)

# От всех портов кросса (каждый порт — отдельный связный граф)
topo.build_from_cross('98d9d368-43e9-4513-9ec7-4e076eea2bda')
```

build_from_splitter

Строит граф от сплиттера.
```python
# От всех интерфейсов (объединяются в один граф)
topo.build_from_splitter(35196)

# От конкретного порта и стороны
topo.build_from_splitter(35196, port=1, side=1)
```

build_from_cwdm

Строит граф от CWDM. Логика аналогична build_from_splitter.
```python
topo.build_from_cwdm(12345, port=1, side=2)
```

build_from_fiber

Строит граф от конкретного волокна в кабеле.
```python
# object_id — ID кабеля, port — порядковый номер волокна (interface)
topo.build_from_fiber(23682, port=1, side=1)
```

build_from_node

Строит граф от сооружения связи (узла). Находит все объекты в узле и строит графы от них, объединяя результат.
```python
topo.build_from_node(23779)
```

build_from_cable

Строит граф от всех волокон кабеля.
```python
topo.build_from_cable(23682)
```

### Фильтрация при построении

Все методы построения принимают три параметра фильтрации:

    included_fibers (Set[int]): ID кабелей, через которые разрешён проход. Применяется только пока мы находимся в стартовом узле. Как только переходим на другой узел, фильтр игнорируется.

    excluded_fibers (Set[int]): ID кабелей, на которых обход останавливается. Применяется всегда.

    excluded_nodes (Set[int]): ID узлов, на которых обход останавливается. Применяется всегда.
```python
# Пример: строим граф от кросса, но не проходим через кабель 23685
topo.build_from_cross(
    '98d9d368-43e9-4513-9ec7-4e076eea2bda',
    port=7,
    excluded_fibers=[23685]
)

# Пример: строим граф от узла, но останавливаемся на узлах 23780 и 23781
topo.build_from_node(
    23779,
    excluded_nodes=[23780, 23781]
)
```

### Получение данных из графа

```python
# Списки объектов
customers = topo.get_customers()      # ID абонентов
nodes = topo.get_nodes()              # ID узлов
cables = topo.get_cables()            # ID кабелей
fibers = topo.get_fibers()            # ID волокон (clps_mid)
devices = topo.get_devices()          # ID устройств
splitters = topo.get_splitters()      # ID сплиттеров
cwdms = topo.get_cwdms()              # ID CWDM
crosses = topo.get_crosses()          # UUID кроссов

# Получение объектов по ID (с использованием кэша)
customer = topo.customer(68168)
node = topo.node(23779)
cable = topo.cable(23682)
device = topo.device(12345)
splitter = topo.splitter(35196)
cwdm = topo.cwdm(12345)
cross = topo.cross('98d9d368-43e9-4513-9ec7-4e076eea2bda')
```

### Построение линейного графа (topology_from_commutation)

Метод topology_from_commutation строит линейный граф (цепочку) от указанного последнего объекта в направлении к корневому объекту (OLT или коммутатор). Возвращает новый объект Topology, содержащий только линейный граф.
```python
# Простейший случай: от абонента до корня (OLT или switch)
linear = topo.topology_from_commutation('customer', customer_id)

# С явным указанием корневого объекта (первого в цепочке)
linear = topo.topology_from_commutation(
    'customer', customer_id,
    first_object_type='olt',
    first_object_id=12345
)

# Для объектов со сторонами указываем порт и сторону
linear = topo.topology_from_commutation(
    'splitter', 35196,
    port=1, side=2
)

# Для объектов с несколькими коммутациями обязательно указать first_object
linear = topo.topology_from_commutation(
    'customer', customer_id,
    first_object_type='olt',
    first_object_id=12345
)
```
#### Правила работы метода:

    Для сплиттера порт обязателен (движение от указанного выхода ко входу)

    Для кросса и кабеля обязательны порт и сторона (транзит через один порт)

    Для CWDM порт обязателен, сторона опциональна

    Для абонента порт не требуется (если несколько коммутаций — обязательно указать first_object)

    Если first_object не указан, автоматически ищется OLT или switch. Если их несколько, выбирается самый удалённый от старта.

    Если в графе нет OLT или switch, выбрасывается исключение с предложением указать first_object явно.
```python
# Автоматический поиск корня (OLT или switch)
linear = topo.topology_from_commutation('customer', customer_id)

# Явное указание корня (если автоматический поиск невозможен)
linear = topo.topology_from_commutation(
    'customer', customer_id,
    first_object_type='switch',
    first_object_id=100855
)
```

### Структура хранения графов

```python
# Список связных графов коммутаций
topo.cgraphs  # List[CGraph]

# Единственный связный граф сооружений
topo.fngraph  # Optional[FNGraph]
```
Каждый CGraph гарантированно связный. Если построение даёт несколько компонент связности, они сохраняются как отдельные элементы списка.

### Пример полного рабочего процесса

```python
from simpleworkernet import WorkerNetClient
from simpleworkernet.utils.topology import Topology

# Инициализация
client = WorkerNetClient("my.workernet.ru", "your-api-key")
topo = Topology(client)

# 1. Строим граф от кросса (порт 7)
topo.build_from_cross('98d9d368-43e9-4513-9ec7-4e076eea2bda', port=7)

# 2. Получаем всех абонентов
customers = topo.get_customers()
print(f"Найдено абонентов: {len(customers)}")

# 3. Для первого абонента строим линейный граф до корня
linear = topo.topology_from_commutation('customer', customers[0])

# 4. Анализируем линейный граф
print(f"Линейный граф: {linear.cgraphs[0].vcount()} вершин, {linear.cgraphs[0].ecount()} рёбер")

# 5. Получаем все устройства в линейном графе
devices_in_line = linear.get_devices()
print(f"Устройств в цепочке: {len(devices_in_line)}")

# 6. Получаем объект корневого устройства (последняя вершина)
# Можно получить последнюю вершину в линейном графе
root_vertex = linear.cgraphs[0].vs[len(linear.cgraphs[0].vs) - 1]
print(f"Корневое устройство: {root_vertex['obj_type']}:{root_vertex['obj_id']}")
```

### Особенности реализации

    Связность графов: все CGraph всегда связные. Если при построении получается несвязный граф, он не добавляется.

    Общий кэш: все объекты и коммутации сохраняются в глобальном DataCache, что обеспечивает быстрый доступ при повторных запросах.

    Автоматическое объединение: при построении от нескольких точек входа графы автоматически объединяются в связные компоненты.

    Линейный граф: метод topology_from_commutation строит цепочку, проходя через сплиттеры строго от выхода к входу, через кроссы и кабели — транзитом через один порт.
  
## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894) 
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
