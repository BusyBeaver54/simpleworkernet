# simpleworkernet/utils/topology/merge.py
"""Объединение нескольких CGraph / FNGraph."""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from .keys import Interface, ObjKey

if TYPE_CHECKING:
    from ...core.client import WorkerNetClient
    from .cache import DataCache
    from .graphs.cgraph import CGraph
    from .graphs.fngraph import FNGraph

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        from ...core.logger import log

        _logger = log
    return _logger


def merge_cgraphs(
    graphs: List["CGraph"],
    client: "WorkerNetClient",
    cache: "DataCache",
) -> Optional["CGraph"]:
    """
    Объединяет несколько CGraph в один, если они пересекаются по вершинам.

    Возвращает связный граф или None, если объединение несвязно.
    """
    from .graphs.cgraph import CGraph

    if not graphs:
        return None
    if len(graphs) == 1:
        return graphs[0]

    logger = _get_logger()
    merged = CGraph(client, cache=cache)
    iface_to_idx: Dict[Interface, int] = {}

    for g in graphs:
        # вершины
        for iface, old_idx in g._vertex_index.items():
            if iface in iface_to_idx:
                continue
            v = g.vs[old_idx]
            attrs = {k: v[k] for k in v.attributes()}
            idx = merged.add_vertex(**attrs).index
            iface_to_idx[iface] = idx
            merged._vertex_index[iface] = idx

        # рёбра
        for e in g.es:
            iface1 = iface2 = None
            for iface, idx in g._vertex_index.items():
                if idx == e.source:
                    iface1 = iface
                if idx == e.target:
                    iface2 = iface
                if iface1 is not None and iface2 is not None:
                    break
            if iface1 is None or iface2 is None:
                continue
            if iface1 not in iface_to_idx or iface2 not in iface_to_idx:
                continue
            i1, i2 = iface_to_idx[iface1], iface_to_idx[iface2]
            if not merged.are_connected(i1, i2):
                e_attrs = {k: e[k] for k in e.attributes()}
                merged.add_edge(i1, i2, **e_attrs)

    # finish_data
    for g in graphs:
        for key, data in getattr(g, "_finish_data", {}).items():
            merged._finish_data.setdefault(key, []).extend(data)

    merged.update_directed_flag()
    if merged.is_connected():
        return merged

    logger.warning("Объединённый CGraph не связный")
    return None


def merge_fngraphs(
    graphs: List["FNGraph"],
    client: "WorkerNetClient",
    cache: "DataCache",
) -> Optional["FNGraph"]:
    """Объединяет несколько FNGraph по node_id."""
    from .graphs.fngraph import FNGraph

    if not graphs:
        return None
    if len(graphs) == 1:
        return graphs[0]

    logger = _get_logger()
    merged = FNGraph(client, cache=cache)
    node_to_idx: Dict[int, int] = {}

    for g in graphs:
        for v in g.vs:
            node_id = v["node_id"]
            if node_id in node_to_idx:
                continue
            attrs = {k: v[k] for k in v.attributes()}
            idx = merged.add_vertex(**attrs).index
            node_to_idx[node_id] = idx
            merged._vertex_index[node_id] = idx

        for e in g.es:
            n1 = g.vs[e.source]["node_id"]
            n2 = g.vs[e.target]["node_id"]
            if n1 not in node_to_idx or n2 not in node_to_idx:
                continue
            i1, i2 = node_to_idx[n1], node_to_idx[n2]
            if not merged.are_connected(i1, i2):
                e_attrs = {k: e[k] for k in e.attributes()}
                merged.add_edge(i1, i2, **e_attrs)

    if merged.is_connected():
        return merged

    logger.warning("Объединённый FNGraph не связный")
    return None
