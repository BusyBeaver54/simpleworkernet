# simpleworkernet/utils/topology/graphs/__init__.py
"""CGraph / FNGraph public exports and CGraph.build binding."""
from __future__ import annotations
from typing import Any, List, Optional, Set, Union

from .cgraph import CGraph
from .fngraph import FNGraph
from ..paths import simple_paths as _simple_paths, shortest_simple_path as _shortest

__all__ = ["CGraph", "FNGraph"]


def _build_with_ports(
    self: CGraph,
    object_type: str,
    object_id: Union[int, str],
    port: Any = None,
    side: Optional[int] = None,
    included_fibers: Optional[Set[int]] = None,
    excluded_fibers: Optional[Set[int]] = None,
    excluded_nodes: Optional[Set[int]] = None,
    linear: bool = False,
    linear_on_fail: str = "raise",
) -> CGraph:
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


def _cgraph_simple_paths(
    self: CGraph,
    source: int,
    target: int,
    *,
    cutoff: Optional[int] = None,
    max_paths: Optional[int] = None,
) -> List[List[int]]:
    return _simple_paths(self, source, target, cutoff=cutoff, max_paths=max_paths)


def _cgraph_shortest_path(
    self: CGraph, source: int, target: int
) -> List[int]:
    return _shortest(self, source, target)


CGraph.build = _build_with_ports  # type: ignore[method-assign]
CGraph.simple_paths = _cgraph_simple_paths  # type: ignore[attr-defined]
CGraph.shortest_path = _cgraph_shortest_path  # type: ignore[attr-defined]
