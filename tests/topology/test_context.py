"""Тесты BuildContext."""

from unittest.mock import MagicMock

from simpleworkernet.utils.topology.cache import DataCache
from simpleworkernet.utils.topology.context import BuildContext
from simpleworkernet.utils.topology.graphs.cgraph import CGraph
from simpleworkernet.utils.topology.keys import Interface, ObjKey


def _ctx(**kwargs):
    client = MagicMock()
    cache = DataCache()
    graph = CGraph(client, cache=cache)
    defaults = dict(
        client=client,
        cache=cache,
        graph=graph,
        start_node_id=100,
    )
    defaults.update(kwargs)
    return BuildContext(**defaults)


def test_enqueue_marks_visited():
    ctx = _ctx()
    iface = Interface(ObjKey("olt", 1), 1, 1)
    ctx.enqueue(iface)
    assert iface in ctx.visited
    assert len(ctx.queue) == 1
    ctx.enqueue(iface)  # повторно — не добавляет
    assert len(ctx.queue) == 1


def test_should_stop_excluded_fiber():
    ctx = _ctx(excluded_fibers={10})
    assert ctx.should_stop_at_fiber(10, 100) is True
    assert ctx.should_stop_at_fiber(11, 100) is False


def test_should_stop_included_only_on_start_node():
    ctx = _ctx(included_fibers={10}, start_node_id=100)
    # на стартовом узле — только included
    assert ctx.should_stop_at_fiber(99, 100) is True
    assert ctx.should_stop_at_fiber(10, 100) is False
    # на другом узле included не действует
    assert ctx.should_stop_at_fiber(99, 200) is False


def test_should_stop_at_node():
    ctx = _ctx(excluded_nodes={5, 6})
    assert ctx.should_stop_at_node(5) is True
    assert ctx.should_stop_at_node(7) is False
