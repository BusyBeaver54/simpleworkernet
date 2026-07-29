"""Тесты CGraph без API."""

from simpleworkernet.utils.topology.graphs.cgraph import CGraph
from simpleworkernet.utils.topology.keys import Interface, ObjKey


def test_empty_cgraph(empty_cgraph):
    assert empty_cgraph.vcount() == 0
    assert empty_cgraph.ecount() == 0
    assert empty_cgraph.is_connected() is False


def test_add_iface_vertex(empty_cgraph):
    iface = Interface(ObjKey("olt", 1), 1, 1)
    idx = empty_cgraph.add_iface_vertex(iface)
    assert idx == 0
    assert empty_cgraph.vcount() == 1
    assert empty_cgraph._vertex_index[iface] == 0
    # повторный add — тот же индекс
    assert empty_cgraph.add_iface_vertex(iface) == 0
    assert empty_cgraph.vcount() == 1


def test_add_iface_edge(empty_cgraph):
    a = Interface(ObjKey("customer", 1), 1, 0)
    b = Interface(ObjKey("fiber", 10), 1, 1)
    empty_cgraph.add_iface_edge(a, b, connect_id=42)
    assert empty_cgraph.vcount() == 2
    assert empty_cgraph.ecount() == 1
    assert empty_cgraph.is_connected()
    # дубликат ребра не добавляется
    empty_cgraph.add_iface_edge(a, b, connect_id=42)
    assert empty_cgraph.ecount() == 1


def test_get_vertices_edges(empty_cgraph):
    a = Interface(ObjKey("olt", 1), 1, 1)
    b = Interface(ObjKey("fiber", 2), 1, 1)
    empty_cgraph.add_iface_edge(a, b, connect_id=1, is_internal=False)
    verts = empty_cgraph.get_vertices()
    edges = empty_cgraph.get_edges()
    assert len(verts) == 2
    assert verts[0].obj_type == "olt"
    assert len(edges) == 1
    assert edges[0].connect_id == 1


def test_to_dict_from_dict(client, cache):
    g = CGraph(client, cache=cache)
    a = Interface(ObjKey("olt", 1), 1, 1)
    b = Interface(ObjKey("fiber", 10), 1, 1)
    g.add_iface_edge(a, b, connect_id=5)
    data = g.to_dict()
    g2 = CGraph.from_dict(data, client, cache)
    assert g2.vcount() == 2
    assert g2.ecount() == 1
    assert a in g2._vertex_index


def test_update_directed_flag(empty_cgraph):
    empty_cgraph.add_iface_vertex(Interface(ObjKey("olt", 1), 1, 1))
    empty_cgraph.update_directed_flag()
    assert empty_cgraph.directed is False

    empty_cgraph.add_iface_vertex(Interface(ObjKey("customer", 2), 1, 0))
    empty_cgraph.update_directed_flag()
    assert empty_cgraph.directed is True


def test_repr(empty_cgraph):
    assert "CGraph" in repr(empty_cgraph)
