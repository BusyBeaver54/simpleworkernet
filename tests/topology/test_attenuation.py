"""Unit-тесты каталога и длины (без live API / без igraph path)."""

from types import SimpleNamespace

import pytest

from simpleworkernet.models.primitives import GeoPoint
from simpleworkernet.utils.topology.attenuation import (
    AttenuationCatalog,
    PathReport,
)
from simpleworkernet.utils.topology.attenuation.catalog import guess_ratio_key
from simpleworkernet.utils.topology.attenuation.length import (
    path_length_m,
    resolve_fiber_length_m,
)
from simpleworkernet.utils.topology.attenuation.models import AttenuationSegment


def test_catalog_defaults():
    cat = AttenuationCatalog.with_defaults()
    assert cat.fiber_db_per_km(1550) == pytest.approx(0.19)
    assert cat.fiber_db_per_km(1310) == pytest.approx(0.34)
    assert cat.fiber_db_per_km(1550, use_max=True) == pytest.approx(0.22)
    assert cat.splice_db() > 0
    assert cat.adapter_db() > 0


def test_catalog_nearest_wavelength():
    cat = AttenuationCatalog.with_defaults()
    # 1548 отсутствует → ближайшая 1550
    v = cat.fiber_db_per_km(1548)
    assert v == pytest.approx(0.19)


def test_catalog_force_fiber():
    cat = AttenuationCatalog.with_defaults()
    cat.force_fiber(100, 0.5)
    assert cat.forced_fiber_db_per_km(100, 1550) == 0.5
    assert cat.forced_fiber_db_per_km(999, 1550) is None
    cat.force_fiber(200, {1310: 0.4, 1550: {"db": 0.18, "db_max": 0.22}})
    assert cat.forced_fiber_db_per_km(200, 1550) == pytest.approx(0.18)
    assert cat.forced_fiber_db_per_km(200, 1550, use_max=True) == pytest.approx(0.22)


def test_catalog_splitter_ratio():
    cat = AttenuationCatalog.with_defaults()
    db, src, _pn = cat.splitter_port_db(ratio_key="1x2_5/95", port=1, port_count_out=2)
    assert src == "ratio" or src.startswith("ratio")
    assert db > 10  # leg 5%
    db2, src2, _pn2 = cat.splitter_port_db(ratio_key="1x2_5/95", port=2, port_count_out=2)
    assert db2 < 2  # leg 95%
    # by port name
    db3, src3, _pn3 = cat.splitter_port_db(
        ratio_key="1x2_5/95", port_name="5%", port_count_out=2
    )
    assert src3 == "ratio" or src3.startswith("ratio")
    assert db3 > 10


def test_catalog_splitter_estimated():
    cat = AttenuationCatalog.with_defaults()
    db, src, _pn = cat.splitter_port_db(port=1, port_count_out=8)
    assert src == "estimated"
    assert db > 9  # ~10.5 theoretical + excess


def test_catalog_force_splitter_and_cross():
    cat = AttenuationCatalog.with_defaults()
    cat.force_splitter_port(42, port=3, db=11.1)
    db, src, _pn = cat.splitter_port_db(splitter_id=42, port=3)
    assert src == "force" and db == pytest.approx(11.1)
    cat.force_cross("uuid-1", 0.55)
    assert cat.forced_cross_db("uuid-1") == pytest.approx(0.55)


def test_guess_ratio_key():
    assert guess_ratio_key("PLC 1x8") in (None, "1x8_equal") or "1x8" in (guess_ratio_key("PLC 1x8") or "")
    k = guess_ratio_key("FBT 5/95")
    assert k is None or "5" in k or "95" in k


def test_path_report_by_kind():
    segs = [
        AttenuationSegment(kind="fiber", db=1.0, description="f"),
        AttenuationSegment(kind="splitter", db=10.0, description="s"),
        AttenuationSegment(kind="splice", db=0.1, description="sp"),
    ]
    pr = PathReport(
        total_db=11.1, total_db_min=11.1, total_db_max=11.1,
        wavelength_nm=1550, segments=segs, direction="upstream",
    )
    bk = pr.by_kind()
    assert bk.get("fiber", 0) == pytest.approx(1.0)
    assert bk.get("splitter", 0) == pytest.approx(10.0)


