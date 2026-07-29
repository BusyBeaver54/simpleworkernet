"""Тесты ObjKey и Interface."""

from simpleworkernet.utils.topology import Interface, ObjKey


def test_objkey_str():
    k = ObjKey("olt", 123)
    assert str(k) == "olt:123"
    assert k.obj_type == "olt"
    assert k.id == 123


def test_objkey_frozen():
    k = ObjKey("cross", "uuid-1")
    assert hash(k) == hash(ObjKey("cross", "uuid-1"))
    assert k == ObjKey("cross", "uuid-1")
    assert k != ObjKey("cross", "uuid-2")


def test_interface_str():
    iface = Interface(ObjKey("fiber", 10), side=2, port=3)
    assert "fiber:10" in str(iface)
    assert "side=2" in str(iface)
    assert "port=3" in str(iface)


def test_interface_hashable():
    a = Interface(ObjKey("splitter", 1), 1, 2)
    b = Interface(ObjKey("splitter", 1), 1, 2)
    c = Interface(ObjKey("splitter", 1), 2, 2)
    assert a == b
    assert a != c
    assert len({a, b, c}) == 2
