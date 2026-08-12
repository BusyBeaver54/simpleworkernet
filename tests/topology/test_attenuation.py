"""Unit-тесты каталога и длины (без live API / без igraph path)."""

from types import SimpleNamespace

import pytest

from simpleworkernet.models.primitives import GeoPoint
from simpleworkernet.utils.topology.attenuation.catalog import AttenuationCatalog
from simpleworkernet.utils.topology.attenuation.length import (
    path_length_m,
    resolve_fiber_length_m,
)


def test_catalog_defaults_wavelength():
    cat = AttenuationCatalog.with_defaults()
    assert cat.fiber_db_per_km(1550) == pytest.approx(0.19)
    assert cat.fiber_db_per_km(1310) == pytest.approx(0.34)
    assert cat.splice_db() == pytest.approx(0.05)
    assert cat.adapter_db() == pytest.approx(0.2)


def test_catalog_splitter_port_by_name():
    cat = AttenuationCatalog.with_defaults()
    db, src, port_name = cat.splitter_port_db(
        catalog_name="PLC 1x8 SC/APC",
        port=1,
        wavelength_nm=1550,
        prefer_name=True,
    )
    assert db > 0
    # источник: ratio:… / estimated / name / catalog / default
    assert src.split(":")[0] in ("name", "catalog", "estimated", "default", "ratio")


def test_fiber_length_opticalen_priority():
    """opticalen2 приоритетнее opticalen (см. resolve_fiber_length_m)."""
    fiber = SimpleNamespace(opticalen=120.0, opticalen2=80.5, path=None)
    length, src = resolve_fiber_length_m(fiber)
    assert length == pytest.approx(80.5)
    assert src == "opticalen2"


def test_fiber_length_opticalen_fallback():
    fiber = SimpleNamespace(opticalen=120.0, opticalen2=None, path=None)
    length, src = resolve_fiber_length_m(fiber)
    assert length == pytest.approx(120.0)
    assert src == "opticalen"


def test_fiber_length_geo_fallback():
    """geo: path из GeoPoint (haversine × slack_k)."""
    p1 = GeoPoint(lat=55.75, lon=37.61)
    p2 = GeoPoint(lat=55.76, lon=37.62)
    fiber = SimpleNamespace(opticalen=None, opticalen2=None, path=[p1, p2])
    length, src = resolve_fiber_length_m(fiber, slack_k=1.0)
    assert length is not None and length > 0
    assert src == "geo"


def test_path_length_m_empty():
    assert path_length_m(None) is None
    assert path_length_m([]) is None
    assert path_length_m([GeoPoint(lat=1, lon=1)]) is None


def test_fiber_core_info_by_number_and_module():
    """port=номер ОВ, module_number/mf_path, port_name fallback → mf_path."""
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
    assert info["module_number"] == 1
    assert info["mf_path"] == "m1f5"
    assert info["port_name"] == "m1f5"  # нет color.name → fallback mf_path

    info2 = att._fiber_core_info({
        "obj_type": "fiber", "obj_id": "42", "port": 1005, "api_obj": cable,
    })
    assert info2["port"] == 5
    assert info2["fiber_core_id"] == 1005
    assert info2["port_name"] == "m1f5"

    info3 = att._fiber_core_info({
        "obj_type": "fiber", "obj_id": "42", "port": 13, "api_obj": cable,
    })
    assert info3["module_number"] == 2
    assert info3["mf_path"] == "m2f13"
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
