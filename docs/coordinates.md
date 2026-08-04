# Координаты

`GeoPoint` / `GeoPointArray` — WGS84 и проекции в плоские метры.

**По умолчанию:** `projection="mercator"` (Web Mercator).

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

1. считаются «сырые» mercator-координаты точки и центра;
2. берётся **разность** (delta);
3. delta умножается на `cos(center.lat)`.

Так центр остаётся точно `(0, 0)`, без фиктивного сдвига, а расстояния
на субкилометровых базисах совпадают с `projection="local"` (сфера R=6378137)
с точностью ≪ 0.1 %.

Для подложки тайлов OSM/Google используйте `absolute=True` и
`auto_scale_mercator=False` (сырые EPSG:3857-метры).

## Legacy AUTOCAD

`legacy=True` — совместимость со старым AUTOCAD GPS (`TO_KM ≈ 0.6194 ≈ cos(51.73°)`):
абсолютные mercator-координаты умножаются на фиксированный коэффициент
вместо relative × cos(lat).

Константа: `LEGACY_TO_KM = 0.6194`.

## Примеры

```python
from simpleworkernet import GeoPoint, GeoPointArray

origin = GeoPoint(55.75, 37.62)
p = GeoPoint(55.76, 37.63)

# default: mercator relative + metric scale
x, y = p.to_xy(center=origin)

# local ENU (строго East/North)
x, y = p.to_xy(center=origin, projection="local")

# сырой mercator (для тайлов), без ×cos
x, y = p.to_xy(center=origin, auto_scale_mercator=False)

# абсолютный mercator (EPSG:3857-like)
x, y = p.to_xy(absolute=True, auto_scale_mercator=False)

# legacy AUTOCAD
x, y = p.to_xy(center=origin, legacy=True)

# UTM
x, y = p.to_xy(center=origin, projection="utm")  # нужен pyproj

back = GeoPoint.from_xy(x, y, center=origin)

arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
xy_list = arr.to_xy()          # center = centroid, mercator
sw, ne = arr.bounds()
print(p.distance_to(origin))   # км (haversine)
```

Доп. параметры: `scale`, `offset`, `rotation_deg`, `absolute`,
`correct_grid_north` (UTM), `legacy`.
