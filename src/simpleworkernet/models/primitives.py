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
        lat_rad, lon_rad = math.radians(lat), math.radians(lon)
        x = _MERCATOR_RADIUS * lon_rad
        y = _MERCATOR_RADIUS * math.log(math.tan(math.pi / 4 + lat_rad / 2))
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
        lon = (mx / _MERCATOR_RADIUS) * 180.0 / math.pi
        lat = (
            2.0 * math.atan(math.exp(my / _MERCATOR_RADIUS)) - math.pi / 2.0
        ) * 180.0 / math.pi
        return float(lat), float(lon)
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


def _effective_scale(
    scale: float,
    projection: str,
    center_lat: Optional[float],
    auto_scale_mercator: bool,
) -> float:
    if (
        projection == "mercator"
        and auto_scale_mercator
        and center_lat is not None
    ):
        return scale / math.cos(math.radians(float(center_lat)))
    return scale


@smart_model
class GeoPoint(BaseModel):
    """
    WGS84 + проекции в плоские XY (метры).

    По умолчанию projection="local" (East/North, Y = истинный север).
    """

    lat: float
    lon: float

    def __init__(self, *args, **kwargs):
        lat: Any = None
        lon: Any = None

        if len(args) == 1:
            arg = args[0]
            if isinstance(arg, GeoPoint):
                lat, lon = arg.lat, arg.lon
            elif isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)) and len(arg) >= 2:
                lat, lon = arg[0], arg[1]
            elif isinstance(arg, str):
                parts = [
                    p.strip()
                    for p in arg.replace(";", ",").replace(" ", ",").split(",")
                    if p.strip()
                ]
                if len(parts) >= 2:
                    lat, lon = parts[0], parts[1]
                else:
                    raise ValueError(f"Не удалось разобрать координаты: {arg!r}")
            elif isinstance(arg, dict):
                lat = arg.get("lat", arg.get("latitude"))
                lon = arg.get("lon", arg.get("longitude"))
            else:
                raise TypeError(f"Неподдерживаемый тип для GeoPoint: {type(arg)!r}")
        elif len(args) >= 2:
            lat, lon = args[0], args[1]
        else:
            lat = kwargs.get("lat", kwargs.get("latitude"))
            lon = kwargs.get("lon", kwargs.get("longitude"))

        super().__init__(lat=_as_float(lat, "lat"), lon=_as_float(lon, "lon"))
        self._validate()

    def _validate(self) -> None:
        lat = getattr(self, "lat", None)
        lon = getattr(self, "lon", None)
        if lat is None or lon is None:
            return
        try:
            lat_f, lon_f = float(lat), float(lon)
        except (TypeError, ValueError):
            return
        if not (-90.0 <= lat_f <= 90.0):
            log.warning(f"Широта {lat_f} вне [-90, 90]")
        if not (-180.0 <= lon_f <= 180.0):
            log.warning(f"Долгота {lon_f} вне [-180, 180]")

    def to_tuple(self) -> Tuple[float, float]:
        return (float(self.lat), float(self.lon))

    def to_list(self) -> List[float]:
        return [float(self.lat), float(self.lon)]

    def to_dict(self) -> dict:
        return {"lat": float(self.lat), "lon": float(self.lon)}

    def distance_to(self, other: "GeoPoint") -> float:
        R = 6371.0
        lat1, lon1 = math.radians(float(self.lat)), math.radians(float(self.lon))
        lat2, lon2 = math.radians(float(other.lat)), math.radians(float(other.lon))
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))

    @property
    def utm_zone(self) -> int:
        return _utm_zone(float(self.lon))

    def meridian_convergence(self) -> float:
        lam0 = _utm_central_meridian(self.utm_zone)
        return (float(self.lon) - lam0) * math.sin(math.radians(float(self.lat)))

    def to_xy(
        self,
        center: Optional[Any] = None,
        *,
        projection: str = "local",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        absolute: bool = False,
        auto_scale_mercator: bool = True,
        correct_grid_north: Optional[bool] = None,
        rotation_deg: float = 0.0,
    ) -> Tuple[float, float]:
        if projection == "local" and center is None:
            center = self

        c = GeoPoint(center) if center is not None else None

        if correct_grid_north is None:
            correct_grid_north = projection == "utm" and c is not None and not absolute

        origin_lat = float(c.lat) if c is not None else None
        origin_lon = float(c.lon) if c is not None else None

        eff_scale = _effective_scale(
            scale,
            projection,
            origin_lat if (c is not None and not absolute) else None,
            auto_scale_mercator,
        )

        if projection == "local":
            x, y = _project_latlon(
                float(self.lat),
                float(self.lon),
                projection="local",
                scale=eff_scale,
                offset=offset,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
            )
            if rotation_deg:
                x, y = _rotate2d(x, y, rotation_deg)
            return float(x), float(y)

        x, y = _project_latlon(
            float(self.lat),
            float(self.lon),
            projection=projection,
            scale=eff_scale,
            offset=offset,
        )

        if c is not None and not absolute:
            cx, cy = _project_latlon(
                float(c.lat),
                float(c.lon),
                projection=projection,
                scale=eff_scale,
                offset=offset,
            )
            x, y = x - cx, y - cy
            rot = rotation_deg
            if correct_grid_north and projection == "utm":
                rot = rot - c.meridian_convergence()
            x, y = _rotate2d(x, y, rot)
        elif rotation_deg:
            x, y = _rotate2d(x, y, rotation_deg)

        return float(x), float(y)

    def to_xyz(
        self,
        center: Optional[Any] = None,
        *,
        z: float = 0.0,
        projection: str = "local",
        scale: float = 1.0,
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        absolute: bool = False,
        auto_scale_mercator: bool = True,
        correct_grid_north: Optional[bool] = None,
        rotation_deg: float = 0.0,
    ) -> Tuple[float, float, float]:
        x, y = self.to_xy(
            center,
            projection=projection,
            scale=scale,
            offset=(offset[0], offset[1]),
            absolute=absolute,
            auto_scale_mercator=auto_scale_mercator,
            correct_grid_north=correct_grid_north,
            rotation_deg=rotation_deg,
        )
        return float(x), float(y), float(z) * scale + offset[2]

    @classmethod
    def from_xy(
        cls,
        x: float,
        y: float,
        center: Any,
        *,
        projection: str = "local",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        auto_scale_mercator: bool = True,
        correct_grid_north: Optional[bool] = None,
        rotation_deg: float = 0.0,
    ) -> "GeoPoint":
        c = cls(center)
        dx, dy = float(x), float(y)

        if correct_grid_north is None:
            correct_grid_north = projection == "utm"

        eff_scale = _effective_scale(
            scale, projection, float(c.lat), auto_scale_mercator
        )

        if projection == "local":
            dx, dy = _rotate2d(dx, dy, -rotation_deg)
            mx = (dx - offset[0]) / eff_scale
            my = (dy - offset[1]) / eff_scale
            lat, lon = _local_en_inverse(mx, my, float(c.lat), float(c.lon))
            return cls(lat, lon)

        rot = -rotation_deg
        if correct_grid_north and projection == "utm":
            rot = rot + c.meridian_convergence()
        dx, dy = _rotate2d(dx, dy, rot)

        cx, cy = _project_latlon(
            float(c.lat),
            float(c.lon),
            projection=projection,
            scale=eff_scale,
            offset=offset,
        )
        lat, lon = _unproject_xy(
            cx + dx,
            cy + dy,
            ref_lat=float(c.lat),
            ref_lon=float(c.lon),
            projection=projection,
            scale=eff_scale,
            offset=offset,
        )
        return cls(lat, lon)

    def __str__(self) -> str:
        return f"{self.lat},{self.lon}"

    def __repr__(self) -> str:
        return f"GeoPoint(lat={self.lat}, lon={self.lon})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, GeoPoint):
            try:
                return abs(float(self.lat) - float(other.lat)) < 1e-10 and abs(
                    float(self.lon) - float(other.lon)
                ) < 1e-10
            except (TypeError, ValueError):
                return False
        return False


