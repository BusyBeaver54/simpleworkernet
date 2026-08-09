# simpleworkernet/utils/topology/graphs/__init__.py
from .cgraph import CGraph
from .fngraph import FNGraph
from .cgraph_extra import cgraph_is_linear

if not hasattr(CGraph, "is_linear"):
    CGraph.is_linear = cgraph_is_linear  # type: ignore[attr-defined]

def _build_with_ports(
    self,
    object_type,
    object_id,
    port=None,
    side=None,
    included_fibers=None,
    excluded_fibers=None,
    excluded_nodes=None,
    linear=False,
    linear_on_fail="raise",
):
    from ..builders.base import GraphBuilder
    return GraphBuilder(self).build(
        object_type=object_type,
        object_id=object_id,
        port=port,
        side=side,
        included_fibers=included_fibers,
        excluded_fibers=excluded_fibers,
        excluded_nodes=excluded_nodes,
        linear=linear,
        linear_on_fail=linear_on_fail,
    )

CGraph.build = _build_with_ports  # type: ignore[method-assign]

__all__ = ["CGraph", "FNGraph"]
