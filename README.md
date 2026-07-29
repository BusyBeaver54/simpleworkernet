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
- [Координаты (GeoPoint)](#координаты-geopoint)
- [Графовая топология (Topology)](#графовая-топология-topology)
- [Тесты](#тесты)
- [Поддержать проект](#-поддержать-проект)

---

## Особенности

| Область | Что даёт |
|---------|----------|
| **SmartData** | Автокастинг JSON → объекты, метаданные пути, fluent-фильтры |
| **WorkerNetClient** | Сессии, авто-GET/POST, ретраи |
| **Topology** | CGraph + FNGraph |
| **GeoPoint** | WGS84 ↔ local ENU / UTM / Mercator, `GeoPointArray` |
| **Graphics** | SVG → PNG |

---

## Структура пакета

```text
src/simpleworkernet/
├── models/primitives.py     # GeoPoint, GeoPointArray, …
├── utils/topology/          # Topology, CGraph, FNGraph
└── …
```

```python
from simpleworkernet import GeoPoint, GeoPointArray, Topology, WorkerNetClient
```

---

## Установка

```bash
pip install simpleworkernet
pip install python-igraph   # topology
pip install pyproj          # опционально, для UTM
```

---

## Координаты (GeoPoint)

По умолчанию `projection="local"` — локальная плоскость **East / North** относительно `center`:
ось **Y = истинный север** (как у карты «север вверх»). Подходит для вставки объектов на подложку в CAD.

```python
from simpleworkernet import GeoPoint, GeoPointArray

origin = GeoPoint(55.75, 37.60)
pt = GeoPoint(55.75, 37.62)

# локальные метры: X — восток, Y — север
x, y = pt.to_xy(center=origin)

back = GeoPoint.from_xy(x, y, center=origin)

# массив
arr = GeoPointArray([(55.75, 37.62), (55.76, 37.63)])
xy = arr.to_xy(center=arr.center())

# другие проекции при необходимости
x, y = pt.to_xy(center=origin, projection="utm")       # нужен pyproj
x, y = pt.to_xy(center=origin, projection="mercator")
```

| Параметр | Описание |
|----------|----------|
| `center` | точка привязки (origin чертежа / куска карты) |
| `projection` | `local` (default) \| `utm` \| `mercator` |
| `rotation_deg` | доп. поворот, если нужен project north |
| `scale` / `offset` | масштаб и смещение |

---

## Графовая топология (Topology)

```python
from simpleworkernet.utils.topology import Topology, DataCache

topo = Topology(client, cache=DataCache())
topo.build_from_node(23779)
```

---

## Тесты

```bash
pytest tests/ -m "not integration" -v

pytest tests/ -v \
  --wn-host=my.workernet.ru --wn-apikey=SECRET \
  --nodeid=23779 --customerid=68168
```

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
