"""Тесты DataCache (без сети)."""

from simpleworkernet.utils.topology.cache import DataCache


def test_cache_set_get():
    c = DataCache()
    c.set_object("olt", 1, {"id": 1})
    assert c.get_object("olt", 1) == {"id": 1}
    # device alias
    assert c.get_object("device", 1) == {"id": 1}


def test_cache_get_or_load():
    c = DataCache()
    calls = []

    def loader():
        calls.append(1)
        return {"loaded": True}

    obj = c.get_or_load_object("node", 5, loader)
    assert obj == {"loaded": True}
    assert len(calls) == 1

    obj2 = c.get_or_load_object("node", 5, loader)
    assert obj2 == {"loaded": True}
    assert len(calls) == 1  # не вызывался повторно


def test_cache_commutations():
    c = DataCache()
    c.set_commutations("fiber", 10, ["comm1"])
    assert c.get_commutations("fiber", 10) == ["comm1"]


def test_cache_clear():
    c = DataCache()
    c.set_object("olt", 1, {})
    c.clear()
    assert c.get_object("olt", 1) is None


def test_cache_to_from_dict():
    c = DataCache()
    c.set_object("olt", 1, {"x": 1})
    c.set_commutations("fiber", 2, ["a"])
    data = c.to_dict()
    c2 = DataCache.from_dict(data)
    assert c2.get_object("olt", 1) == {"x": 1}
    assert c2.get_commutations("fiber", 2) == ["a"]
