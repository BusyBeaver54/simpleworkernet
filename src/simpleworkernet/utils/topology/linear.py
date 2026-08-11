# simpleworkernet/utils/topology/linear.py
"""Построение линейной цепочки (LinearPathFinder)."""

from __future__ import annotations

from typing import List, Optional, Set, Tuple, Union

from .constants import (
    DEVICE_TYPES,
    SIDE_TYPES,
    TERMINAL_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_CWDM,
    TYPE_FIBER,
    TYPE_OLT,
    TYPE_SPLITTER,
    TYPE_SWITCH,
)
from .errors import TopologyBuildError
from .keys import Interface, ObjKey
from .graphs.cgraph import CGraph


class LinearPathFinder:
    """Извлекает линейный подграф из уже построенных CGraph NetworkTopology."""

    def __init__(self, topology) -> None:
        self.topology = topology
        self.client = getattr(topology, "client", None)
        self.cache = getattr(topology, "cache", None)

    def _require_graphs(self) -> List:
        cgraphs = getattr(self.topology, "cgraphs", None) or []
        if not cgraphs:
            raise ValueError(
                "Нет построенных CGraph. Сначала вызовите build_from_*"
            )
        return cgraphs

    def _find_vertices(
        self, cg, obj_type: str, obj_id, port=None, side=None,
    ) -> List[int]:
        oid = str(obj_id)
        found: List[int] = []
        for v in cg.vs:
            attrs = v.attributes()
            if attrs.get("obj_type") != obj_type:
                continue
            if str(attrs.get("obj_id")) != oid:
                continue
            if side is not None:
                try:
                    if int(attrs.get("side") or 0) != int(side):
                        continue
                except (TypeError, ValueError):
                    continue
            if port is not None:
                try:
                    if int(attrs.get("port") or 0) != int(port):
                        continue
                except (TypeError, ValueError):
                    continue
            found.append(int(v.index))
        return found

    def _pick_cgraph(self, obj_type, obj_id, port, side):
        for cg in self._require_graphs():
            if self._find_vertices(cg, obj_type, obj_id, port, side):
                return cg
        return self._require_graphs()[0]

    def _walk(self, cg, start: int) -> List[int]:
        path = [start]
        prev = None
        cur = start
        for _ in range(10000):
            nbrs = [
                int(n) for n in cg.neighbors(cur)
                if prev is None or int(n) != prev
            ]
            if not nbrs:
                break
            if len(nbrs) > 1:
                break
            nxt = nbrs[0]
            path.append(nxt)
            prev, cur = cur, nxt
        return path

    def _induced_linear(self, source: CGraph, path_indices: List[int]) -> CGraph:
        """Индуцированный подграф с сохранением атрибутов и _vertex_index."""
        linear = CGraph(self.client, cache=self.cache)
        index_map = {}
        for idx in path_indices:
            attrs = {k: source.vs[idx][k] for k in source.vs[idx].attributes()}
            new_idx = linear.add_vertex(**attrs)
            # igraph may return VertexSeq-like; normalize
            try:
                new_idx = int(new_idx)
            except (TypeError, ValueError):
                new_idx = linear.vcount() - 1
            index_map[idx] = new_idx
            for iface, i in getattr(source, "_vertex_index", {}).items():
                if i == idx:
                    linear._vertex_index[iface] = new_idx
                    break

        for i in range(len(path_indices) - 1):
            a, b = path_indices[i], path_indices[i + 1]
            eid = source.get_eid(a, b, error=False)
            if eid == -1:
                eid = source.get_eid(b, a, error=False)
            if eid != -1:
                e_attrs = {
                    k: source.es[eid][k] for k in source.es[eid].attributes()
                }
                linear.add_edge(index_map[a], index_map[b], **e_attrs)

        if hasattr(linear, "update_directed_flag"):
            linear.update_directed_flag()
        return linear

    def trace(
        self,
        start_type: str,
        start_id: Union[int, str],
        *,
        port: Optional[int] = None,
        side: Optional[int] = None,
        cgraph_index: Optional[int] = None,
    ) -> CGraph:
        """Линейный CGraph от стартового объекта до ветвления / конца."""
        cgraphs = self._require_graphs()

        if start_type in (TYPE_SPLITTER, TYPE_CWDM) and port is None:
            raise ValueError("Для splitter/cwdm необходимо указать порт")
        if start_type in (TYPE_FIBER, TYPE_CROSS) and side is None:
            raise ValueError("Для fiber/cross необходимо указать side")

        if cgraph_index is not None:
            if cgraph_index < 0 or cgraph_index >= len(cgraphs):
                raise ValueError(f"cgraph_index={cgraph_index} вне диапазона")
            cg = cgraphs[cgraph_index]
        else:
            cg = self._pick_cgraph(start_type, start_id, port, side)

        starts = self._find_vertices(cg, start_type, start_id, port, side)
        if not starts:
            raise ValueError(
                f"Объект {start_type}:{start_id} не найден в CGraph"
            )

        path = self._walk(cg, starts[0])
        return self._induced_linear(cg, path)