class GeoPointArray:
    def __init__(self, points: Optional[Iterable[Any]] = None):
        self._points: List[GeoPoint] = []
        if points is not None:
            for p in points:
                self._points.append(p if isinstance(p, GeoPoint) else GeoPoint(p))

    def __len__(self) -> int:
        return len(self._points)

    def __iter__(self):
        return iter(self._points)

    def __getitem__(self, index):
        return self._points[index]

    def __repr__(self) -> str:
        return f"GeoPointArray({len(self._points)} points)"

    def append(self, point: Any) -> None:
        self._points.append(point if isinstance(point, GeoPoint) else GeoPoint(point))

    def extend(self, points: Iterable[Any]) -> None:
        for p in points:
            self.append(p)

    def to_list(self) -> List[GeoPoint]:
        return list(self._points)

    def center(self) -> GeoPoint:
        if not self._points:
            raise ValueError("Пустой GeoPointArray")
        n = len(self._points)
        return GeoPoint(
            sum(float(p.lat) for p in self._points) / n,
            sum(float(p.lon) for p in self._points) / n,
        )

    def to_xy(
        self,
        center: Optional[Any] = None,
        *,
        projection: str = "local",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        absolute: bool = False,
        auto_scale_mercator: bool = True,
        correct_grid_north: Optional[bool] = None,
        rotation_deg: float = 0.0,
    ) -> List[Tuple[float, float]]:
        c = center
        if c is None and not absolute and self._points:
            c = self.center()
        return [
            p.to_xy(
                c,
                projection=projection,
                scale=scale,
                offset=offset,
                absolute=absolute,
                auto_scale_mercator=auto_scale_mercator,
                correct_grid_north=correct_grid_north,
                rotation_deg=rotation_deg,
            )
            for p in self._points
        ]

    def to_xyz(
        self,
        center: Optional[Any] = None,
        *,
        zs: Optional[Sequence[float]] = None,
        default_z: float = 0.0,
        projection: str = "local",
        scale: float = 1.0,
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        **kwargs,
    ) -> List[Tuple[float, float, float]]:
        if zs is None:
            zs = [default_z] * len(self._points)
        if len(zs) != len(self._points):
            raise ValueError("Длина zs должна совпадать с числом точек")
        return [
            p.to_xyz(center, z=z, projection=projection, scale=scale, offset=offset, **kwargs)
            for p, z in zip(self._points, zs)
        ]

    @classmethod
    def from_xy(
        cls,
        xy_list: Sequence[Sequence[float]],
        center: Any,
        *,
        projection: str = "local",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        auto_scale_mercator: bool = True,
        correct_grid_north: Optional[bool] = None,
        rotation_deg: float = 0.0,
    ) -> "GeoPointArray":
        pts = [
            GeoPoint.from_xy(
                float(xy[0]),
                float(xy[1]),
                center,
                projection=projection,
                scale=scale,
                offset=offset,
                auto_scale_mercator=auto_scale_mercator,
                correct_grid_north=correct_grid_north,
                rotation_deg=rotation_deg,
            )
            for xy in xy_list
        ]
        return cls(pts)

    def bounds(self) -> Tuple[GeoPoint, GeoPoint]:
        if not self._points:
            raise ValueError("Пустой GeoPointArray")
        lats = [float(p.lat) for p in self._points]
        lons = [float(p.lon) for p in self._points]
        return GeoPoint(min(lats), min(lons)), GeoPoint(max(lats), max(lons))


