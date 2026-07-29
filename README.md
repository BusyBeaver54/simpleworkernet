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
- [Координаты (GeoPoint)](#координаты-geopoint)
- [Графовая топология (Topology)](#графовая-топология-topology)
- [Тесты](#тесты)
- [Поддержать проект](#-поддержать-проект)

---

## Особенности

| Область | Что даёт |
|---------|----------|
| **SmartData** | Автокастинг JSON → объекты, метаданные пути, fluent-фильтры |
| **BaseModel** | Рекурсивный кастинг Union / Optional / List / вложенных моделей |
| **WorkerNetClient** | Сессии, авто-GET/POST при длинном URL, ретраи |
| **Логирование** | Раздельные уровни console / file, сессионные логи, ротация |
| **Кэш полей** | LFU / LRU / FIFO, dirty-flag, предзагрузка из моделей |
| **Topology** | CGraph + FNGraph, фильтры, линейные цепочки, save/load |
| **GeoPoint** | WGS84 ↔ UTM/Mercator, пакет `GeoPointArray`, коррекция grid north |
| **Graphics** | SVG → PNG (Wand / Cairo / Inkscape / WeasyPrint) |
| **Cleanup CLI** | `cleanup-simpleworkernet` — логи, кэш, конфиг |

---

## Структура пакета

```text
src/simpleworkernet/
├── models/
│   └── primitives.py        # GeoPoint, GeoPointArray, vMoney, …
├── utils/
│   ├── graphics.py
│   └── topology/            # CGraph, FNGraph, Topology
└── …
```

Модуль `utils/coordinates.py` **удалён** — проекции живут в `GeoPoint`.

```python
from simpleworkernet import GeoPoint, GeoPointArray, Topology, WorkerNetClient
```

---

## Установка

```bash
pip install simpleworkernet
pip install python-igraph          # topology
pip install pyproj                 # точный UTM (иначе — mercator)
```

---

## Координаты (GeoPoint)

### Одна точка

```python
from simpleworkernet import GeoPoint

pt = GeoPoint(55.75, 37.62)
origin = GeoPoint(55.75, 37.60)

# абсолютные метры (UTM нужен pyproj; иначе projection="mercator")
x, y = pt.to_xy(projection="utm", absolute=True)

# локальные относительно origin (для CAD)
x, y = pt.to_xy(center=origin, projection="utm")

# выровнять Y с истинным севером (см. «наклон» ниже)
x, y = pt.to_xy(center=origin, projection="utm", correct_grid_north=True)

# обратно
back = GeoPoint.from_xy(x, y, center=origin, projection="utm", correct_grid_north=True)

pt.utm_zone                  # 37 для Москвы
pt.meridian_convergence()    # угол γ, градусы
pt.distance_to(origin)       # км, гаверсинус
```

### Массив точек

```python
from simpleworkernet import GeoPointArray

arr = GeoPointArray([(55.75, 37.62), (55.76, 37.63), "55.77,37.64"])
center = arr.center()
xy = arr.to_xy(center=center, projection="utm", correct_grid_north=True)
restored = GeoPointArray.from_xy(xy, center=center, projection="utm", correct_grid_north=True)
sw, ne = arr.bounds()
```

| Метод | Описание |
|-------|----------|
| `to_xy` / `from_xy` | WGS84 ↔ плоские метры |
| `to_xyz` | + высота `z` |
| `correct_grid_north` | поворот на −γ (true north) |
| `rotation_deg` | доп. поворот (project / plant north) |
| `projection` | `"utm"` \| `"mercator"` |

### Почему в AutoCAD объекты «наклонены» относительно карты

| Причина | Суть |
|---------|------|
| **Схождение меридианов** | В UTM оси || центральному меридиану зоны, а не true north. γ ≈ (λ−λ₀)·sin(φ). На карте «вверх = север» локальная UTM-система выглядит повёрнутой. **Фикс:** `correct_grid_north=True`. |
| **Разная CRS** | Точки в UTM, подложка — Web Mercator / «сырой» lat-lon. |
| **Project north** | В чертеже задан локальный север площадки ≠ географическому. **Фикс:** `rotation_deg=…`. |
| **Оси X/Y** | UTM: X=Easting, Y=Northing. Путаница с «север = −Y» в CAD. |
| **Нет единой привязки** | Без `center` абсолютные UTM-метры «уезжают»; для CAD всегда задавайте origin. |

---

## Графовая топология (Topology)

```python
from simpleworkernet.utils.topology import Topology, DataCache

topo = Topology(client, cache=DataCache())
topo.build_from_node(23779)
```

**Зависимость:** `pip install python-igraph`

---

## Тесты

```bash
pytest tests/ -m "not integration" -v

pytest tests/ -v \
  --wn-host=my.workernet.ru --wn-apikey=SECRET \
  --nodeid=23779 --customerid=68168
```

| CLI | Env |
|-----|-----|
| `--wn-host` | `WORKERNET_HOST` |
| `--wn-apikey` | `WORKERNET_APIKEY` |
| `--nodeid` | `WORKERNET_TEST_NODE_ID` |
| `--customerid` | `WORKERNET_TEST_CUSTOMER_ID` |

---

## ☕ Поддержать проект

[![YooMoney](https://img.shields.io/badge/Donation-Yoo.money-blue.svg)](https://yoomoney.ru/to/4100118099549894)
[![Boosty](https://img.shields.io/badge/Boosty-donate-orange.svg)](https://boosty.to/busybeaver/donate)
