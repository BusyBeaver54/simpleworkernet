# simpleworkernet/utils/topology/graphs/__init__.py
from .cgraph import CGraph
from .fngraph import FNGraph
from .cgraph_extra import cgraph_is_linear
from ..paths import simple_paths as _simple_paths, shortest_simple_path as _shortest

if not hasattr(CGraph, "is_linear"):
    CGraph.is_linear = cgraph_is_linear  # type: ignore[attr-defined]

def _build_with_ports(
    self, object_type, object_id, port=None, side=None,
    included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    linear=False, linear_on_fail="raise",
):
    from ..builders.base import GraphBuilder
    return GraphBuilder(self).build(
        object_type=object_type, object_id=object_id, port=port, side=side,
        included_fibers=included_fibers, excluded_fibers=excluded_fibers,
        excluded_nodes=excluded_nodes, linear=linear, linear_on_fail=linear_on_fail,
    )

def _cgraph_simple_paths(self, source, target, *, cutoff=None, max_paths=None):
    return _simple_paths(self, source, target, cutoff=cutoff, max_paths=max_paths)

def _cgraph_shortest_path(self, source, target):
    return _shortest(self, source, target)

CGraph.build = _build_with_ports  # type: ignore[method-assign]
CGraph.simple_paths = _cgraph_simple_paths  # type: ignore[attr-defined]
CGraph.shortest_path = _cgraph_shortest_path  # type: ignore[attr-defined]

__all__ = ["CGraph", "FNGraph"]