class vPhoneNumber(str):
    def __new__(cls, value: Any) -> "vPhoneNumber":
        if value is None:
            value = ""
        instance = super().__new__(cls, str(value))
        instance._original = str(value)
        return instance

    def __init__(self, value: Any):
        self._digits = self._extract_digits()

    def _extract_digits(self) -> str:
        return "".join(filter(str.isdigit, self._original))

    @property
    def normalized(self) -> str:
        return self._digits

    @property
    def formatted(self) -> str:
        return self._original

    @property
    def international(self) -> Optional[str]:
        if len(self._digits) == 10:
            return f"+7{self._digits}"
        if len(self._digits) == 11 and self._digits.startswith("7"):
            return f"+{self._digits}"
        if len(self._digits) == 11 and self._digits.startswith("8"):
            return f"+7{self._digits[1:]}"
        return None

    def __repr__(self) -> str:
        return f"vPhoneNumber('{self._original}')"


class vINN(str):
    def __new__(cls, value: Any) -> "vINN":
        if value is None:
            value = ""
        return super().__new__(cls, str(value))

    def __init__(self, value: Any):
        self._digits = "".join(filter(str.isdigit, str(value)))

    @property
    def normalized(self) -> str:
        return self._digits

    @property
    def is_valid(self) -> bool:
        return len(self._digits) in (10, 12) and self._digits.isdigit()

    @property
    def is_legal(self) -> bool:
        return len(self._digits) == 10

    @property
    def is_individual(self) -> bool:
        return len(self._digits) == 12

    def __repr__(self) -> str:
        return f"vINN('{self._digits}')"


class vKPP(str):
    def __new__(cls, value: Any) -> "vKPP":
        if value is None:
            value = ""
        return super().__new__(cls, str(value))

    def __init__(self, value: Any):
        self._digits = "".join(filter(str.isdigit, str(value)))

    @property
    def normalized(self) -> str:
        return self._digits

    @property
    def is_valid(self) -> bool:
        return len(self._digits) == 9 and self._digits.isdigit()

    def __repr__(self) -> str:
        return f"vKPP('{self._digits}')"


class vSNILS(str):
    def __new__(cls, value: Any) -> "vSNILS":
        if value is None:
            value = ""
        return super().__new__(cls, str(value))

    def __init__(self, value: Any):
        self._digits = "".join(filter(str.isdigit, str(value)))

    @property
    def normalized(self) -> str:
        return self._digits

    @property
    def is_valid(self) -> bool:
        return len(self._digits) == 11 and self._digits.isdigit()

    @property
    def formatted(self) -> str:
        if len(self._digits) == 11:
            return (
                f"{self._digits[:3]}-{self._digits[3:6]}-"
                f"{self._digits[6:9]} {self._digits[9:]}"
            )
        return self._digits

    def __repr__(self) -> str:
        return f"vSNILS('{self._digits}')"


