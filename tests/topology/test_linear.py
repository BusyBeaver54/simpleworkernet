"""Тесты LinearPathFinder на синтетическом графе."""

from tests.topology.conftest import chain_customer_fiber_olt
from simpleworkernet.utils.topology.linear import LinearPathFinder
from simpleworkernet.utils.topology.topology import Topology


def test_linear_trace_to_olt(client, cache):
    topo = Topology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]

    finder = LinearPathFinder(topo)
    linear = finder.trace("customer", 1, port=0)
    assert linear.vcount() == 3
    assert linear.ecount() == 2


def test_linear_requires_graphs(client):
    topo = Topology(client)
    finder = LinearPathFinder(topo)
    try:
        finder.trace("customer", 1)
        assert False
    except ValueError as e:
        assert "build_from" in str(e).lower() or "граф" in str(e).lower()


def test_linear_splitter_requires_port(client, cache):
    topo = Topology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]
    finder = LinearPathFinder(topo)
    try:
        finder.trace("splitter", 5)
        assert False
    except ValueError as e:
        assert "порт" in str(e).lower()


def test_linear_side_requires_side(client, cache):
    topo = Topology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]
    finder = LinearPathFinder(topo)
    try:
        finder.trace("fiber", 10, port=1)  # side не указан
        assert False
    except ValueError:
        pass


def test_topology_from_commutation(client, cache):
    topo = Topology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]

    linear_topo = topo.topology_from_commutation("customer", 1, port=0)
    assert len(linear_topo.cgraphs) == 1
    assert linear_topo.cgraphs[0].vcount() == 3
