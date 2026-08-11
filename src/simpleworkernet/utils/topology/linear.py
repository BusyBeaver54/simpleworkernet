# simpleworkernet/utils/topology/linear.py
"""Построение линейной цепочки (LinearPathFinder)."""

from __future__ import annotations

from typing import List, Optional, Union

from .constants import (
    DEVICE_TYPES,
    SIDE_TYPES,
    TERMINAL_TYPES,
    TYPE_CWDM,
    TYPE_OLT,
    TYPE_SPLITTER,
    TYPE_SWITCH,
)
from .keys import Interface, ObjKey
from .graphs.cgraph import CGraph


class LinearPathFinder:
    """
    Строит линейный путь от last-объекта к first/корню (OLT|switch).

    Предпочитает external-рёбра, иначе internal; при ветвлении — shortest_path.
    """

    def __init__(self, topology) -> None:
        self.topology = topology
        self.logger = topology.logger

    def trace(
        self,
        last_object_type: str,
        last_object_id: Union[int, str],
        port: Optional[int] = None,
        side: Optional[int] = None,
        first_object_type: Optional[str] = None,
        first_object_id: Optional[Union[int, str]] = None,
    ) -> CGraph:
        if not self.topology.cgraphs:
            raise ValueError(
                "Нет построенных графов. Сначала вызовите build_from_*"
            )

        if last_object_type == TYPE_SPLITTER and port is None:
            raise ValueError("Для сплиттера порт обязателен")
        if last_object_type in SIDE_TYPES and side is None:
            raise ValueError(
                f"Для объекта {last_object_type} необходимо указать сторону (side)"
            )

        last_key = ObjKey(last_object_type, last_object_id)

        if last_object_type in TERMINAL_TYPES:
            if port is None:
                comms = self.topology._get_commutations(
                    last_object_type, last_object_id
                )
                if len(comms) > 1 and (
                    first_object_type is None or first_object_id is None
                ):
                    raise ValueError(
                        f"Объект {last_object_type}:{last_object_id} имеет "
                        "несколько коммутаций — укажите first_object"
                    )
                p = (
                    int(comms[0].clps_first)
                    if comms and comms[0].clps_first is not None
                    else 1
                )
                last_iface = Interface(last_key, side=1, port=p)
            else:
                last_iface = Interface(last_key, side=1, port=port)
        else:
            if port is None or side is None:
                raise ValueError("Для SIDE-объекта нужны port и side")
            last_iface = Interface(last_key, side=side, port=port)

        candidates = [
            g for g in self.topology.cgraphs
            if last_iface in getattr(g, "_vertex_index", {})
        ]
        if not candidates:
            candidates = list(self.topology.cgraphs)
        cg = candidates[0]

        if last_iface not in cg._vertex_index:
            # fallback: find by attributes
            found = None
            for iface, idx in cg._vertex_index.items():
                if (
                    iface.obj.obj_type == last_object_type
                    and str(iface.obj.id) == str(last_object_id)
                ):
                    if port is not None and iface.port != port:
                        continue
                    if side is not None and iface.side != side:
                        continue
                    found = iface
                    break
            if found is None:
                raise ValueError(
                    f"Объект {last_object_type}:{last_object_id} не найден в CGraph"
                )
            last_iface = found

        path = self._walk(
            cg, last_iface, first_object_type, first_object_id
        )
        return self._build_linear(cg, path)

    def _walk(
        self,
        cg: CGraph,
        start: Interface,
        first_type: Optional[str],
        first_id: Optional[Union[int, str]],
    ) -> List[Interface]:
        path: List[Interface] = [start]
        prev = None
        current = start

        for _ in range(10000):
            cur_idx = cg._vertex_index.get(current)
            if cur_idx is None:
                break

            external = []
            internal = []
            for eid in cg.incident(cur_idx, mode="all"):
                e = cg.es[eid]
                src, tgt = e.source, e.target
                other = tgt if src == cur_idx else src
                if prev is not None and other == cg._vertex_index.get(prev):
                    continue
                is_internal = bool(e.attributes().get("is_internal"))
                other_iface = None
                for iface, i in cg._vertex_index.items():
                    if i == other:
                        other_iface = iface
                        break
                if other_iface is None:
                    continue
                (internal if is_internal else external).append(other_iface)

            candidates = external or internal
            if not candidates:
                break
            if len(candidates) > 1:
                return self._shortest(
                    cg, cur_idx, path, first_type, first_id
                )

            next_iface = candidates[0]
            path.append(next_iface)

            nt = next_iface.obj.obj_type
            if nt in (TYPE_OLT, TYPE_SWITCH):
                break
            if (
                first_type is not None
                and first_id is not None
                and nt == first_type
                and str(next_iface.obj.id) == str(first_id)
            ):
                break
            prev, current = current, next_iface

        return path

    def _shortest(
        self,
        cg: CGraph,
        from_idx: int,
        path_so_far: List[Interface],
        first_type: Optional[str],
        first_id: Optional[Union[int, str]],
    ) -> List[Interface]:
        if not first_type or first_id is None:
            raise ValueError(
                "Ветвление: укажите first_object для выбора направления"
            )
        target_idx = None
        for v in cg.vs:
            if v["obj_type"] == first_type and str(v["obj_id"]) == str(first_id):
                target_idx = v.index
                break
        if target_idx is None:
            raise ValueError(f"Целевой объект {first_type}:{first_id} не найден")

        paths = cg.get_shortest_paths(from_idx, target_idx, mode="all")
        if not paths or not paths[0]:
            raise ValueError("Путь не найден")

        result = list(path_so_far)
        for idx in paths[0][1:]:
            for iface, i in cg._vertex_index.items():
                if i == idx:
                    result.append(iface)
                    break
        return result

    def _build_linear(self, source: CGraph, path: List[Interface]) -> CGraph:
        linear = CGraph(self.topology.client, cache=self.topology.cache)
        index_map = {}
        path_indices = [source._vertex_index[iface] for iface in path]

        for idx in path_indices:
            attrs = {k: source.vs[idx][k] for k in source.vs[idx].attributes()}
            new_idx = linear.add_vertex(**attrs).index
            index_map[idx] = new_idx
            for iface, i in source._vertex_index.items():
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

        linear.update_directed_flag()
        return linear