class vOGRN(str):
    def __new__(cls, value: Any) -> "vOGRN":
        if value is None:
            value = ""
        return super().__new__(cls, str(value))

    def __init__(self, value: Any):
        self._digits = "".join(filter(str.isdigit, str(value)))

    @property
    def normalized(self) -> str:
        return self._digits

    @property
    def is_valid(self) -> bool:
        return len(self._digits) in (13, 15) and self._digits.isdigit()

    @property
    def is_legal(self) -> bool:
        return len(self._digits) == 13

    @property
    def is_individual(self) -> bool:
        return len(self._digits) == 15

    def __repr__(self) -> str:
        return f"vOGRN('{self._digits}')"


@smart_model
class vMoney(BaseModel):
    amount: float
    currency: str = "RUB"

    def __init__(self, *args, **kwargs):
        if args and "amount" not in kwargs:
            kwargs["amount"] = args[0]
            if len(args) > 1 and "currency" not in kwargs:
                kwargs["currency"] = args[1]
        super().__init__(**kwargs)

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"

    def __repr__(self) -> str:
        return f"vMoney(amount={self.amount}, currency='{self.currency}')"

    def __add__(self, other: Union["vMoney", float, int]) -> "vMoney":
        if isinstance(other, vMoney):
            if other.currency != self.currency:
                raise ValueError(
                    f"Нельзя складывать разные валюты: {self.currency} и {other.currency}"
                )
            return vMoney(amount=self.amount + other.amount, currency=self.currency)
        return vMoney(amount=self.amount + float(other), currency=self.currency)

    def __sub__(self, other: Union["vMoney", float, int]) -> "vMoney":
        if isinstance(other, vMoney):
            if other.currency != self.currency:
                raise ValueError(
                    f"Нельзя вычитать разные валюты: {self.currency} и {other.currency}"
                )
            return vMoney(amount=self.amount - other.amount, currency=self.currency)
        return vMoney(amount=self.amount - float(other), currency=self.currency)

    def __mul__(self, other: Union[float, int]) -> "vMoney":
        return vMoney(amount=self.amount * float(other), currency=self.currency)

    def __truediv__(self, other: Union[float, int]) -> "vMoney":
        return vMoney(amount=self.amount / float(other), currency=self.currency)

    def to_dict(self, clear_meta: bool = True) -> dict:
        return {"amount": self.amount, "currency": self.currency}


class vPercent(float):
    def __new__(cls, value: Any) -> "vPercent":
        return super().__new__(cls, float(value))

    def __str__(self) -> str:
        return f"{self:.1f}%"

    def __repr__(self) -> str:
        return f"vPercent({super().__str__()})"

    def of(self, value: float) -> float:
        return (self / 100) * value

    def add_to(self, value: float) -> float:
        return value * (1 + self / 100)

    def subtract_from(self, value: float) -> float:
        return value * (1 - self / 100)


@smart_model
class vPeriod(BaseModel):
    start: str
    end: str

    def __post_init__(self):
        try:
            from datetime import datetime

            self._start_date = datetime.strptime(self.start, "%Y-%m-%d")
            self._end_date = datetime.strptime(self.end, "%Y-%m-%d")
            if self._start_date > self._end_date:
                log.warning(f"Начало периода {self.start} позже конца {self.end}")
        except (ValueError, TypeError) as e:
            log.warning(f"Ошибка парсинга дат периода: {e}")
            self._start_date = None
            self._end_date = None

    @property
    def days(self) -> Optional[int]:
        if self._start_date and self._end_date:
            return (self._end_date - self._start_date).days
        return None

    @property
    def months(self) -> Optional[float]:
        if self.days:
            return self.days / 30.44
        return None

    def contains(self, date: str) -> bool:
        try:
            from datetime import datetime

            check_date = datetime.strptime(date, "%Y-%m-%d")
            return self._start_date <= check_date <= self._end_date
        except (ValueError, TypeError, AttributeError):
            return False

    def __str__(self) -> str:
        return f"{self.start} - {self.end}"


additional_field = lambda x: f"additional_field_{x}"
additional_data = lambda x: f"additional_data{x}"

__all__ = [
    "vStr",
    "vFlag",
    "GeoPoint",
    "GeoPointArray",
    "HAS_PYPROJ",
    "vPhoneNumber",
    "vINN",
    "vKPP",
    "vSNILS",
    "vOGRN",
    "vMoney",
    "vPercent",
    "vPeriod",
    "additional_field",
    "additional_data",
]
