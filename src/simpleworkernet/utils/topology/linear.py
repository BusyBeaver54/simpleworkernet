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


class LinearPathFinder:
    """Поиск линейного пути в CGraph от стартового объекта."""

    def __init__(self, topology) -> None:
        self.topology = topology
        self.client = topology.client
        self.cache = topology.cache

    def _graphs(self):
        cgraphs = getattr(self.topology, "cgraphs", None) or []
        if not cgraphs:
            raise ValueError(
                "Нет построенных CGraph. Сначала вызовите build_from_*"
            )
        return cgraphs

    def _find_start(self, cg, obj_type, obj_id, port, side):
        oid = str(obj_id)
        found = []
        for v in cg.vs:
            if v["obj_type"] != obj_type or str(v["obj_id"]) != oid:
                continue
            if side is not None:
                try:
                    if int(v.attributes().get("side") or 0) != int(side):
                        continue
                except Exception:
                    continue
            if port is not None:
                try:
                    if int(v.attributes().get("port") or 0) != int(port):
                        continue
                except Exception:
                    continue
            found.append(int(v.index))
        return found

    def _walk(self, cg, start: int) -> List[int]:
        path = [start]
        prev = None
        cur = start
        guard = 0
        while guard < 10000:
            guard += 1
            nbrs = [int(n) for n in cg.neighbors(cur) if prev is None or int(n) != prev]
            if not nbrs:
                break
            if len(nbrs) > 1:
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
        cgraph_index: int = 0,
    ):
        cgraphs = self._graphs()
        if start_type in (TYPE_SPLITTER, TYPE_CWDM) and port is None:
            raise ValueError("Для splitter/cwdm необходимо указать порт")
        if start_type in (TYPE_FIBER, TYPE_CROSS) and side is None:
            raise ValueError("Для fiber/cross необходимо указать side")

        if cgraph_index < 0 or cgraph_index >= len(cgraphs):
            cg = None
            for g in cgraphs:
                if self._find_start(g, start_type, start_id, port, side):
                    cg = g
                    break
            if cg is None:
                cg = cgraphs[0]
        else:
            cg = cgraphs[cgraph_index]

        starts = self._find_start(cg, start_type, start_id, port, side)
        if not starts:
            raise ValueError(
                f"Объект {start_type}:{start_id} не найден в CGraph"
            )
        path = self._walk(cg, starts[0])
        try:
            return cg.subgraph(path)
        except Exception:
            return cg.induced_subgraph(path)
