# Тесты

Структура:

```text
tests/
├── conftest.py              # CLI-опции --wn-*, фикстуры
├── test_coordinates.py
├── test_primitives.py
├── test_operators.py
├── test_smartdata.py
├── test_exceptions.py
├── test_version.py
├── integration/
│   ├── test_api_smoke.py
│   └── test_topology_live.py
└── topology/
    ├── test_cgraph.py, test_fngraph.py, test_linear.py, …
    ├── test_attenuation.py, test_attenuation_splitter.py
    └── test_cache.py, test_handlers.py, test_merge.py, …
```

## Offline (unit)

Не требуют API. Покрывают примитивы, координаты, SmartData, operators,
topology (CGraph/FNGraph/handlers/linear/merge/attenuation/cache) на
синтетических данных.

```bash
pytest tests/ -m "not integration" -v
pytest tests/test_coordinates.py -v
pytest tests/test_operators.py tests/test_smartdata.py -v
pytest tests/topology/ -v
```

## Integration (live API)

Нужны доступный WorkerNet и ключ. Маркер: `@pytest.mark.integration`.
Без host/apikey тесты **skip**.

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

| Опция | Env | Описание |
|-------|-----|----------|
| `--wn-host` | `WORKERNET_HOST` | хост API |
| `--wn-apikey` | `WORKERNET_APIKEY` | API-ключ |
| `--wn-protocol` | `WORKERNET_PROTOCOL` | `http` / `https` (default `https`) |
| `--wn-port` | `WORKERNET_PORT` | порт (default `443`) |
| `--nodeid` | `WORKERNET_TEST_NODE_ID` | ID узла для live topology |
| `--customerid` | `WORKERNET_TEST_CUSTOMER_ID` | ID абонента |

Настройки pytest: `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths`, `pythonpath=src`, marker `integration`).
