"""Тесты проекций GeoPoint / GeoPointArray."""

import math

import pytest

from simpleworkernet.models.primitives import (
    DEFAULT_PROJECTION,
    HAS_PYPROJ,
    GeoPoint,
    GeoPointArray,
)


def test_default_projection_is_mercator():
    assert DEFAULT_PROJECTION == "mercator"


def test_utm_zone():
    assert GeoPoint(55.75, 37.62).utm_zone == 37
    assert GeoPoint(0.0, 0.0).utm_zone == 31


def test_local_en_north_is_positive_y():
    origin = GeoPoint(55.75, 37.62)
    north = GeoPoint(55.76, 37.62)
    x, y = north.to_xy(center=origin, projection="local")
    assert abs(x) < 5
    assert y > 0


def test_local_en_east_is_positive_x():
    origin = GeoPoint(55.75, 37.62)
    east = GeoPoint(55.75, 37.63)
    x, y = east.to_xy(center=origin, projection="local")
    assert x > 0
    assert abs(y) < 5


def test_local_roundtrip():
    origin = GeoPoint(55.75, 37.62)
    target = GeoPoint(55.76, 37.63)
    xy = target.to_xy(center=origin, projection="local")
    back = GeoPoint.from_xy(*xy, center=origin, projection="local")
    assert abs(back.lat - target.lat) < 1e-6
    assert abs(back.lon - target.lon) < 1e-6


def test_to_xy_mercator_absolute():
    x, y = GeoPoint(55.75, 37.62).to_xy(projection="mercator", absolute=True)
    assert x > 0 and y > 0


def test_to_xy_default_is_relative_mercator():
    """Без center точка даёт (0, 0) — origin = self, projection=mercator."""
    x, y = GeoPoint(55.75, 37.62).to_xy()
    assert abs(x) < 1e-9 and abs(y) < 1e-9


def test_to_xy_centered_mercator():
    origin = GeoPoint(55.75, 37.62)
    x, y = GeoPoint(55.76, 37.63).to_xy(center=origin)
    assert abs(x) < 5000 and abs(y) < 5000


def test_from_xy_roundtrip_mercator():
    origin = GeoPoint(55.75, 37.62)
    target = GeoPoint(55.76, 37.63)
    xy = target.to_xy(center=origin)
    back = GeoPoint.from_xy(*xy, center=origin)
    assert abs(back.lat - target.lat) < 1e-5
    assert abs(back.lon - target.lon) < 1e-5


def test_mercator_auto_scale_matches_local():
    """
    auto_scale_mercator=True → relative delta × cos(lat),
    совпадает с local ENU на сфере R=6378137.
    Без коррекции raw mercator ≈ 1/cos(φ) раз больше.
    """
    origin = GeoPoint(55.75, 37.62)
    target = GeoPoint(55.76, 37.63)

    lx, ly = target.to_xy(center=origin, projection="local")
    mx, my = target.to_xy(center=origin, projection="mercator")
    mx_raw, my_raw = target.to_xy(
        center=origin, projection="mercator", auto_scale_mercator=False
    )

    d_local = math.hypot(lx, ly)
    d_merc = math.hypot(mx, my)
    d_raw = math.hypot(mx_raw, my_raw)

    assert abs(d_merc - d_local) / d_local < 0.001  # < 0.1 %
    assert d_raw / d_local > 1.5


def test_mercator_origin_stays_zero():
    """Центр в relative mercator всегда (0, 0) — без фиктивного сдвига."""
    origin = GeoPoint(55.75, 37.62)
    x, y = origin.to_xy(center=origin)
    assert abs(x) < 1e-9 and abs(y) < 1e-9


def test_to_xyz_local():
    origin = GeoPoint(55.75, 37.62)
    x, y, z = GeoPoint(55.75, 37.62).to_xyz(
        center=origin, z=10.0, projection="local"
    )
    assert abs(x) < 1e-6 and abs(y) < 1e-6
    assert abs(z - 10.0) < 1e-9


def test_geopoint_array_default_mercator():
    arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
    c = arr.center()
    xy = arr.to_xy(center=c)
    assert len(xy) == 2
    back = GeoPointArray.from_xy(xy, center=c)
    assert abs(back[0].lat - 55.0) < 1e-5


def test_geopoint_array_local():
    arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
    c = arr.center()
    xy = arr.to_xy(center=c, projection="local")
    assert len(xy) == 2
    back = GeoPointArray.from_xy(xy, center=c, projection="local")
    assert abs(back[0].lat - 55.0) < 1e-5


def test_geopoint_array_bounds():
    arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
    sw, ne = arr.bounds()
    assert sw.lat == 55.0 and ne.lat == 57.0


@pytest.mark.skipif(not HAS_PYPROJ, reason="pyproj not installed")
def test_utm_with_default_grid_north_correction():
    origin = GeoPoint(55.75, 30.0)
    p = GeoPoint(55.85, 30.2)
    a = p.to_xy(center=origin, projection="utm")
    b = p.to_xy(center=origin, projection="utm", correct_grid_north=False)
    assert math.hypot(a[0] - b[0], a[1] - b[1]) > 1.0


@pytest.mark.skipif(HAS_PYPROJ, reason="pyproj is installed")
def test_utm_import_error_without_pyproj():
    with pytest.raises(ImportError):
        GeoPoint(55.75, 37.62).to_xy(projection="utm", absolute=True)
