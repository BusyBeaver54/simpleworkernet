"""Тесты FNGraph без API."""

from simpleworkernet.utils.topology.graphs.fngraph import FNGraph


def test_empty_fngraph(empty_fngraph):
    assert empty_fngraph.vcount() == 0
    assert empty_fngraph.ecount() == 0


def test_add_node_and_fiber(empty_fngraph):
    empty_fngraph._add_node_vertex(1)
    empty_fngraph._add_node_vertex(2)
    empty_fngraph._add_fiber_edge(1, 2, fiber_id=100)
    assert empty_fngraph.vcount() == 2
    assert empty_fngraph.ecount() == 1
    assert empty_fngraph.is_connected()


def test_no_self_loop(empty_fngraph):
    empty_fngraph._add_node_vertex(1)
    empty_fngraph._add_fiber_edge(1, 1, fiber_id=1)
    assert empty_fngraph.ecount() == 0


def test_get_vertices_edges(empty_fngraph):
    empty_fngraph._add_node_vertex(10)
    empty_fngraph._add_node_vertex(20)
    empty_fngraph._add_fiber_edge(10, 20, fiber_id=55)
    verts = empty_fngraph.get_vertices()
    edges = empty_fngraph.get_edges()
    assert {v.node_id for v in verts} == {10, 20}
    assert edges[0].fiber_id == 55


def test_to_dict_from_dict(client, cache):
    g = FNGraph(client, cache=cache)
    g._add_node_vertex(1)
    g._add_node_vertex(2)
    g._add_fiber_edge(1, 2, fiber_id=7)
    data = g.to_dict()
    g2 = FNGraph.from_dict(data, client, cache)
    assert g2.vcount() == 2
    assert g2.ecount() == 1


def test_repr(empty_fngraph):
    assert "FNGraph" in repr(empty_fngraph)
