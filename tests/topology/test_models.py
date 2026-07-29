"""Тесты dataclass-моделей вершин/рёбер."""

from simpleworkernet.utils.topology.models import (
    CGraphEdge,
    CGraphVertex,
    FNGraphEdge,
    FNGraphVertex,
)


def test_cgraph_vertex_defaults():
    v = CGraphVertex(obj_type="olt", obj_id="1", side=1, port=1)
    assert v.node_id is None
    assert v.terminate_vertex is False
    assert v.finish_data == []


def test_cgraph_edge_defaults():
    e = CGraphEdge(source=0, target=1)
    assert e.connect_id == 0
    assert e.is_internal is False


def test_fngraph_vertex():
    v = FNGraphVertex(node_id=42, name="node:42")
    assert v.node_id == 42
    assert v.coordinates is None


def test_fngraph_edge():
    e = FNGraphEdge(source=0, target=1, fiber_id=100)
    assert e.fiber_id == 100
