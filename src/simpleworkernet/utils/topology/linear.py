# simpleworkernet/utils/topology/linear.py
"""Построение линейной цепочки (LinearPathFinder)."""

from __future__ import annotations
from .paths import simple_paths, neighbors_undirected
from .errors import TopologyBuildError

from typing import Any, Sequence, List, Optional, Union

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

# ---------------------------------------------------------------------------
# extract linear subgraphs (ex-linear_extract.py)
# ---------------------------------------------------------------------------

def find_vertices_by_obj(
    cg: Any,
    obj_type: str,
    obj_id: Union[int, str],
    side: Optional[int] = None,
    port: Optional[int] = None,
) -> List[int]:
    hits = []
    for v in cg.vs:
        if v["obj_type"] != obj_type or str(v["obj_id"]) != str(obj_id):
            continue
        if side is not None and int(v["side"]) != int(side):
            continue
        if port is not None and int(v["port"]) != int(port):
            continue
        hits.append(v.index)
    return hits

def subgraph_from_vpath(source_cg: Any, vpath: Sequence[int]) -> Any:
    from .graphs.cgraph import CGraph
    linear = CGraph(source_cg.client, cache=source_cg.cache)
    index_map = {}
    for idx in vpath:
        attrs = {k: source_cg.vs[idx][k] for k in source_cg.vs[idx].attributes()}
        new_idx = linear.add_vertex(**attrs).index
        index_map[idx] = new_idx
        ot, oid = attrs["obj_type"], attrs["obj_id"]
        try:
            oid_cast: Union[int, str] = int(oid)
        except (TypeError, ValueError):
            oid_cast = oid
        iface = Interface(ObjKey(ot, oid_cast), int(attrs.get("side", 1)), int(attrs.get("port", 0)))
        linear._vertex_index[iface] = new_idx
    for a, b in zip(vpath, vpath[1:]):
        try:
            eid = source_cg.get_eid(a, b, error=False)
        except Exception:
            eid = -1
        if eid is None or eid < 0:
            try:
                eid = source_cg.get_eid(b, a, error=False)
            except Exception:
                eid = -1
        if eid is None or eid < 0:
            continue
        e_attrs = {k: source_cg.es[eid][k] for k in source_cg.es[eid].attributes()}
        linear.add_edge(index_map[a], index_map[b], **e_attrs)
    linear.update_directed_flag()
    return linear

def _neighbors(cg: Any, idx: int) -> List[int]:
    return neighbors_undirected(cg, idx)

def _all_simple_paths(cg, source, target, cutoff=200):
    """Обёртка: все простые пути, early-stop при 2+ (для проверки ветвления)."""
    return simple_paths(cg, source, target, cutoff=cutoff, max_paths=2)

def _walk_unique(cg: Any, start: int) -> List[int]:
    path = [start]
    prev = None
    current = start
    visited = {start}
    while True:
        nbrs = [n for n in _neighbors(cg, current) if n != prev]
        forward = [n for n in nbrs if n not in visited]
        if not forward:
            return path
        if len(forward) > 1:
            types = [cg.vs[n]["obj_type"] for n in forward]
            raise TopologyBuildError(
                f"ветвление в {cg.vs[current]['obj_type']}:{cg.vs[current]['obj_id']} "
                f"(соседи types={types})"
            )
        nxt = forward[0]
        path.append(nxt)
        visited.add(nxt)
        attrs = cg.vs[nxt].attributes()
        if attrs.get("terminate_vertex") or attrs.get("obj_type") in TERMINAL_TYPES:
            more = [n for n in _neighbors(cg, nxt) if n not in visited]
            if not more:
                return path
            if attrs.get("obj_type") in TERMINAL_TYPES and len(path) > 1:
                return path
        prev, current = current, nxt

