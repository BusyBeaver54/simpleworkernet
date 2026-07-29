# simpleworkernet/utils/topology/linear.py
"""Построение линейной цепочки (topology_from_commutation)."""

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
            cg for cg in self.topology.cgraphs if last_iface in cg._vertex_index
        ]
        if not candidates:
            raise ValueError(f"Интерфейс {last_iface} не найден в графах")

        selected = candidates[0]
        if first_object_type and first_object_id is not None:
            for cg in candidates:
                for v in cg.vs:
                    if (
                        v["obj_type"] == first_object_type
                        and str(v["obj_id"]) == str(first_object_id)
                    ):
                        selected = cg
                        break

        path = self._walk(
            selected, last_iface, first_object_type, first_object_id
        )
        return self._build_linear(selected, path)

    def _walk(
        self,
        cg: CGraph,
        start: Interface,
        first_type: Optional[str],
        first_id: Optional[Union[int, str]],
    ) -> List[Interface]:
        current = start
        prev: Optional[Interface] = None
        path = [current]

        while True:
            cur_idx = cg._vertex_index[current]
            attrs = cg.vs[cur_idx].attributes()
            cur_type = attrs["obj_type"]

            external, internal = [], []
            for eid in cg.incident(cur_idx, mode="all"):
                edge = cg.es[eid]
                n_idx = edge.target if edge.source == cur_idx else edge.source
                n_iface = None
                for iface, i in cg._vertex_index.items():
                    if i == n_idx:
                        n_iface = iface
                        break
                if n_iface is None or n_iface == prev:
                    continue
                if edge.attributes().get("is_internal"):
                    internal.append(n_iface)
                else:
                    external.append(n_iface)

            next_iface = None
            if len(external) == 1:
                next_iface = external[0]
            elif len(external) > 1:
                return self._shortest(
                    cg, cur_idx, path, first_type, first_id
                )
            elif len(internal) == 1:
                next_iface = internal[0]
            elif len(internal) > 1:
                return self._shortest(
                    cg, cur_idx, path, first_type, first_id
                )
            else:
                # тупик
                if cur_type in (TYPE_OLT, TYPE_SWITCH):
                    break
                if (
                    first_type
                    and first_id is not None
                    and cur_type == first_type
                    and str(attrs["obj_id"]) == str(first_id)
                ):
                    break
                raise ValueError(
                    f"Тупик на {cur_type}:{attrs['obj_id']} без OLT/switch"
                )

            if next_iface is None:
                break

            nt = next_iface.obj.obj_type
            if nt == TYPE_CWDM:
                raise ValueError("Линейный граф через CWDM не поддерживается")
            path.append(next_iface)
            if nt in (TYPE_OLT, TYPE_SWITCH):
                break
            if nt in DEVICE_TYPES and nt not in (TYPE_OLT, TYPE_SWITCH):
                raise ValueError(f"Неожиданное устройство {nt} на пути")
            if (
                first_type
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
            # восстановить _vertex_index
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
