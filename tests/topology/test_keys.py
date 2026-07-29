"""Тесты ObjKey и Interface."""

from simpleworkernet.utils.topology import Interface, ObjKey


def test_objkey_str():
    k = ObjKey("olt", 123)
    assert str(k) == "olt:123"
    assert k.obj_type == "olt"
    assert k.id == 123


def test_objkey_cross_uuid():
    k = ObjKey("cross", "uuid-abc")
    assert str(k) == "cross:uuid-abc"


def test_objkey_frozen_hashable():
    a = ObjKey("cross", "uuid-1")
    b = ObjKey("cross", "uuid-1")
    c = ObjKey("cross", "uuid-2")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert len({a, b, c}) == 2


def test_interface_str():
    iface = Interface(ObjKey("fiber", 10), side=2, port=3)
    s = str(iface)
    assert "fiber:10" in s
    assert "side=2" in s
    assert "port=3" in s


def test_interface_hashable():
    a = Interface(ObjKey("splitter", 1), 1, 2)
    b = Interface(ObjKey("splitter", 1), 1, 2)
    c = Interface(ObjKey("splitter", 1), 2, 2)
    assert a == b
    assert a != c
    assert len({a, b, c}) == 2
