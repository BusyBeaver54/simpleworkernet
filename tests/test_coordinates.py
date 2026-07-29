"""Тесты проекций GeoPoint / GeoPointArray (mercator — без pyproj)."""

import math

import pytest

from simpleworkernet.models.primitives import HAS_PYPROJ, GeoPoint, GeoPointArray


def test_utm_zone():
    assert GeoPoint(55.75, 37.62).utm_zone == 37
    assert GeoPoint(0.0, 0.0).utm_zone == 31


def test_meridian_convergence_near_central_meridian():
    # центр зоны 37: λ₀ = 39°
    p = GeoPoint(55.0, 39.0)
    assert abs(p.meridian_convergence()) < 0.05


def test_to_xy_mercator_absolute():
    x, y = GeoPoint(55.75, 37.62).to_xy(projection="mercator", absolute=True)
    assert x > 0 and y > 0


def test_to_xy_centered_mercator():
    origin = GeoPoint(55.75, 37.62)
    x, y = GeoPoint(55.76, 37.63).to_xy(center=origin, projection="mercator")
    assert abs(x) < 5000 and abs(y) < 5000


def test_from_xy_roundtrip_mercator():
    origin = GeoPoint(55.75, 37.62)
    target = GeoPoint(55.76, 37.63)
    xy = target.to_xy(center=origin, projection="mercator")
    back = GeoPoint.from_xy(*xy, center=origin, projection="mercator")
    assert abs(back.lat - target.lat) < 1e-5
    assert abs(back.lon - target.lon) < 1e-5


def test_to_xyz_mercator():
    x, y, z = GeoPoint(55.75, 37.62).to_xyz(
        z=10.0, projection="mercator", absolute=True
    )
    assert abs(z - 10.0) < 1e-9
    assert isinstance(x, float) and isinstance(y, float)


def test_geopoint_array_center_and_xy():
    arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
    c = arr.center()
    assert abs(c.lat - 56.0) < 1e-9
    assert abs(c.lon - 38.0) < 1e-9
    xy = arr.to_xy(center=c, projection="mercator")
    assert len(xy) == 2
    assert all(len(p) == 2 for p in xy)


def test_geopoint_array_from_xy_roundtrip():
    origin = GeoPoint(55.75, 37.62)
    arr = GeoPointArray([GeoPoint(55.75, 37.62), GeoPoint(55.76, 37.63)])
    xy = arr.to_xy(center=origin, projection="mercator")
    back = GeoPointArray.from_xy(xy, center=origin, projection="mercator")
    assert len(back) == 2
    assert abs(back[1].lat - 55.76) < 1e-5


def test_geopoint_array_bounds():
    arr = GeoPointArray([(55.0, 37.0), (57.0, 39.0)])
    sw, ne = arr.bounds()
    assert sw.lat == 55.0 and sw.lon == 37.0
    assert ne.lat == 57.0 and ne.lon == 39.0


def test_correct_grid_north_changes_angle_when_far_from_cm():
    """Вдали от центрального меридиана зоны поворот должен менять XY."""
    origin = GeoPoint(55.75, 30.0)  # зона 36, λ₀=33° — заметное γ
    p = GeoPoint(55.85, 30.2)
    xy0 = p.to_xy(center=origin, projection="mercator")  # mercator: флаг no-op
    # для mercator correct_grid_north не крутит — проверим только API
    xy1 = p.to_xy(center=origin, projection="mercator", correct_grid_north=True)
    assert xy0 == xy1

    if HAS_PYPROJ:
        a = p.to_xy(center=origin, projection="utm", correct_grid_north=False)
        b = p.to_xy(center=origin, projection="utm", correct_grid_north=True)
        # координаты должны отличаться при ненулевом γ
        assert math.hypot(a[0] - b[0], a[1] - b[1]) > 1.0


@pytest.mark.skipif(not HAS_PYPROJ, reason="pyproj not installed")
def test_utm_to_xy():
    x, y = GeoPoint(55.75, 37.62).to_xy(projection="utm", absolute=True)
    assert x > 0 and y > 0


@pytest.mark.skipif(HAS_PYPROJ, reason="pyproj is installed")
def test_utm_import_error_without_pyproj():
    with pytest.raises(ImportError):
        GeoPoint(55.75, 37.62).to_xy(projection="utm")
