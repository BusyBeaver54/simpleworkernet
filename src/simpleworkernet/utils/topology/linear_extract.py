# simpleworkernet/utils/topology/linear_extract.py
"""Извлечение линейного подграфа из CGraph / FNGraph."""
from __future__ import annotations
from typing import Any, List, Optional, Sequence, Set, Tuple, Union
from .errors import TopologyBuildError
from .keys import Interface, ObjKey
from .constants import TERMINAL_TYPES

def find_vertices_by_obj(cg, obj_type, obj_id, side=None, port=None):
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

def subgraph_from_vpath(source_cg, vpath: Sequence[int]):
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

def _neighbors(cg, idx):
    out = []
    try:
        for eid in cg.incident(idx, mode="all"):
            edge = cg.es[eid]
            out.append(edge.target if edge.source == idx else edge.source)
    except Exception:
        pass
    return out

def _all_simple_paths(cg, source, target, cutoff=200):
    results = []
    stack = [(source, [source])]
    while stack:
        node, path = stack.pop()
        if len(path) > cutoff:
            continue
        for n in _neighbors(cg, node):
            if n in path:
                continue
            npath = path + [n]
            if n == target:
                results.append(npath)
                if len(results) > 1:
                    return results
            else:
                stack.append((n, npath))
    return results

def _walk_unique(cg, start):
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
                paths = _all_simple_paths(cg, s, e)
                if len(paths) > 1:
                    raise TopologyBuildError(
                        f"ветвление: {len(paths)} путей между {start_type}:{start_id} и {end_type}:{end_id}"
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
            try:
                deg = fn.degree(idx)
            except Exception:
                deg = len(_neighbors(fn, idx))
            if deg <= 1:
                leaves.append(nid)
        if not leaves:
            raise TopologyBuildError("FNGraph: нет конечных узлов")
        if len(leaves) > 1:
            raise TopologyBuildError(
                f"FNGraph: листьев={len(leaves)}, укажите end_node_id"
            )
        end_node_id = leaves[0]
    if end_node_id not in node_to_v:
        raise TopologyBuildError(f"узел {end_node_id} не в FNGraph")
    s, e = node_to_v[start_node_id], node_to_v[end_node_id]
    paths = _all_simple_paths(fn, s, e)
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
