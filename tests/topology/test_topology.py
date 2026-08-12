"""Тесты оркестратора NetworkTopology (без реального API)."""

import os
import tempfile

from tests.topology.conftest import chain_customer_fiber_olt
from simpleworkernet.utils.topology.graphs.fngraph import FNGraph
from simpleworkernet.utils.topology.topology import NetworkTopology, _normalize_set


def test_normalize_set():
    assert _normalize_set(None) is None
    assert _normalize_set(5) == {5}
    assert _normalize_set([1, 2]) == {1, 2}
    assert _normalize_set({3}) == {3}


def test_topology_init(topology):
    assert topology.cgraphs == []
    assert topology.fngraph is None


def test_topology_repr(topology):
    assert "NetworkTopology" in repr(topology)


def test_add_cgraph_rejects_empty(topology, empty_cgraph):
    topology._add_cgraph(empty_cgraph)
    assert topology.cgraphs == []


def test_add_cgraph_connected(topology, client, cache):
    g, *_ = chain_customer_fiber_olt(client, cache)
    topology._add_cgraph(g)
    assert len(topology.cgraphs) == 1


def test_getters(client, cache):
    topo = NetworkTopology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]

    assert 1 in topo.get_customers()
    assert 10 in topo.get_fibers()
    assert 100 in topo.get_devices()
    # get_cables == get_fibers (только из cgraphs)
    assert 10 in topo.get_cables()


def test_get_nodes_from_fngraph(client, cache):
    """get_nodes читает node_id из FNGraph; get_cables — только из cgraphs."""
    topo = NetworkTopology(client, cache=cache)
    fn = FNGraph(client, cache=cache)
    fn._add_node_vertex(1)
    fn._add_node_vertex(2)
    fn._add_fiber_edge(1, 2, fiber_id=99)
    topo.fngraph = fn

    assert set(topo.get_nodes()) == {1, 2}
    # fiber_id из FNGraph в get_cables не попадает (алгоритм смотрит cgraphs)
    assert topo.get_cables() == []


def test_save_load_roundtrip(client, cache):
    """pickle без live client/cache (MagicMock не сериализуется)."""
    topo = NetworkTopology(client, cache=cache)
    g, *_ = chain_customer_fiber_olt(client, cache)
    topo.cgraphs = [g]

    # отвязываем несериализуемые ссылки (как при реальном save без mock)
    topo.client = None
    topo.cache = None
    for cg in topo.cgraphs:
        cg.client = None
        cg.cache = None

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "topo.pkl")
        topo.save_to_file(path)
        assert os.path.isfile(path)

        loaded = NetworkTopology.load_from_file(path)
        assert len(loaded.cgraphs) == 1
        assert loaded.cgraphs[0].vcount() == 3


def test_reset(topology, client, cache):
    g, *_ = chain_customer_fiber_olt(client, cache)
    topology.cgraphs = [g]
    topology._reset()
    assert topology.cgraphs == []
    assert topology.fngraph is None
