# simpleworkernet/utils/topology/linear.py
"""Построение линейной цепочки (LinearPathFinder)."""

from __future__ import annotations

from typing import List, Optional, Union

from .constants import (
    DEVICE_TYPES,
    SIDE_TYPES,
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
from .ports_spec import expand_ports


def _deg(graph, v: int) -> int:
    try:
        return int(graph.degree(v))
    except Exception:
        return len(list(graph.neighbors(v)))


def _is_splitter_like(obj_type: str) -> bool:
    return obj_type in (TYPE_SPLITTER, TYPE_CWDM)


def _port_matches(vattrs: dict, allowed: Optional[set]) -> bool:
    if allowed is None:
        return True
    try:
        p = int(vattrs.get("port") or 0)
    except (TypeError, ValueError):
        return False
    return p in allowed


class LinearPathFinder:
    """Извлекает линейный CGraph из уже построенных графов NetworkTopology."""

    def __init__(self, topology) -> None:
        self.topology = topology

    def _require_graphs(self) -> None:
        cgraphs = getattr(self.topology, "cgraphs", None) or []
        if not cgraphs:
            raise ValueError(
                "Нет CGraph. Сначала NetworkTopology.build_from_*"
            )

    def _pick_cgraph(self, start_type: str, start_id, port, side):
        from .graphs.cgraph import CGraph

        cgraphs = self.topology.cgraphs
        oid = str(start_id)
        for cg in cgraphs:
            for v in cg.vs:
                if v["obj_type"] != start_type:
                    continue
                if str(v["obj_id"]) != oid:
                    continue
                if side is not None:
                    try:
                        if int(v["side"] or 0) != int(side):
                            continue
                    except Exception:
                        continue
                if port is not None:
                    try:
                        if int(v["port"] or 0) != int(port):
                            continue
                    except Exception:
                        continue
                return cg
        return cgraphs[0] if cgraphs else None

    def _start_vertex(self, cg, start_type, start_id, port, side):
        oid = str(start_id)
        candidates = []
        for v in cg.vs:
            if v["obj_type"] != start_type or str(v["obj_id"]) != oid:
                continue
            if side is not None:
                try:
                    if int(v["side"] or 0) != int(side):
                        continue
                except Exception:
                    continue
            if port is not None:
                try:
                    if int(v["port"] or 0) != int(port):
                        continue
                except Exception:
                    continue
            candidates.append(int(v.index))
        if not candidates:
            raise ValueError(f"вершина {start_type}:{start_id} не найдена в CGraph")
        return candidates[0]

    def _walk_linear(self, cg, start: int) -> List[int]:
        path = [start]
        prev = None
        cur = start
        while True:
            nbrs = [int(n) for n in cg.neighbors(cur) if int(n) != prev]
            if not nbrs:
                break
            if len(nbrs) > 1:
                # неоднозначность — останавливаемся на ветвлении
                break
            nxt = nbrs[0]
            path.append(nxt)
            prev, cur = cur, nxt
        return path

    def trace(
        self,
        start_type: str,
        start_id: Union[int, str],
        *,
        port: Optional[int] = None,
        side: Optional[int] = None,
        cgraph_index: Optional[int] = None,
    ):
        """Линейный подграф CGraph от стартового объекта."""
        self._require_graphs()

        if start_type in (TYPE_SPLITTER, TYPE_CWDM) and port is None:
            raise ValueError("для splitter/cwdm укажите порт")

        if start_type in SIDE_TYPES and side is None and start_type != TYPE_CUSTOMER:
            if start_type in (TYPE_FIBER, TYPE_CROSS):
                raise ValueError("для fiber/cross укажите side")

        if cgraph_index is not None:
            cg = self.topology.cgraphs[cgraph_index]
        else:
            cg = self._pick_cgraph(start_type, start_id, port, side)
        if cg is None:
            raise ValueError("CGraph не найден")

        start = self._start_vertex(cg, start_type, start_id, port, side)
        path = self._walk_linear(cg, start)

        # индуцированный подграф
        try:
            sub = cg.subgraph(path)
        except Exception:
            # fallback: копия через induced
            sub = cg.induced_subgraph(path)
        return sub
