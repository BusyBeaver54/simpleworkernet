# Клиент и SmartData

## WorkerNetClient

HTTP-клиент к REST API WorkerNet. Категории API доступны как атрибуты.

### Конструктор

```python
WorkerNetClient(
    host: str,                          # например "my.workernet.ru"
    apikey: str,
    protocol: Literal["http", "https"] = "https",
    port: int = 443,
    apiscr: str = "api.php",
    session: requests.Session | None = None,
    timeout: int | None = None,         # иначе config_manager.default_timeout
    max_retries: int | None = None,     # иначе config_manager.max_retries
)
```

URL собирается как `{protocol}://{host}:{port}/{apiscr}`.

### Сессия

| Метод | Описание |
|-------|----------|
| `session()` | Создаёт `requests.Session`, если ещё нет. Возвращает `True`, если сессия была создана сейчас. |
| `closeSession()` | Закрывает сессию. |
| `__enter__` / `__exit__` | Контекстный менеджер: открывает/закрывает сессию. |

```python
with WorkerNetClient("my.workernet.ru", "key") as client:
    users = client.Module.get_user_list()
```

Без `with`:

```python
client = WorkerNetClient("my.workernet.ru", "key")
client.session()
try:
    users = client.Module.get_user_list()
finally:
    client.closeSession()
```

### Запросы

Параметры запроса: `key`, `cat` (категория), `action` (+ пользовательские kwargs).
Для категории `module` поле `action` уходит как `request`.

- Если длина URL ≤ 2048 — **GET**.
- Если длиннее — **POST** с теми же params.
- Повторы при timeout: до `max_retries`.
- Строки в params: `/` → `&#047;`, `\` → `&#092;`.

| Метод | Описание |
|-------|----------|
| `is_online(timeout=5)` | Проверка доступности сервера (status code или `False`). |
| `set_timeout(timeout)` | Таймаут запросов (пишет в `config_manager`). |
| `set_max_retries(n)` | Число повторов. |

### Категории API

Заранее объявленные (типизированные модели):

`Address`, `Attach`, `Additional_data`, `Advertising`, `Billing`, `Cable_route`, `Call`, `Commutation`, `Cross`, `Customer`, `Cwdm`, `Device`, `Employee`, `Fiber`, `Gps`, `Inventory`, `Key`, `Map`, `Module`, `Node`, `Notepad`, `Owner`, `Service`, `Setting`, `Sms`, `Splitter`, `System`, `Tariff`, `Task`, `Trader`, `Vehicle`, `Vlan`.

```python
users = client.Module.get_user_list()
nodes = client.Node.get()
fibers = client.Fiber.get_list(cable_line_type_id=1)
```

Неизвестное имя категории создаёт **динамическую** категорию через `__getattr__`:

```python
# cat=some_category, action=list
data = client.some_category.list(param=1)
```

---

## SmartData

Контейнер над ответом API: lazy-кастинг в модели, fluent-фильтры, сериализация.

При создании JSON проходит через `DataProcessor` (глубина — `smartdata_max_depth`). Элементы хранятся как raw; модель создаётся при первом доступе (`_get_item`) и кэшируется.

### Фильтрация и поиск

#### `where(key, value=None, op=Operator.EQ)`

Одно условие. Эквивалент `filter(Where(key, value, op))`.

```python
from simpleworkernet import Operator

active = users.where("state_id", 2)
rich = users.where("balance", 1000, Operator.GTE)
# или позиционно: where(key, value, op)
```

#### `filter(*conditions: Where, join="AND")`

Несколько условий. `join="AND"` — все; иначе — любое (`OR`).

```python
from simpleworkernet import Where, Operator

result = users.filter(
    Where("state_id", 2),
    Where("balance", 500, Operator.GTE),
    join="AND",
)
```

#### Операторы (`Operator`)

| Оператор | Смысл |
|----------|--------|
| `EQ` (`==`) | Равно |
| `NE` (`!=`) | Не равно |
| `GT` / `LT` / `GTE` / `LTE` | Сравнения; при TypeError — приведение типа value к типу поля |
| `LIKE` | Подстрока, case-insensitive (`value in target`) |
| `IN` | `target in value` (value — коллекция) |
| `BETWEEN` | Диапазон `[min, max]` (value — list/tuple из 2 чисел, порядок любой) |
| `REGEX` | `re.search(pattern, str(target))` |

Значение поля берётся так: `getattr(item, key)` или `item.get(key)` для dict; иначе `None`.

