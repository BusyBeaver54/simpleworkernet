# Графовая топология

**Зависимость:** `pip install python-igraph`

## Быстрый пример

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

## Типы графов

| Граф | Вершины | Рёбра |
|------|---------|-------|
| **CGraph** | интерфейсы (`obj_type` + `obj_id` + `side` + `port`) | коммутации |
| **FNGraph** | `node_id` | `fiber_id` |

Фильтры при build: `included_fibers`, `excluded_fibers`, `excluded_nodes`.

## DataCache

Отдельный экземплярный кэш (не синглтон) для инвентаря, длин волокон и geo.
Можно передавать один `DataCache` нескольким `Topology`.

См. также: [Затухания](attenuation.md).