def extract_linear_cgraph(cg, start_type, start_id, end_type=None, end_id=None, *, port=None, side=None):
    from .ports_spec import expand_ports
    allowed = expand_ports(port)
    port_one = next(iter(allowed)) if allowed is not None and len(allowed) == 1 else None
    starts = find_vertices_by_obj(cg, start_type, start_id, side=side, port=port_one)
    if not starts and allowed:
        for p in sorted(allowed):
            starts = find_vertices_by_obj(cg, start_type, start_id, side=side, port=p)
            if starts:
                break
    if not starts:
        starts = find_vertices_by_obj(cg, start_type, start_id, side=side)
    if not starts:
        raise TopologyBuildError(f"объект не найден в CGraph: {start_type}:{start_id}")
    if end_type is not None and end_id is not None:
        ends = find_vertices_by_obj(cg, end_type, end_id)
        if not ends:
            raise TopologyBuildError(f"объект не найден в CGraph: {end_type}:{end_id}")
        best = None
        for s in starts:
            for e in ends:
                if s == e:
                    return subgraph_from_vpath(cg, [s])
                # max_paths=2: достаточно чтобы обнаружить ветвление
                paths = simple_paths(cg, s, e, max_paths=2)
                if len(paths) > 1:
                    raise TopologyBuildError(
                        f"ветвление: несколько путей между {start_type}:{start_id} и {end_type}:{end_id}"
                    )
                if len(paths) == 1 and (best is None or len(paths[0]) < len(best)):
                    best = paths[0]
        if best is None:
            raise TopologyBuildError(f"нет пути между {start_type}:{start_id} и {end_type}:{end_id}")
        return subgraph_from_vpath(cg, best)
    if len(starts) > 1 and side is None and port_one is None:
        candidates, errors = [], []
        for s in starts:
            try:
                candidates.append(_walk_unique(cg, s))
            except TopologyBuildError as ex:
                errors.append(str(ex))
        if not candidates:
            raise TopologyBuildError(errors[0] if errors else "не удалось выбрать линейный путь")
        keys = {tuple(p) for p in candidates}
        if len(keys) > 1:
            raise TopologyBuildError(
                f"неоднозначный старт {start_type}:{start_id}: {len(keys)} путей"
            )
        return subgraph_from_vpath(cg, candidates[0])
    return subgraph_from_vpath(cg, _walk_unique(cg, starts[0]))

def extract_linear_fngraph(fn, start_node_id, end_node_id=None):
    from .graphs.fngraph import FNGraph
    node_to_v = {int(v["node_id"]): v.index for v in fn.vs}
    if start_node_id not in node_to_v:
        raise TopologyBuildError(f"узел {start_node_id} не в FNGraph")
    if end_node_id is None:
        leaves = []
        for nid, idx in node_to_v.items():
            if nid == start_node_id:
                continue
            deg = len(_neighbors(fn, idx))
            if deg <= 1:
                leaves.append(nid)
        if not leaves:
            raise TopologyBuildError("FNGraph: нет конечных узлов")
        if len(leaves) > 1:
            raise TopologyBuildError(f"FNGraph: листьев={len(leaves)}, укажите end_node_id")
        end_node_id = leaves[0]
    if end_node_id not in node_to_v:
        raise TopologyBuildError(f"узел {end_node_id} не в FNGraph")
    s, e = node_to_v[start_node_id], node_to_v[end_node_id]
    paths = simple_paths(fn, s, e, max_paths=2)
    if not paths:
        raise TopologyBuildError(f"нет FN-пути {start_node_id}↔{end_node_id}")
    if len(paths) > 1:
        raise TopologyBuildError(f"ветвление FNGraph: {len(paths)} путей")
    vpath = paths[0]
    linear = FNGraph(fn.client, cache=fn.cache)
    index_map = {}
    for idx in vpath:
        attrs = {k: fn.vs[idx][k] for k in fn.vs[idx].attributes()}
        index_map[idx] = linear.add_vertex(**attrs).index
    for a, b in zip(vpath, vpath[1:]):
        try:
            eid = fn.get_eid(a, b, error=False)
        except Exception:
            eid = -1
        if eid is None or eid < 0:
            continue
        e_attrs = {k: fn.es[eid][k] for k in fn.es[eid].attributes()}
        linear.add_edge(index_map[a], index_map[b], **e_attrs)
    return linear
