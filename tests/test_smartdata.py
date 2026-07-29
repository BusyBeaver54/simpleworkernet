"""Тесты SmartData (без сети)."""

import json
import os
import tempfile

from simpleworkernet.models.operators import Operator, Where
from simpleworkernet.smartdata import SmartData
from simpleworkernet.smartdata.metadata import META_KEY, MetaData, PathSegment, SegmentType


def test_empty():
    sd = SmartData(None)
    assert len(sd) == 0
    assert not sd
    assert sd.count() == 0
    assert sd.first() is None
    assert sd.last() is None


def test_list_of_dicts(sample_users):
    sd = SmartData(sample_users)
    assert len(sd) == 4
    assert sd.count() == 4
    assert bool(sd)


def test_where(sample_users):
    sd = SmartData(sample_users)
    active = sd.where("state_id", 2)
    assert active.count() == 3

    rich = sd.where("balance", 1000, Operator.GT)
    assert rich.count() == 2


def test_filter_and_or(sample_users):
    sd = SmartData(sample_users)
    both = sd.filter(
        Where("state_id", 2),
        Where("balance", 1000, Operator.GT),
        join="AND",
    )
    assert both.count() == 2

    either = sd.filter(
        Where("city", "Казань"),
        Where("city", "СПб"),
        join="OR",
    )
    assert either.count() == 2


def test_sort_limit_skip(sample_users):
    sd = SmartData(sample_users)
    sorted_sd = sd.sort(key_field="balance", reverse=True)
    assert sorted_sd.first()["balance"] == 3000 or sorted_sd.to_raw_list()[0]["balance"] == 3000

    top2 = sorted_sd.limit(2)
    assert top2.count() == 2

    rest = sd.skip(2)
    assert rest.count() == 2


def test_map_group_unique(sample_users):
    sd = SmartData(sample_users)
    names = sd.map(lambda x: x["name"])
    assert "Иван" in names
    assert len(names) == 4

    by_city = sd.group_by(lambda x: x["city"])
    assert "Москва" in by_city
    assert by_city["Москва"].count() == 2

    uniq = sd.unique(key_func=lambda x: x["city"])
    assert uniq.count() == 3


def test_aggregates(sample_users):
    sd = SmartData(sample_users)
    assert sd.sum(lambda x: x["balance"]) == 5000
    assert sd.avg(lambda x: x["balance"]) == 1250.0

    mx = sd.max(key_func=lambda x: x["balance"])
    assert mx["balance"] == 3000 or (
        isinstance(mx, dict) and mx.get("balance") == 3000
    )

    mn = sd.min(key_func=lambda x: x["balance"])
    raw = mn if isinstance(mn, dict) else None
    if raw is None and hasattr(mn, "get"):
        raw = mn
    # min balance = 0
    bal = mn["balance"] if isinstance(mn, dict) else getattr(mn, "balance", None)
    assert bal == 0


def test_getitem_slice_attr(sample_users):
    sd = SmartData(sample_users)
    first = sd[0]
    assert first["id"] == 1 or getattr(first, "id", None) == 1

    subset = sd[1:3]
    assert subset.count() == 2

    ids = sd["id"]
    assert ids == [1, 2, 3, 4]


def test_add_eq(sample_users):
    a = SmartData(sample_users[:2])
    b = SmartData(sample_users[2:])
    c = a + b
    assert c.count() == 4
    assert a == SmartData(sample_users[:2])


def test_to_raw_list_and_dict(sample_users):
    sd = SmartData(sample_users)
    raw = sd.to_raw_list()
    assert len(raw) == 4
    assert isinstance(raw[0], dict)

    d = sd.to_dict()
    assert "data" in d


def test_to_file_json(sample_users):
    sd = SmartData(sample_users)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "data.json")
        sd.to_file(path)
        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data  # не пустой


def test_repr_stats(sample_users):
    sd = SmartData(sample_users)
    assert "SmartData" in repr(sd)
    stats = sd.get_stats()
    assert stats["total_items"] == 4


def test_metadata_path():
    seg = PathSegment(SegmentType.FLD, "data")
    assert str(seg) == "fld:data"
    assert PathSegment.from_dict(seg.to_dict()).key == "data"

    meta = MetaData(
        path=[
            PathSegment(SegmentType.FLD, "users"),
            PathSegment(SegmentType.IDX, "0"),
            PathSegment(SegmentType.FLD, "name"),
        ]
    )
    assert meta.get_path_string() == "fld:users/idx:0/fld:name"
    assert meta.depth() == 3
    assert not meta.is_root()
    assert meta.get_parent_path() == "fld:users/idx:0"
    assert meta.get_keys_by_type(SegmentType.FLD) == ["users", "name"]

    empty = MetaData()
    assert empty.is_root()
    assert empty.get_path_string() == ""


def test_segment_type_from_string():
    assert SegmentType.from_string("fld") == SegmentType.FLD
    assert SegmentType.from_string("unknown") == SegmentType.COL


def test_meta_key_constant():
    assert META_KEY == "__meta__"
