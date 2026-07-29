"""Эвристика side1=IN / side2=OUT для сплиттера."""

from simpleworkernet.utils.topology.attenuation.calculator import Attenuation
from simpleworkernet.utils.topology.constants import TYPE_SPLITTER


def test_splitter_out_vertex_prefers_side2():
    ua = {"obj_type": TYPE_SPLITTER, "obj_id": "10", "side": 1, "port": 1}
    va = {"obj_type": TYPE_SPLITTER, "obj_id": "10", "side": 2, "port": 3}
    out = Attenuation._splitter_out_vertex(ua, va)
    assert out["side"] == 2 and out["port"] == 3

    out2 = Attenuation._splitter_out_vertex(va, ua)
    assert out2["side"] == 2 and out2["port"] == 3


def test_splitter_out_symmetric_db_direction_label_only():
    """Порт OUT один и тот же независимо от порядка ua/va."""
    in_v = {"obj_type": TYPE_SPLITTER, "obj_id": "5", "side": 1, "port": 1}
    out_v = {"obj_type": TYPE_SPLITTER, "obj_id": "5", "side": 2, "port": 2}
    assert Attenuation._splitter_out_vertex(in_v, out_v)["port"] == 2
    assert Attenuation._splitter_out_vertex(out_v, in_v)["port"] == 2
