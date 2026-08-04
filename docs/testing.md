# Тесты

## Offline (unit)

Не требуют API. Покрывают примитивы, координаты, SmartData, operators,
topology (CGraph/FNGraph/handlers/linear/merge/attenuation/cache) на
синтетических данных.

```bash
pytest tests/ -m "not integration" -v
```

Только координаты:

```bash
pytest tests/test_coordinates.py -v
```

Только топология:

```bash
pytest tests/topology/ -v
```

## Integration (live API)

Нужны доступный WorkerNet и ключ.

```bash
pytest tests/ -v --wn-host=my.workernet.ru --wn-apikey=YOUR_KEY
```

Или через окружение:

```bash
export WORKERNET_HOST=my.workernet.ru
export WORKERNET_APIKEY=YOUR_KEY
export WORKERNET_PROTOCOL=https
export WORKERNET_PORT=443
export WORKERNET_TEST_NODE_ID=123
export WORKERNET_TEST_CUSTOMER_ID=456
pytest tests/ -v
```

CLI-опции pytest (см. `tests/conftest.py`):

| Опция | Env | Описание |
|-------|-----|----------|
| `--wn-host` | `WORKERNET_HOST` | хост API |
| `--wn-apikey` | `WORKERNET_APIKEY` | API-ключ |
| `--wn-protocol` | `WORKERNET_PROTOCOL` | `http` / `https` (default `https`) |
| `--wn-port` | `WORKERNET_PORT` | порт (default `443`) |
| `--nodeid` | `WORKERNET_TEST_NODE_ID` | ID узла для live topology |
| `--customerid` | `WORKERNET_TEST_CUSTOMER_ID` | ID абонента |

Без host/apikey integration-тесты автоматически `skip`.

Маркер: `@pytest.mark.integration`.
