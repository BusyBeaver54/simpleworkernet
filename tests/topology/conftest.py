"""Общие фикстуры для тестов topology."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from simpleworkernet.utils.topology.cache import DataCache
from simpleworkernet.utils.topology.graphs.cgraph import CGraph
from simpleworkernet.utils.topology.graphs.fngraph import FNGraph
from simpleworkernet.utils.topology.keys import Interface, ObjKey
from simpleworkernet.utils.topology.topology import Topology


@pytest.fixture
def client():
    return MagicMock()


@pytest.fixture
def cache():
    return DataCache()


@pytest.fixture
def empty_cgraph(client, cache):
    return CGraph(client, cache=cache)


@pytest.fixture
def empty_fngraph(client, cache):
    return FNGraph(client, cache=cache)


@pytest.fixture
def topology(client, cache):
    return Topology(client, cache=cache)


def make_comm(
    *,
    connect_id: int = 1,
    object_type: str = "fiber",
    object_id=None,
    object_uuid=None,
    clps_first=1,
    clps_mid=1,
    clps_last=None,
):
    """Простая запись коммутации (как из API)."""
    return SimpleNamespace(
        connect_id=connect_id,
        object_type=object_type,
        object_id=object_id,
        object_uuid=object_uuid,
        clps_first=clps_first,
        clps_mid=clps_mid,
        clps_last=clps_last,
    )


def chain_customer_fiber_olt(client, cache):
    """customer -- fiber -- olt."""
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
