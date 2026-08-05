# **SimpleWorkerNet**

Python-клиент для REST API [WorkerNet](https://workernet.ru) с типизацией ответов, SmartData и графовой топологией сети.

[![Tag](https://img.shields.io/github/v/tag/busy4beaver/simpleworkernet?color=00c2e8)](https://pypi.org/project/simpleworkernet/)
[![Supported Python versions](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=FFE873)](https://www.python.org/downloads/)
[![Licence](https://img.shields.io/github/license/busy4beaver/simpleworkernet.svg)](LICENSE)

---

## Особенности

| Область | Что даёт |
|---------|----------|
| **SmartData** | Автокастинг JSON → объекты, метаданные пути, fluent-фильтры |
| **BaseModel** | Рекурсивный кастинг Union / Optional / List / вложенных моделей |
| **WorkerNetClient** | Сессии, авто-GET/POST при длинном URL, ретраи |
| **Логирование** | Стандартный `logging`, без собственного управления |
| **Кэш полей** | LFU / LRU / FIFO, dirty-flag, предзагрузка из моделей |
| **Топология** | CGraph + FNGraph, фильтры, линейные цепочки, save/load |
| **Attenuation** | Расчёт оптических затуханий по CGraph (fiber / splitter / splice / adapter) |
| **Координаты** | WGS84 ↔ Mercator (default) / local ENU / UTM |
| **Графика** | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |
| **Cleanup CLI** | `cleanup-simpleworkernet` — логи, кэш, конфиг |

---

## Установка

```bash
pip install simpleworkernet
```

Опционально:

```bash
pip install python-igraph   # топология
pip install pyproj          # UTM
pip install Wand            # SVG → PNG
```

Подробнее: [docs/installation.md](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/installation.md)

---

## Быстрый старт

```python
from simpleworkernet import WorkerNetClient, Where, Operator

with WorkerNetClient("my.workernet.ru", "your-api-key") as client:
    customers = client.Module.get_user_list()
    active = customers.where("state_id", 2)
    print(active.count())

    rich = customers.where("balance", Operator.GE, 1000)
```

Полный гайд: [docs/quickstart.md](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/quickstart.md)

---

## Документация

| Раздел | Описание |
|--------|----------|
| [Установка](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/installation.md) | pip, опциональные зависимости |
| [Быстрый старт](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/quickstart.md) | первый клиент, SmartData |
| [Конфигурация](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/configuration.md) | `config_manager`, defaults |
| [Клиент и SmartData](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/client-and-smartdata.md) | WorkerNetClient, фильтры, модели |
| [Логирование](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/logging.md) | stdlib logging |
| [Кэш и каталоги данных](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/cache-and-data.md) | SmartDataCache, XDG/AppData пути |
| [Координаты](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/coordinates.md) | GeoPoint, проекции, legacy AUTOCAD |
| [Топология](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/topology.md) | CGraph, FNGraph, Topology |
| [Затухания](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/attenuation.md) | Attenuation, каталог, PathReport |
| [Графика](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/graphics.md) | SVG / PNG |
| [Очистка](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/cleanup.md) | CLI `cleanup-simpleworkernet` |
| [Тесты](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/testing.md) | unit / integration |

Структура пакета и публичный API: [docs/package-structure.md](https://github.com/busy4beaver/simpleworkernet/blob/main/docs/package-structure.md)

Полный индекс: [docs/](https://github.com/busy4beaver/simpleworkernet/tree/main/docs)

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
