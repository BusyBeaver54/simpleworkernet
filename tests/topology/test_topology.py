"""Тесты оркестратора Topology (без реального API)."""

import os
import tempfile

from tests.topology.conftest import chain_customer_fiber_olt
from simpleworkernet.utils.topology.graphs.cgraph import CGraph
from simpleworkernet.utils.topology.graphs.fngraph import FNGraph
from simpleworkernet.utils.topology.keys import Interface, ObjKey
from simpleworkernet.utils.topology.topology import Topology, _normalize_set


def test_normalize_set():
    assert _normalize_set(None) is None
    assert _normalize_set(5) == {5}
    assert _normalize_set([1, 2]) == {1, 2}
    assert _normalize_set({3}) == {3}


def test_topology_init(topology):
    assert topology.cgraphs == []
    assert topology.fngraph is None


def test_topology_repr(topology):
    assert "Topology" in repr(topology)


def test_add_cgraph_rejects_empty(topology, empty_cgraph):
    topology._add_cgraph(empty_cgraph)
    assert topology.cgraphs == []


def test_add_cgraph_connected(topology, client, cache):
    g, *_ = chain_customer_fiber_olt(client, cache)
    topology._add_cgraph(g)
    assert len(topology.cgraphs) == 1


def test_getters(client, cache):
    topo = Topology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]

    assert 1 in topo.get_customers()
    assert 10 in topo.get_fibers()
    assert 100 in topo.get_devices()


def test_get_nodes_cables_from_fngraph(client, cache):
    topo = Topology(client, cache=cache)
    fn = FNGraph(client, cache=cache)
    fn._add_node_vertex(1)
    fn._add_node_vertex(2)
    fn._add_fiber_edge(1, 2, fiber_id=99)
    topo.fngraph = fn

    assert set(topo.get_nodes()) == {1, 2}
    assert 99 in topo.get_cables()


def test_save_load_roundtrip(client, cache):
    topo = Topology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]
    client._url = "https://example.test"
    client._apikey = "secret"

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "topo.pkl")
        topo.save_to_file(path)
        assert os.path.isfile(path)

        loaded = Topology.load_from_file(path)
        assert len(loaded.cgraphs) == 1
        assert loaded.cgraphs[0].vcount() == 3


def test_reset(topology, client, cache):
    g, *_ = chain_customer_fiber_olt(client, cache)
    topology.cgraphs = [g]
    topology._reset()
    assert topology.cgraphs == []
    assert topology.fngraph is None
