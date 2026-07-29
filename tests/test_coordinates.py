"""Тесты координат (mercator — без pyproj)."""

import pytest

from simpleworkernet.utils.coordinates import (
    HAS_PYPROJ,
    auto_center,
    geo_to_xy,
    geo_to_xyz,
    lat_lon_to_xy,
    utm_zone,
)


def test_utm_zone():
    assert utm_zone(37.62) == 37  # Москва
    assert utm_zone(0.0) == 31


def test_lat_lon_to_xy_mercator():
    x, y = lat_lon_to_xy(55.75, 37.62, projection="mercator")
    assert isinstance(x, float) and isinstance(y, float)
    # Москва восточнее Гринвича и севернее экватора
    assert x > 0
    assert y > 0


def test_geo_to_xy_single_mercator():
    xy = geo_to_xy("55.75, 37.62", projection="mercator")
    assert len(xy) == 2
    assert all(isinstance(v, float) for v in xy)


def test_geo_to_xy_list_mercator():
    pts = geo_to_xy([(55.75, 37.62), (55.76, 37.63)], projection="mercator")
    assert len(pts) == 2
    assert len(pts[0]) == 2


def test_geo_to_xy_centered_mercator():
    xy = geo_to_xy(
        (55.76, 37.63),
        center=(55.75, 37.62),
        projection="mercator",
    )
    assert len(xy) == 2
    # относительно центра — небольшие смещения
    assert abs(xy[0]) < 5000
    assert abs(xy[1]) < 5000


def test_geo_to_xyz_mercator():
    xyz = geo_to_xyz((55.75, 37.62, 10.0), projection="mercator")
    assert len(xyz) == 3
    assert abs(xyz[2] - 10.0) < 1e-6


def test_auto_center():
    lat, lon = auto_center([(55.0, 37.0), (57.0, 39.0)])
    assert abs(lat - 56.0) < 1e-9
    assert abs(lon - 38.0) < 1e-9


def test_parse_dict():
    xy = geo_to_xy({"lat": 55.75, "lon": 37.62}, projection="mercator")
    assert len(xy) == 2


@pytest.mark.skipif(not HAS_PYPROJ, reason="pyproj not installed")
def test_utm_requires_pyproj():
    xy = geo_to_xy((55.75, 37.62), projection="utm")
    assert len(xy) == 2


@pytest.mark.skipif(HAS_PYPROJ, reason="pyproj is installed")
def test_utm_import_error_without_pyproj():
    with pytest.raises(ImportError):
        geo_to_xy((55.75, 37.62), projection="utm")
