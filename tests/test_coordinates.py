"""Тесты проекций GeoPoint / GeoPointArray."""

import math

import pytest

from simpleworkernet.models.primitives import HAS_PYPROJ, GeoPoint, GeoPointArray


def test_utm_zone():
    assert GeoPoint(55.75, 37.62).utm_zone == 37
    assert GeoPoint(0.0, 0.0).utm_zone == 31


def test_local_en_north_is_positive_y():
    origin = GeoPoint(55.75, 37.62)
    north = GeoPoint(55.76, 37.62)  # севернее, та же долгота
    x, y = north.to_xy(center=origin)  # default local
    assert abs(x) < 5  # почти на одной меридиане
    assert y > 0  # север = +Y


def test_local_en_east_is_positive_x():
    origin = GeoPoint(55.75, 37.62)
    east = GeoPoint(55.75, 37.63)  # восточнее, та же широта
    x, y = east.to_xy(center=origin)
    assert x > 0
    assert abs(y) < 5


def test_local_roundtrip():
    origin = GeoPoint(55.75, 37.62)
    target = GeoPoint(55.76, 37.63)
    xy = target.to_xy(center=origin)
    back = GeoPoint.from_xy(*xy, center=origin)
    assert abs(back.lat - target.lat) < 1e-6
    assert abs(back.lon - target.lon) < 1e-6


def test_to_xy_mercator_absolute():
    x, y = GeoPoint(55.75, 37.62).to_xy(projection="mercator", absolute=True)
    assert x > 0 and y > 0


def test_to_xy_centered_mercator():
    origin = GeoPoint(55.75, 37.62)
    x, y = GeoPoint(55.76, 37.63).to_xy(
        center=origin, projection="mercator"
    )
    assert abs(x) < 5000 and abs(y) < 5000


def test_from_xy_roundtrip_mercator():
    origin = GeoPoint(55.75, 37.62)
    target = GeoPoint(55.76, 37.63)
    xy = target.to_xy(center=origin, projection="mercator")
    back = GeoPoint.from_xy(*xy, center=origin, projection="mercator")
    assert abs(back.lat - target.lat) < 1e-5
    assert abs(back.lon - target.lon) < 1e-5


def test_to_xyz_local():
    origin = GeoPoint(55.75, 37.62)
    x, y, z = GeoPoint(55.75, 37.62).to_xyz(center=origin, z=10.0)
    assert abs(x) < 1e-6 and abs(y) < 1e-6
    assert abs(z - 10.0) < 1e-9


def test_geopoint_array_local():
    arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
    c = arr.center()
    xy = arr.to_xy(center=c)  # local
    assert len(xy) == 2
    back = GeoPointArray.from_xy(xy, center=c)
    assert abs(back[0].lat - 55.0) < 1e-5


def test_geopoint_array_bounds():
    arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
    sw, ne = arr.bounds()
    assert sw.lat == 55.0 and ne.lat == 57.0


@pytest.mark.skipif(not HAS_PYPROJ, reason="pyproj not installed")
def test_utm_with_default_grid_north_correction():
    origin = GeoPoint(55.75, 30.0)
    p = GeoPoint(55.85, 30.2)
    # по умолчанию correct_grid_north=True для utm+center
    a = p.to_xy(center=origin, projection="utm")
    b = p.to_xy(center=origin, projection="utm", correct_grid_north=False)
    assert math.hypot(a[0] - b[0], a[1] - b[1]) > 1.0


@pytest.mark.skipif(HAS_PYPROJ, reason="pyproj is installed")
def test_utm_import_error_without_pyproj():
    with pytest.raises(ImportError):
        GeoPoint(55.75, 37.62).to_xy(projection="utm", absolute=True)
