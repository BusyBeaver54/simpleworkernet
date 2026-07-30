# simpleworkernet/models/primitives.py
"""
Примитивные типы данных для SimpleWorkerNet
"""
from __future__ import annotations

import html
import math
from enum import IntFlag
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union
from urllib.parse import unquote_plus

from .base import BaseModel, smart_model
from ..core.logger import log

try:
    import pyproj

    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

_MERCATOR_RADIUS = 6378137.0
_EARTH_RADIUS = 6378137.0

# Default planar projection for to_xy / from_xy / GeoPointArray.
DEFAULT_PROJECTION = "mercator"

# Fixed scale used by legacy AUTOCAD GPS (≈ cos(51.73°)).
# With legacy=True, absolute mercator coordinates are multiplied by this
# constant (old TO_KM behaviour) instead of relative cos(lat) correction.
LEGACY_TO_KM = 0.6194


class vStr(str):
    def __new__(cls, value: Any) -> "vStr":
        if value is None:
            value = ""
        decoded = unquote_plus(string=html.unescape(str(value)), encoding="utf-8")
        return super().__new__(cls, decoded)

    def __repr__(self) -> str:
        return f"vStr('{super().__str__()}')"

    def __add__(self, other: Any) -> "vStr":
        return vStr(super().__str__() + str(other))

    def __radd__(self, other: Any) -> "vStr":
        return vStr(str(other) + super().__str__())


class vFlag(IntFlag):
    v0 = 0
    v1 = 1

    @classmethod
    def from_bool(cls, value: bool) -> "vFlag":
        return cls.v1 if value else cls.v0

    def to_bool(self) -> bool:
        return bool(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"vFlag.{self.name if self.value else 'v0'}"


def _utm_zone(lon: float) -> int:
    return int((lon + 180) / 6) + 1


def _utm_central_meridian(zone: int) -> float:
    return zone * 6 - 183


def _get_utm_transformer(lat: float, lon: float):
    if not HAS_PYPROJ:
        raise ImportError("Для проекции UTM нужен pyproj: pip install pyproj")
    zone = _utm_zone(lon)
    hemisphere = "north" if lat >= 0 else "south"
    proj_str = (
        f"+proj=utm +zone={zone} +{hemisphere} "
        f"+ellps=WGS84 +datum=WGS84 +units=m +no_defs"
    )
    return pyproj.Transformer.from_crs("EPSG:4326", proj_str, always_xy=True)


def _local_en(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    lat_r, lon_r = math.radians(lat), math.radians(lon)
    lat0_r, lon0_r = math.radians(lat0), math.radians(lon0)
    x = _EARTH_RADIUS * (lon_r - lon0_r) * math.cos(lat0_r)
    y = _EARTH_RADIUS * (lat_r - lat0_r)
    return x, y


def _local_en_inverse(x: float, y: float, lat0: float, lon0: float) -> Tuple[float, float]:
    lat0_r = math.radians(lat0)
    lat = lat0 + math.degrees(y / _EARTH_RADIUS)
    lon = lon0 + math.degrees(x / (_EARTH_RADIUS * math.cos(lat0_r)))
    return lat, lon


def _mercator_raw(lat: float, lon: float) -> Tuple[float, float]:
    """Spherical Web Mercator (EPSG:3857-like), metres, no scale correction."""
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    # clamp for numerical stability near poles
    lat_rad = max(min(lat_rad, math.radians(85.05112878)), math.radians(-85.05112878))
    x = _MERCATOR_RADIUS * lon_rad
    y = _MERCATOR_RADIUS * math.log(math.tan(math.pi / 4.0 + lat_rad / 2.0))
    return x, y


def _mercator_raw_inverse(x: float, y: float) -> Tuple[float, float]:
    lon = (x / _MERCATOR_RADIUS) * 180.0 / math.pi
    lat = (
        2.0 * math.atan(math.exp(y / _MERCATOR_RADIUS)) - math.pi / 2.0
    ) * 180.0 / math.pi
    return float(lat), float(lon)


def _project_latlon(
    lat: float,
    lon: float,
    *,
    projection: str = "local",
    scale: float = 1.0,
    offset: Tuple[float, float] = (0.0, 0.0),
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
) -> Tuple[float, float]:
    if projection == "local":
        if origin_lat is None or origin_lon is None:
            raise ValueError("projection='local' требует origin (center)")
        x, y = _local_en(lat, lon, origin_lat, origin_lon)
    elif projection == "utm":
        x, y = _get_utm_transformer(lat, lon).transform(lon, lat)
    elif projection == "mercator":
        x, y = _mercator_raw(lat, lon)
    else:
        raise ValueError(f"Неизвестная проекция: {projection!r} (local|utm|mercator)")
    return x * scale + offset[0], y * scale + offset[1]


def _unproject_xy(
    x: float,
    y: float,
    *,
    ref_lat: float,
    ref_lon: float,
    projection: str = "local",
    scale: float = 1.0,
    offset: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float]:
    mx = (x - offset[0]) / scale
    my = (y - offset[1]) / scale
    if projection == "local":
        return _local_en_inverse(mx, my, ref_lat, ref_lon)
    if projection == "utm":
        lon, lat = _get_utm_transformer(ref_lat, ref_lon).transform(
            mx, my, direction="INVERSE"
        )
        return float(lat), float(lon)
    if projection == "mercator":
        return _mercator_raw_inverse(mx, my)
    raise ValueError(f"Неизвестная проекция: {projection!r}")


def _rotate2d(x: float, y: float, angle_deg: float) -> Tuple[float, float]:
    if abs(angle_deg) < 1e-15:
        return x, y
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def _as_float(value: Any, name: str) -> float:
    if value is None:
        raise TypeError(f"GeoPoint.{name} не может быть None")
    return float(value)


def _mercator_metric_scale(center_lat: float) -> float:
    """
    Web Mercator overstates ground distances by sec(φ) = 1/cos(φ).

    Multiply *relative* mercator deltas by cos(center_lat) to get
    approximate true metres near the origin (matches local ENU on
    sphere R=6378137 within ~0.01 % on sub-km baselines).
    """
    return math.cos(math.radians(float(center_lat)))
