"""Тесты merge_cgraphs / merge_fngraphs."""

from simpleworkernet.utils.topology.graphs.cgraph import CGraph
from simpleworkernet.utils.topology.graphs.fngraph import FNGraph
from simpleworkernet.utils.topology.keys import Interface, ObjKey
from simpleworkernet.utils.topology.merge import merge_cgraphs, merge_fngraphs


def test_merge_cgraphs_empty(client, cache):
    assert merge_cgraphs([], client, cache) is None


def test_merge_cgraphs_single(client, cache):
    g = CGraph(client, cache=cache)
    g.add_iface_vertex(Interface(ObjKey("olt", 1), 1, 1))
    assert merge_cgraphs([g], client, cache) is g


def test_merge_cgraphs_overlapping(client, cache):
    g1 = CGraph(client, cache=cache)
    a = Interface(ObjKey("olt", 1), 1, 1)
    b = Interface(ObjKey("fiber", 10), 1, 1)
    g1.add_iface_vertex(a)
    g1.add_iface_vertex(b)
    g1.add_iface_edge(a, b, connect_id=100)

    g2 = CGraph(client, cache=cache)
    c = Interface(ObjKey("customer", 5), 1, 0)
    g2.add_iface_vertex(b)
    g2.add_iface_vertex(c)
    g2.add_iface_edge(b, c, connect_id=200)

    merged = merge_cgraphs([g1, g2], client, cache)
    assert merged is not None
    assert merged.vcount() == 3
    assert merged.ecount() == 2
    assert merged.is_connected()


def test_merge_fngraphs_empty(client, cache):
    assert merge_fngraphs([], client, cache) is None


def test_merge_fngraphs_single(client, cache):
    g = FNGraph(client, cache=cache)
    g._add_node_vertex(1)
    assert merge_fngraphs([g], client, cache) is g


def test_merge_fngraphs_overlapping(client, cache):
    g1 = FNGraph(client, cache=cache)
    g1._add_node_vertex(1)
    g1._add_node_vertex(2)
    g1._add_fiber_edge(1, 2, fiber_id=100)

    g2 = FNGraph(client, cache=cache)
    g2._add_node_vertex(2)
    g2._add_node_vertex(3)
    g2._add_fiber_edge(2, 3, fiber_id=200)

    merged = merge_fngraphs([g1, g2], client, cache)
    assert merged is not None
    assert merged.vcount() == 3
    assert merged.ecount() == 2