```python
users.where("name", "иван", Operator.LIKE)
users.where("state_id", [1, 2, 3], Operator.IN)
users.where("balance", [100, 5000], Operator.BETWEEN)
users.where("comment", r"^TODO", Operator.REGEX)
```

### Выборка и порядок

| Метод | Описание |
|-------|----------|
| `sort(key=None, reverse=False, key_field=None)` | Сортировка. `key_field` — имя поля dict/attr; иначе callable `key`. |
| `limit(n)` | Первые `n` элементов. |
| `skip(n)` | Пропустить первые `n`. |
| `unique(key_func=None)` | Уникальные; с `key_func` — по ключу. |
| `group_by(key_func)` | `dict[key → SmartData]`. |

```python
users.sort(key_field="balance", reverse=True).limit(10)
by_city = users.group_by(lambda u: u.city if hasattr(u, "city") else None)
```

Цепочки возвращают **новый** `SmartData` (`_derive`), исходный не меняется.

### Доступ к элементам

| Метод / синтаксис | Описание |
|-------------------|----------|
| `count()` / `len(sd)` | Число элементов. |
| `first()` / `last()` | Первый/последний как модель (или `None`). |
| `sd[i]` | Элемент по индексу (lazy model). |
| `sd[i:j]` | Срез → новый `SmartData`. |
| `sd["field"]` / `sd.field` | Список значений поля по всем элементам. |
| `for x in sd` | Итерация с кастингом. |
| `item in sd` | Проверка вхождения. |
| `sd1 + sd2` | Конкатенация raw-списков. |

```python
print(users.count())
print(users.first())
ids = users["id"]          # list
names = users.name         # то же через __getattr__
for u in users.limit(5):
    print(u)
```

### Агрегаты и map

| Метод | Описание |
|-------|----------|
| `map(func)` | `list` результатов `func` по каждому элементу (raw, при ошибке — model). |
| `min(key_func=None)` / `max(...)` | Элемент с мин/макс; с `key_func` — по ключу. |
| `sum(key_func)` / `avg(key_func)` | Сумма / среднее по числовому ключу. |

```python
names = users.map(lambda u: u.get("name") if isinstance(u, dict) else u.name)
total = users.sum(lambda u: float(u.get("balance") or 0))
```

### Сериализация и структура

При разборе ответа `DataProcessor` вешает на элементы **метаданные пути** (`MetaData`: сегменты FLD/IDX/NUM/DAT/COL). Это позволяет восстановить вложенную структуру JSON.

| Метод | Описание |
|-------|----------|
| `to_list()` | Все элементы как модели (`list[T]`). |
| `to_raw_list()` | Копия raw-списка (с meta, без кастинга). |
| `to_dict()` | Восстановление иерархии по meta.path. Без meta → `{"data": items}`. Плоский index-only path → `{"data": [...]}` без meta. Иначе вложенный dict. |
| `to_file(filename, format=None)` | `to_dict()` → файл. Формат по суффиксу: `json`, `pkl`, `gz` (gzip+pickle). |
| `save_raw(filename, format=None)` | Сырой `_raw_items` без восстановления структуры. |
| `SmartData.from_file(filename, target_type=Any)` | Загрузка json/pkl/gz → новый SmartData. |

```python
users.to_file("users.json")           # структура по meta
users.save_raw("users_raw.json")      # плоский raw
loaded = SmartData.from_file("users.json")
```

Метаданные элемента:

```python
meta = users.get_metadata(users.first())
path = users.get_item_path(users.first())  # строка пути
```

### Кэш схем полей (classmethod)

| Метод | Описание |
|-------|----------|
| `preload_from_models(*classes, recursive=True)` | Прогрев кэша имён полей из моделей. |
| `save_cache(force=False)` / `load_cache()` / `clear_cache()` | Персист кэша схем. |
| `get_cache_stats()` / `set_cache_max_size(n)` | Статистика / лимит. |
| `get_stats()` | Статистика этого экземпляра (items, models_created, processor_stats). |

При импорте пакета (если кэш включён) схемы category-моделей предзагружаются автоматически.

---

## BaseModel / smart_model

```python
from simpleworkernet import BaseModel, smart_model, vStr

@smart_model
class DeviceInfo(BaseModel):
    id: int
    name: vStr
    parent_id: int | None = None
```

Рекурсивный кастинг Union / Optional / List / вложенных моделей из сырого JSON. Ответы API-категорий оборачиваются в SmartData с соответствующим `target_type`.
