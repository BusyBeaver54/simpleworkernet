# Клиент и SmartData

## WorkerNetClient

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

Рекомендуется контекстный менеджер:

```python
with WorkerNetClient("my.workernet.ru", "key") as client:
    users = client.Module.get_user_list()
```

## SmartData

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

```python
from simpleworkernet import Operator, Where
```

Для получения необработанных данных используйте lowercase категорий с теми же параметрами:
```python
users = client.module.get_user_list()
```

## BaseModel / smart_model

```python
from simpleworkernet import BaseModel, smart_model, vStr

@smart_model
class DeviceInfo(BaseModel):
    id: int
    name: vStr
    parent_id: int | None = None
```

Рекурсивный кастинг Union / Optional / List / вложенных моделей из сырого JSON.
