"""Тесты LinearPathFinder на синтетическом графе."""

from tests.topology.conftest import chain_customer_fiber_olt
from simpleworkernet.utils.topology.linear import LinearPathFinder
from simpleworkernet.utils.topology.topology import NetworkTopology


def test_linear_trace_to_olt(client, cache):
    topo = NetworkTopology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]

    finder = LinearPathFinder(topo)
    linear = finder.trace("customer", 1, port=0)
    assert linear.vcount() == 3
    assert linear.ecount() == 2


def test_linear_requires_graphs(client):
    topo = NetworkTopology(client)
    finder = LinearPathFinder(topo)
    try:
        finder.trace("customer", 1)
        assert False
    except ValueError as e:
        assert "build_from" in str(e).lower() or "граф" in str(e).lower()


def test_linear_splitter_requires_port(client, cache):
    topo = NetworkTopology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]
    finder = LinearPathFinder(topo)
    try:
        finder.trace("splitter", 5)
        assert False
    except ValueError as e:
        assert "порт" in str(e).lower()


def test_linear_side_requires_side(client, cache):
    topo = NetworkTopology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]
    finder = LinearPathFinder(topo)
    try:
        finder.trace("fiber", 10, port=1)
        assert False
    except ValueError:
        pass


def test_linear_path_finder_on_synthetic_chain(client, cache):
    """get_linear требует node_id на fiber; LinearPathFinder работает на синтетике."""
    topo = NetworkTopology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]

    finder = LinearPathFinder(topo)
    linear = finder.trace("customer", 1, port=0)
    assert linear.vcount() == 3
    assert linear.ecount() == 2
