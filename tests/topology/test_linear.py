"""Тесты LinearPathFinder на синтетическом графе."""

from unittest.mock import MagicMock

from simpleworkernet.utils.topology.cache import DataCache
from simpleworkernet.utils.topology.graphs.cgraph import CGraph
from simpleworkernet.utils.topology.keys import Interface, ObjKey
from simpleworkernet.utils.topology.linear import LinearPathFinder
from simpleworkernet.utils.topology.topology import Topology


def _chain_graph(client, cache):
    """customer -- fiber -- olt (линейная цепочка)."""
    g = CGraph(client, cache=cache)
    cust = Interface(ObjKey("customer", 1), 1, 0)
    fib = Interface(ObjKey("fiber", 10), 1, 1)
    olt = Interface(ObjKey("olt", 100), 1, 1)

    g.add_iface_vertex(cust)
    g.add_iface_vertex(fib)
    g.add_iface_vertex(olt)
    g.add_iface_edge(cust, fib, connect_id=1)
    g.add_iface_edge(fib, olt, connect_id=2)
    return g, cust, fib, olt


def test_linear_trace_to_olt():
    client = MagicMock()
    cache = DataCache()
    topo = Topology(client, cache=cache)
    g, cust, fib, olt = _chain_graph(client, cache)
    topo.cgraphs = [g]

    finder = LinearPathFinder(topo)
    linear = finder.trace("customer", 1, port=0)
    assert linear.vcount() == 3
    assert linear.ecount() == 2


def test_linear_requires_graphs():
    client = MagicMock()
    topo = Topology(client)
    finder = LinearPathFinder(topo)
    try:
        finder.trace("customer", 1)
        assert False
    except ValueError as e:
        assert "build_from" in str(e).lower() or "граф" in str(e).lower()


def test_linear_splitter_requires_port():
    client = MagicMock()
    cache = DataCache()
    topo = Topology(client, cache=cache)
    g, *_ = _chain_graph(client, cache)
    topo.cgraphs = [g]
    finder = LinearPathFinder(topo)
    try:
        finder.trace("splitter", 5)
        assert False
    except ValueError as e:
        assert "порт" in str(e).lower()
