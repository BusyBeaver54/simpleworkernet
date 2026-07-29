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
- [Логирование](#логирование)
- [Кэширование](#кэширование)
- [Очистка данных](#очистка-данных)
- [Графика (SVG/PNG)](#графика-svgpng)
- [Координаты](#координаты)
- [Графовая топология (Topology)](#графовая-топология-topology)
- [Тесты](#тесты)
- [Поддержать проект](#-поддержать-проект)

> **Примечание:** если в истории git есть полный README (до accidental truncate), восстановите его через
> `git checkout 40f10e2381fff574c86123578ffe85b2e3bb0fbf -- README.md` и смержите раздел Тесты ниже.

---

## Тесты

Тесты в `tests/`. Pytest: `[tool.pytest.ini_options]` в `pyproject.toml`.

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
