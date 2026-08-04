# Быстрый старт

## Клиент и фильтры

```python
from simpleworkernet import WorkerNetClient, Where, Operator

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    customers = client.Module.get_user_list()
    active = customers.where("state_id", 2)
    print(active.count())

    rich = customers.where("balance", 1000, Operator.GTE)
    moscow = customers.where("city", "Москва", Operator.LIKE)

    # несколько условий
    subset = customers.filter(
        Where("state_id", 2),
        Where("balance", 500, Operator.GTE),
    )
    print(subset.sort(key_field="balance", reverse=True).limit(5).to_list())
```

Контекстный менеджер открывает/закрывает HTTP-сессию.
Без `with`: `client.session()` / `client.closeSession()`.

## Сохранение выборки

```python
active.to_file("active_users.json")          # структура по meta
active.save_raw("active_raw.json")           # плоский raw
```

## Топология (нужен python-igraph)

```python
from simpleworkernet import WorkerNetClient, Topology

with WorkerNetClient("my.workernet.ru", "key") as client:
    topo = Topology(client)
    topo.build_from_device("olt", 12345, port=1)
    customers = topo.get_customers()
    print(len(customers))

    if customers:
        linear = topo.topology_from_commutation("customer", customers[0])
        topo.save_to_file("topo.json")
```

## Координаты

```python
from simpleworkernet import GeoPoint

a = GeoPoint(55.75, 37.62)
b = GeoPoint(55.76, 37.63)
print(a.distance_to(b))           # км
x, y = b.to_xy(center=a)          # mercator relative + cos(lat)
```

Далее: [Клиент и SmartData](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/client-and-smartdata.md), [Топология](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/topology.md).
