# simpleworkernet/utils/topology/attenuation/calculator_graph.py
"""Graph selection and path helpers for Attenuation."""
from __future__ import annotations
from typing import Any, List, Optional, Union
from .models import PathReport
from .errors import AttenuationError

VertexRef = Union[int, str, tuple]


class AttenuationGraphMixin:
    def _cgraph_has_object(
        self, cg: Any, obj_type: str, obj_id: Union[int, str],
        side: Optional[int] = None, port: Optional[int] = None,
    ) -> bool:
        if cg is None:
            return False
        try:
            vs = cg.vs
        except Exception:
            return False
        oid = str(obj_id)
        for v in vs:
            try:
                if v["obj_type"] != obj_type:
                    continue
                if str(v["obj_id"]) != oid:
                    continue
            except Exception:
                continue
            if side is not None:
                try:
                    if int(v["side"] if v["side"] is not None else 0) != int(side):
                        continue
                except Exception:
                    continue
            if port is not None:
                try:
                    if int(v["port"] if v["port"] is not None else 0) != int(port):
                        continue
                except Exception:
                    continue
            return True
        return False

    def _select_cgraph_for_objects(
        self, obj1_type: str, obj1_id: Union[int, str],
        obj2_type: Optional[str] = None, obj2_id: Optional[Union[int, str]] = None,
        *, obj1_side: Optional[int] = None, obj1_port: Optional[int] = None,
        obj2_side: Optional[int] = None, obj2_port: Optional[int] = None,
    ) -> None:
        graphs = list(self.cgraphs) if self.cgraphs else (
            [self.g] if self.g is not None else []
        )
        if not graphs:
            self.g = None
            return
        if len(graphs) == 1:
            self.g = graphs[0]
            return
        has_obj2 = obj2_type is not None and obj2_id is not None and obj2_id != ""
        both: List[Any] = []
        only1: List[Any] = []
        for cg in graphs:
            ok1 = self._cgraph_has_object(cg, obj1_type, obj1_id, side=obj1_side, port=obj1_port)
            if not ok1:
                ok1 = self._cgraph_has_object(cg, obj1_type, obj1_id)
            if not ok1:
                continue
            if has_obj2:
                ok2 = self._cgraph_has_object(cg, obj2_type, obj2_id, side=obj2_side, port=obj2_port)
                if not ok2:
                    ok2 = self._cgraph_has_object(cg, obj2_type, obj2_id)
                if ok2:
                    both.append(cg)
                else:
                    only1.append(cg)
            else:
                only1.append(cg)
        if both:
            self.g = both[0]
            return
        if only1:
            self.g = only1[0]
            return
        self.g = None

    def _dedupe_paths_by_endpoints(self, paths: List[List[int]]) -> List[List[int]]:
        from .calculator_paths import _DEVICE_TYPE_PRIORITY, _AUTO_TARGETS
        from ..constants import TYPE_CUSTOMER

        def _ends(path):
            if not path or self.g is None:
                return None, None, 99
            try:
                a = self.g.vs[path[0]]
                b = self.g.vs[path[-1]]
            except Exception:
                return None, None, 99
            ta, tb = a["obj_type"], b["obj_type"]
            ida, idb = str(a["obj_id"]), str(b["obj_id"])
            cust = dev = None
            dev_pri = 99
            for t, i in ((ta, ida), (tb, idb)):
                if t == TYPE_CUSTOMER:
                    cust = i
                elif t in _AUTO_TARGETS:
                    dev = i
                    dev_pri = min(dev_pri, _DEVICE_TYPE_PRIORITY.get(t, 99))
            return cust, dev, dev_pri

        best = {}
        order = []
        for p in paths:
            cust, dev, pri = _ends(p)
            key = (cust, dev)
            if key == (None, None):
                order.append((len(order), p))
                continue
            prev = best.get(key)
            if prev is None or pri < prev[0]:
                best[key] = (pri, p)
        out = [p for _, p in order]
        seen_keys = set()
        for p in paths:
            cust, dev, pri = _ends(p)
            key = (cust, dev)
            if key == (None, None):
                continue
            if key in seen_keys:
                continue
            chosen = best.get(key)
            if chosen and chosen[1] is p:
                out.append(p)
                seen_keys.add(key)
            elif chosen and key not in seen_keys:
                out.append(chosen[1])
                seen_keys.add(key)
        return out

    def _dedupe_device_vertices(self, indices: List[int]) -> List[int]:
        if self.g is None or not indices:
            return list(indices or [])
        from .calculator_paths import _DEVICE_TYPE_PRIORITY, _AUTO_TARGETS
        best = {}
        for idx in indices:
            try:
                v = self.g.vs[idx]
                ot = v["obj_type"]
                oid = str(v["obj_id"])
            except Exception:
                continue
            if ot not in _AUTO_TARGETS:
                best[f"_raw:{idx}"] = (99, idx)
                continue
            pri = _DEVICE_TYPE_PRIORITY.get(ot, 99)
            prev = best.get(oid)
            if prev is None or pri < prev[0]:
                best[oid] = (pri, idx)
        return [idx for _, idx in sorted(best.values(), key=lambda x: x[1])]

    def _vertices_of_types(self, types) -> List[int]:
        if self.g is None:
            return []
        out: List[int] = []
        for v in self.g.vs:
            if v["obj_type"] in types:
                out.append(int(v.index))
        return out

    def _leaf_vertices(self) -> List[int]:
        if self.g is None:
            return []
        leaves: List[int] = []
        for v in self.g.vs:
            idx = int(v.index)
            try:
                deg = self.g.degree(idx)
            except Exception:
                try:
                    deg = len(list(self.g.neighbors(idx)))
                except Exception:
                    deg = 0
            if deg == 1:
                leaves.append(idx)
        return leaves

    def _linear_cover_path(self) -> List[int]:
        leaves = self._leaf_vertices()
        if len(leaves) != 2:
            is_lin = getattr(self.g, "is_linear", None)
            if callable(is_lin):
                try:
                    if not is_lin():
                        return []
                except Exception:
                    pass
            if len(leaves) < 2:
                return []
        s, t = leaves[0], leaves[-1]
        return self.shortest_path(s, t)

    def path_report(
        self, source: VertexRef, target: VertexRef, *,
        direction: Optional[str] = None,
    ) -> PathReport:
        if self.g is None:
            raise AttenuationError("CGraph не задан")
        s = self.resolve_vertex(source) if not isinstance(source, int) else source
        t = self.resolve_vertex(target) if not isinstance(target, int) else target
        if s is None or t is None:
            raise AttenuationError("не удалось разрешить вершины пути")
        vpath = self.shortest_path(s, t)
        if not vpath:
            raise AttenuationError("нет пути между вершинами")
        return self._report_from_vpath(vpath, direction=direction)
