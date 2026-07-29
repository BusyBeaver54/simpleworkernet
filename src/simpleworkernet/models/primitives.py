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

# Радиус сферы Web Mercator (EPSG:3857)
_MERCATOR_RADIUS = 6378137.0


class vStr(str):
    """Строка с URL/HTML-декодированием."""

    def __new__(cls, value: Any) -> "vStr":
        if value is None:
            value = ""
        decoded = unquote_plus(
            string=html.unescape(str(value)),
            encoding="utf-8",
        )
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
        raise ImportError(
            "Для проекции UTM нужен pyproj: pip install pyproj"
        )
    zone = _utm_zone(lon)
    hemisphere = "north" if lat >= 0 else "south"
    proj_str = (
        f"+proj=utm +zone={zone} +{hemisphere} "
        f"+ellps=WGS84 +datum=WGS84 +units=m +no_defs"
    )
    return pyproj.Transformer.from_crs("EPSG:4326", proj_str, always_xy=True)


def _project_latlon(
    lat: float,
    lon: float,
    *,
    projection: str = "utm",
    scale: float = 1.0,
    offset: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float]:
    if projection == "utm":
        transformer = _get_utm_transformer(lat, lon)
        x, y = transformer.transform(lon, lat)
    elif projection == "mercator":
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        x = _MERCATOR_RADIUS * lon_rad
        y = _MERCATOR_RADIUS * math.log(math.tan(math.pi / 4 + lat_rad / 2))
    else:
        raise ValueError(f"Неизвестная проекция: {projection!r} (utm|mercator)")
    return x * scale + offset[0], y * scale + offset[1]


def _unproject_xy(
    x: float,
    y: float,
    *,
    ref_lat: float,
    ref_lon: float,
    projection: str = "utm",
    scale: float = 1.0,
    offset: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float]:
    mx = (x - offset[0]) / scale
    my = (y - offset[1]) / scale
    if projection == "utm":
        transformer = _get_utm_transformer(ref_lat, ref_lon)
        lon, lat = transformer.transform(mx, my, direction="INVERSE")
        return float(lat), float(lon)
    if projection == "mercator":
        lon = (mx / _MERCATOR_RADIUS) * 180.0 / math.pi
        lat = (
            2.0 * math.atan(math.exp(my / _MERCATOR_RADIUS)) - math.pi / 2.0
        ) * 180.0 / math.pi
        return float(lat), float(lon)
    raise ValueError(f"Неизвестная проекция: {projection!r}")


def _rotate2d(
    x: float, y: float, angle_deg: float
) -> Tuple[float, float]:
    """Поворот вокруг (0,0): положительный angle — против часовой (математический)."""
    if abs(angle_deg) < 1e-15:
        return x, y
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