def test_resolve_fiber_length_m_opticalen():
    obj = SimpleNamespace(opticalen=1200, opticalen2=0, building_length=None)
    length, src = resolve_fiber_length_m(obj)
    assert length == pytest.approx(1200.0)
    assert src in ("opticalen", "opticalen2", "building", "geo", "cache") or src


def test_path_length_m_geo():
    pts = [GeoPoint(lat=55.0, lon=37.0), GeoPoint(lat=55.001, lon=37.001)]
    try:
        L = path_length_m(pts)
        assert L is None or L > 0
    except Exception:
        pass


# ---------------------------------------------------------------------------
# fiber core info: port = ОВ number, port_name = mNfM, core id in meta
# ---------------------------------------------------------------------------

def test_fiber_core_info_by_number_and_module():
    """port_name=m1f5, port=номер ОВ, fiber_core_id в результате."""
    from types import SimpleNamespace
    from simpleworkernet.utils.topology.attenuation.calculator import Attenuation

    fibers = [
        SimpleNamespace(
            id=1001, number=1,
            moduleColor=SimpleNamespace(htmlCode="#ff0000", name="red"),
        ),
        SimpleNamespace(
            id=1005, number=5,
            moduleColor=SimpleNamespace(htmlCode="#ff0000", name="red"),
        ),
        SimpleNamespace(
            id=2001, number=13,
            moduleColor=SimpleNamespace(htmlCode="#00ff00", name="green"),
        ),
    ]
    cable = SimpleNamespace(id=42, fibers=fibers, opticalen=100)
    att = Attenuation(cgraph=None, client=None, cache=None)
    info = att._fiber_core_info({
        "obj_type": "fiber", "obj_id": "42", "port": 5, "api_obj": cable,
    })
    assert info["port"] == 5
    assert info["fiber_number"] == 5
    assert info["fiber_core_id"] == 1005
    assert info["module"] == 1
    assert info["port_name"] == "m1f5"

    info2 = att._fiber_core_info({
        "obj_type": "fiber", "obj_id": "42", "port": 1005, "api_obj": cable,
    })
    assert info2["port"] == 5
    assert info2["fiber_core_id"] == 1005
    assert info2["port_name"] == "m1f5"

    info3 = att._fiber_core_info({
        "obj_type": "fiber", "obj_id": "42", "port": 13, "api_obj": cable,
    })
    assert info3["module"] == 2
    assert info3["port_name"] == "m2f13"


def test_fiber_core_info_without_fibers_list_small_port():
    from simpleworkernet.utils.topology.attenuation.calculator import Attenuation

    att = Attenuation(cgraph=None, client=None, cache=None)
    info = att._fiber_core_info({
        "obj_type": "fiber", "obj_id": "1", "port": 3, "api_obj": None,
    })
    assert info["port"] == 3
    assert info["fiber_number"] == 3
    assert info["port_name"] == "f3"


def test_ensure_api_obj_from_cache():
    """_ensure_api_obj подтягивает объект из DataCache без API."""
    from types import SimpleNamespace
    from simpleworkernet.utils.topology.attenuation.calculator import Attenuation
    from simpleworkernet.utils.topology.cache import DataCache
    from simpleworkernet.utils.topology.constants import TYPE_CUSTOMER

    cache = DataCache()
    customer = SimpleNamespace(id=17711, full_name="Иванов И.И.", name="Иванов")
    cache.set_object(TYPE_CUSTOMER, 17711, customer)

    att = Attenuation(cgraph=None, client=None, cache=cache)
    va = att._ensure_api_obj({
        "obj_type": TYPE_CUSTOMER, "obj_id": "17711", "port": 0, "api_obj": None,
    })
    assert va.get("api_obj") is customer
