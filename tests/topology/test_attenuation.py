"""Unit-тесты каталога и длины (без live API / без igraph path)."""

from types import SimpleNamespace

import pytest

from simpleworkernet.models.primitives import GeoPoint
from simpleworkernet.utils.topology.attenuation import (
    AttenuationCatalog,
    PathReport,
)
from simpleworkernet.utils.topology.attenuation.length import (
    path_length_m,
    resolve_fiber_length_m,
)
from simpleworkernet.utils.topology.attenuation.models import AttenuationSegment


def test_catalog_defaults():
    cat = AttenuationCatalog.with_defaults()
    assert cat.fiber_db_per_km(1550) == pytest.approx(0.22)
    assert cat.fiber_db_per_km(1310) == pytest.approx(0.35)
    assert cat.splice_db() > 0
    assert cat.adapter_db() > 0


def test_catalog_force_fiber():
    cat = AttenuationCatalog.with_defaults()
    cat.force_fiber(100, 0.5)
    assert cat.forced_fiber_db_per_km(100) == 0.5
    assert cat.forced_fiber_db_per_km(999) is None


def test_catalog_splitter_ratio():
    cat = AttenuationCatalog.with_defaults()
    db, src = cat.splitter_port_db(ratio_key="1x2_5/95", port=1, port_count_out=2)
    assert src == "ratio"
    assert db > 10  # leg 5%
    db2, src2 = cat.splitter_port_db(ratio_key="1x2_5/95", port=2, port_count_out=2)
    assert db2 < 2  # leg 95%


def test_catalog_splitter_estimated():
    cat = AttenuationCatalog.with_defaults()
    db, src = cat.splitter_port_db(port=1, port_count_out=8)
    assert src == "estimated"
    assert db > 9  # ~10.5 theoretical + excess


def test_catalog_json_roundtrip(tmp_path):
    cat = AttenuationCatalog.with_defaults()
    cat.set_cable(12, name="OKL", db_per_km={1310: 0.4, 1550: 0.25})
    path = tmp_path / "att.json"
    cat.save(path)
    loaded = AttenuationCatalog.from_json(path)
    assert loaded.cable_db_per_km(12, 1550) == pytest.approx(0.25)


def test_resolve_length_opticalen2():
    obj = SimpleNamespace(opticalen2=1200, opticalen=1000, path=None)
    L, src = resolve_fiber_length_m(obj)
    assert L == 1200 and src == "opticalen2"


def test_resolve_length_opticalen():
    obj = SimpleNamespace(opticalen2=0, opticalen=800, path=None)
    L, src = resolve_fiber_length_m(obj)
    assert L == 800 and src == "opticalen"


def test_resolve_length_geo_path():
    path = [GeoPoint(55.75, 37.60), GeoPoint(55.76, 37.60)]
    obj = SimpleNamespace(opticalen2=None, opticalen=None, path=path)
    L, src = resolve_fiber_length_m(obj, slack_k=1.0)
    assert src == "geo"
    assert L is not None and L > 1000  # ~1.1 km


def test_path_report_table():
    r = PathReport(
        total_db=12.5,
        wavelength_nm=1550,
        from_label="olt:1",
        to_label="customer:2",
        direction="downstream",
        segments=[
            AttenuationSegment(kind="fiber", db=2.0, length_m=5000, description="f"),
            AttenuationSegment(kind="splitter", db=10.5, description="s"),
        ],
    )
    text = r.to_table()
    assert "12.500" in text or "12.5" in text
    assert r.fiber_db == pytest.approx(2.0)
    assert r.splitter_db == pytest.approx(10.5)
    d = r.to_dict()
    assert d["by_kind"]["fiber"] == pytest.approx(2.0)
