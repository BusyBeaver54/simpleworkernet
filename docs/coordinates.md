# Координаты

`GeoPoint` / `GeoPointArray` — WGS84 и проекции в плоские метры.

**По умолчанию:** `projection="mercator"` (`DEFAULT_PROJECTION`).

```python
from simpleworkernet import GeoPoint, GeoPointArray
from simpleworkernet.models.primitives import HAS_PYPROJ
```

## Создание GeoPoint

```python
GeoPoint(55.75, 37.62)
GeoPoint([55.75, 37.62])
GeoPoint("55.75,37.62")
GeoPoint({"lat": 55.75, "lon": 37.62})
GeoPoint(other_geopoint)
```

## Проекции

| `projection` | Описание | Зависимости |
|--------------|----------|-------------|
| `"mercator"` **(default)** | Web Mercator; relative → метры через × cos(lat) | нет |
| `"local"` | East/North относительно `center`; Y = истинный север | нет |
| `"utm"` | UTM-зона по долготе; опционально `correct_grid_north` | `pyproj` |

## Масштаб Mercator

Web Mercator завышает наземные расстояния в `1/cos(φ)`.

При **relative**-режиме (`center` задан, `absolute=False`) и
`auto_scale_mercator=True` (default):

1. сырые mercator-координаты точки и центра;
2. **разность** (delta);
3. delta × `cos(center.lat)`.

Центр остаётся `(0, 0)`; на субкилометровых базисах совпадает с `projection="local"` (R=6378137) с точностью ≪ 0.1 %.

Для тайлов OSM/Google: `absolute=True`, `auto_scale_mercator=False` (EPSG:3857-like).

## Методы GeoPoint

### `to_xy(...)`

```python
to_xy(
    center=None,
    *,
    projection="mercator",
    scale=1.0,
    offset=(0.0, 0.0),
    absolute=False,
    auto_scale_mercator=True,
    correct_grid_north=None,   # default: True для utm + center + not absolute
    rotation_deg=0.0,
    legacy=False,                # для тестов / не использовать в product
) -> tuple[float, float]
```

Если `center is None` и не `absolute` — origin = сама точка → `(0, 0)`.

### `from_xy(x, y, center, ...)`

Обратное преобразование (те же kwargs, без `absolute`).

### `to_xyz(..., z=0.0, offset=(0,0,0))`

XY + Z (z масштабируется `scale`, сдвигается `offset[2]`).

### Прочее

| Метод / свойство | Описание |
|------------------|----------|
| `distance_to(other)` | Haversine, **км** (R=6371). |
| `to_tuple()` / `to_list()` / `to_dict()` | `(lat,lon)` / list / `{"lat","lon"}`. |
| `utm_zone` | Номер зоны UTM по lon. |
| `meridian_convergence()` | Схождение меридиана (°), для UTM grid-north. |

## GeoPointArray

```python
arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
arr.append(GeoPoint(56, 38))
xy_list = arr.to_xy()              # center = centroid, mercator
xyz_list = arr.to_xyz(zs=[0, 10])
sw, ne = arr.bounds()
c = arr.center()
back = GeoPointArray.from_xy(xy_list, center=c)
```

`to_xy` / `from_xy` / `to_xyz` — те же параметры проекции, что у `GeoPoint`.

## Примеры

```python
origin = GeoPoint(55.75, 37.62)
p = GeoPoint(55.76, 37.63)

x, y = p.to_xy(center=origin)                              # mercator + cos
x, y = p.to_xy(center=origin, projection="local")          # ENU
x, y = p.to_xy(center=origin, auto_scale_mercator=False)
x, y = p.to_xy(absolute=True, auto_scale_mercator=False)
x, y = p.to_xy(center=origin, legacy=True)                 # для тестов / не использовать в product
x, y = p.to_xy(center=origin, projection="utm")            # нужен pyproj

back = GeoPoint.from_xy(x, y, center=origin)
print(p.distance_to(origin))
```