@smart_model
class GeoPoint(BaseModel):
    """
    Географические координаты WGS84 (широта, долгота) + проекции в плоские XY.

    Инициализация:
        GeoPoint(55.75, 37.62)
        GeoPoint([55.75, 37.62]) / GeoPoint((55.75, 37.62))
        GeoPoint("55.75,37.62")
        GeoPoint(lat=55.75, lon=37.62)

    Плоские координаты (метры):
        pt.to_xy()                         # абсолютные UTM (нужен pyproj)
        pt.to_xy(center=origin)            # локальные относительно origin
        pt.to_xy(projection="mercator")    # без pyproj
        GeoPoint.from_xy(x, y, center=origin)

    Наклон относительно карты в AutoCAD
    -------------------------------------
    Часто объекты «чуть повёрнуты» относительно подложки карты. Типичные причины:

    1. **Схождение меридианов (grid north ≠ true north)**.
       В UTM оси параллельны центральному меридиану зоны, а не географическому
       северу в точке. Угол γ ≈ (λ − λ₀)·sin(φ). Чем дальше от центра зоны и
       чем севернее — тем заметнее. На карте с ориентацией «вверх = север»
       UTM-локальная система выглядит наклонённой.
       Решение: ``to_xy(..., correct_grid_north=True)`` — поворот на −γ
       вокруг центра, чтобы ось Y совпала с истинным севером.

    2. **Разная CRS у точек и подложки** (UTM-точки на Web Mercator / гео-карте).

    3. **Project / plant north** в чертеже (локальный поворот стройплощадки).

    4. **Оси**: UTM даёт (Easting, Northing) = (X, Y). В CAD иногда путают
       X/Y или «север вверх» с «север = −Y».

    5. Масштаб UTM (k₀=0.9996) и отсутствие единой точки привязки (center).
    """

    lat: float
    lon: float

    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            arg = args[0]
            if isinstance(arg, Sequence) and not isinstance(arg, (str, bytes)) and len(arg) == 2:
                super().__init__(lat=float(arg[0]), lon=float(arg[1]))
                self._validate()
                return
            if isinstance(arg, str):
                parts = [p.strip() for p in arg.replace(";", ",").split(",")]
                if len(parts) == 2:
                    super().__init__(lat=float(parts[0]), lon=float(parts[1]))
                    self._validate()
                    return
            if isinstance(arg, dict):
                lat = arg.get("lat", arg.get("latitude"))
                lon = arg.get("lon", arg.get("longitude"))
                super().__init__(lat=float(lat), lon=float(lon))
                self._validate()
                return
        if len(args) == 2:
            super().__init__(lat=float(args[0]), lon=float(args[1]))
            self._validate()
            return
        super().__init__(*args, **kwargs)
        self._validate()

    def _validate(self) -> None:
        if not -90 <= self.lat <= 90:
            log.warning(f"Широта {self.lat} вне [-90, 90]")
        if not -180 <= self.lon <= 180:
            log.warning(f"Долгота {self.lon} вне [-180, 180]")

    # --- базовые представления ---

    def to_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lon)

    def to_list(self) -> List[float]:
        return [self.lat, self.lon]

    def to_dict(self) -> dict:
        return {"lat": self.lat, "lon": self.lon}

    def distance_to(self, other: "GeoPoint") -> float:
        """Расстояние по гаверсинусу, км."""
        R = 6371.0
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lon)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))

    # --- UTM / проекции ---

    @property
    def utm_zone(self) -> int:
        return _utm_zone(self.lon)

    def meridian_convergence(self) -> float:
        """
        Приближённый угол схождения меридианов γ (градусы).

        γ ≈ (λ − λ₀) · sin(φ), где λ₀ — центральный меридиан UTM-зоны.
        Положительный γ: grid north восточнее true north.
        """
        zone = self.utm_zone
        lam0 = _utm_central_meridian(zone)
        return (self.lon - lam0) * math.sin(math.radians(self.lat))

    def to_xy(
        self,
        center: Optional[Any] = None,
        *,
        projection: str = "utm",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        absolute: bool = False,
        auto_scale_mercator: bool = True,
        correct_grid_north: bool = False,
        rotation_deg: float = 0.0,
    ) -> Tuple[float, float]:
        """
        WGS84 → плоские (x, y) в метрах.

        Args:
            center: точка привязки (GeoPoint / (lat,lon) / …). Если задана и
                absolute=False — результат относительно center.
            projection: ``"utm"`` (pyproj) или ``"mercator"``.
            scale / offset: масштаб и смещение после проекции.
            absolute: игнорировать центрирование даже при заданном center.
            auto_scale_mercator: 1/cos(φ) для mercator при центрировании.
            correct_grid_north: повернуть локальные координаты на −γ
                (выравнивание оси Y с истинным севером — для CAD/карты).
            rotation_deg: дополнительный поворот (°, против часовой),
                например project north.

        Returns:
            (x, y) — для UTM это (easting, northing) или смещения от center.
        """
        c = GeoPoint(center) if center is not None else None

        eff_scale = scale
        if (
            c is not None
            and not absolute
            and projection == "mercator"
            and auto_scale_mercator
        ):
            eff_scale = scale / math.cos(math.radians(c.lat))

        x, y = _project_latlon(
            self.lat, self.lon, projection=projection, scale=eff_scale, offset=offset
        )

        if c is not None and not absolute:
            cx, cy = _project_latlon(
                c.lat, c.lon, projection=projection, scale=eff_scale, offset=offset
            )
            x, y = x - cx, y - cy

            rot = rotation_deg
            if correct_grid_north and projection == "utm":
                # Выровнять локальную систему с true north
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
        projection: str = "utm",
        scale: float = 1.0,
        offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        absolute: bool = False,
        auto_scale_mercator: bool = True,
        correct_grid_north: bool = False,
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
        z_out = z * scale + offset[2]
        if center is not None and not absolute:
            # z относительно центра не вычитаем, если у center нет высоты
            pass
        return float(x), float(y), float(z_out)

    @classmethod
    def from_xy(
        cls,
        x: float,
        y: float,
        center: Any,
        *,
        projection: str = "utm",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        correct_grid_north: bool = False,
        rotation_deg: float = 0.0,
    ) -> "GeoPoint":
        """
        Плоские (x, y) относительно center → GeoPoint.

        Параметры correct_grid_north / rotation_deg должны совпадать с to_xy.
        """
        c = cls(center)
        dx, dy = float(x), float(y)

        rot = -rotation_deg
        if correct_grid_north and projection == "utm":
            rot = rot + c.meridian_convergence()
        dx, dy = _rotate2d(dx, dy, rot)

        cx, cy = _project_latlon(
            c.lat, c.lon, projection=projection, scale=scale, offset=offset
        )
        lat, lon = _unproject_xy(
            cx + dx,
            cy + dy,
            ref_lat=c.lat,
            ref_lon=c.lon,
            projection=projection,
            scale=scale,
            offset=offset,
        )
        return cls(lat, lon)

    def __str__(self) -> str:
        return f"{self.lat},{self.lon}"

    def __repr__(self) -> str:
        return f"GeoPoint(lat={self.lat}, lon={self.lon})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, GeoPoint):
            return abs(self.lat - other.lat) < 1e-10 and abs(self.lon - other.lon) < 1e-10
        return False


class GeoPointArray:
    """
    Список GeoPoint с пакетными проекциями.

    >>> arr = GeoPointArray([(55.75, 37.62), (55.76, 37.63)])
    >>> arr.to_xy(center=arr.center())
    >>> GeoPointArray.from_xy([[0, 0], [100, 50]], center=origin)
    """

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
        """Среднее арифметическое lat/lon (достаточно для локальной привязки)."""
        if not self._points:
            raise ValueError("Пустой GeoPointArray")
        n = len(self._points)
        return GeoPoint(
            sum(p.lat for p in self._points) / n,
            sum(p.lon for p in self._points) / n,
        )

    def to_xy(
        self,
        center: Optional[Any] = None,
        *,
        projection: str = "utm",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        absolute: bool = False,
        auto_scale_mercator: bool = True,
        correct_grid_north: bool = False,
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
        projection: str = "utm",
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
        projection: str = "utm",
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
        correct_grid_north: bool = False,
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
                correct_grid_north=correct_grid_north,
                rotation_deg=rotation_deg,
            )
            for xy in xy_list
        ]
        return cls(pts)

    def bounds(self) -> Tuple[GeoPoint, GeoPoint]:
        """(юго-запад, северо-восток) по lat/lon."""
        if not self._points:
            raise ValueError("Пустой GeoPointArray")
        lats = [p.lat for p in self._points]
        lons = [p.lon for p in self._points]
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
