# Быстрый старт

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

## Минимальный пример топологии

```python
from simpleworkernet import WorkerNetClient, Topology

with WorkerNetClient("my.workernet.ru", "key") as client:
    topo = Topology(client)
    topo.build_from_device("olt", 12345, port=1)
    customers = topo.get_customers()
    print(len(customers))
```

Нужен `python-igraph`.

См. также: [Клиент и SmartData](client-and-smartdata.md), [Топология](topology.md).
