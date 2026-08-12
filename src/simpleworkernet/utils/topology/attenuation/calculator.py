# simpleworkernet/utils/topology/attenuation/calculator.py
"""Attenuation — calculate() between objects or over entire CGraph."""
from __future__ import annotations
from typing import Any, List, Optional, Sequence, Tuple, Union
from ..keys import Interface
from ..constants import (
    TYPE_CUSTOMER, TYPE_OLT, TYPE_ONU, TYPE_RADIO, TYPE_SWITCH,
    TERMINAL_TYPES,
)
from .catalog import AttenuationCatalog
from .models import PathReport
from .multipath import MultiPathReport
from .calculator_segments import AttenuationSegmentsMixin, _label_vertex
from .calculator_path import AttenuationPathMixin
from .calculator_edge import AttenuationEdgeMixin
from .calculator_build import AttenuationBuildMixin
from .calculator_fn import AttenuationFNMixin
from .calculator_fiber import AttenuationFiberMixin
from .calculator_paths import AttenuationPathsMixin
from .errors import AttenuationError

VertexRef = Union[int, Interface, Tuple[str, Union[int, str], int, int], str]

_SINK_TYPES = frozenset({TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO})
_SOURCE_TYPES = frozenset({TYPE_CUSTOMER}) | _SINK_TYPES


def _is_network_topology(obj: Any) -> bool:
    if obj is None:
        return False
    cgraphs = getattr(obj, "cgraphs", None)
    return isinstance(cgraphs, list) and hasattr(obj, "client")


def _is_cgraph_like(obj: Any) -> bool:
    if obj is None:
        return False
    return hasattr(obj, "vs") and (
        hasattr(obj, "vcount") or hasattr(obj, "get_eid") or hasattr(obj, "es")
    )


class Attenuation(
    AttenuationBuildMixin,
    AttenuationFNMixin,
    AttenuationFiberMixin,
    AttenuationSegmentsMixin,
    AttenuationEdgeMixin,
    AttenuationPathMixin,
    AttenuationPathsMixin,
):
    def __init__(
        self,
        graph: Any = None,
        *,
        catalog: Optional[AttenuationCatalog] = None,
        wavelength: int = 1550,
        cache: Any = None,
        client: Any = None,
        # устаревшие алиасы (graph предпочтителен)
        cgraph: Any = None,
        topology: Any = None,
    ) -> None:
        """graph — CGraph или NetworkTopology (единственный входной граф).

        cgraph=/topology= оставлены как алиасы graph= для совместимости.
        """
        self.topology: Any = None
        self.cgraphs: List[Any] = []
        self.g: Any = None

        self.wavelength = int(wavelength)
        # min/max/avg считаются всегда; use_max больше не используется
        self.use_max = False

        src = graph if graph is not None else (topology if topology is not None else cgraph)
        self._bind_graphs(
            cgraph=None if _is_network_topology(src) else src,
            topology=src if _is_network_topology(src) else None,
        )

        if client is not None:
            self.client = client
        elif self.topology is not None:
            self.client = getattr(self.topology, "client", None)
        elif self.g is not None:
            self.client = getattr(self.g, "client", None)
        elif self.cgraphs:
            self.client = getattr(self.cgraphs[0], "client", None)
        else:
            self.client = None

        if cache is not None:
            self.cache = cache
        elif self.topology is not None:
            self.cache = getattr(self.topology, "cache", None)
        elif self.g is not None:
            self.cache = getattr(self.g, "cache", None)
        elif self.cgraphs:
            self.cache = getattr(self.cgraphs[0], "cache", None)
        else:
            self.cache = None

        if catalog is not None:
            self.catalog = catalog
        else:
            loaded = None
            if self.client is not None:
                try:
                    from .template import load_attenuation_catalog
                    loaded = load_attenuation_catalog(self.client)
                except Exception:
                    loaded = None
            self.catalog = loaded or AttenuationCatalog.with_defaults()

    def _bind_graphs(self, *, cgraph: Any = None, topology: Any = None) -> None:
        self.topology = None
        self.cgraphs = []
        self.g = None

        src = topology if topology is not None else cgraph
        if src is None:
            return

        if topology is not None and cgraph is not None and topology is not cgraph:
            src = topology

        if _is_network_topology(src):
            self.topology = src
            self.cgraphs = [cg for cg in (src.cgraphs or []) if cg is not None]
            if len(self.cgraphs) == 1:
                self.g = self.cgraphs[0]
            return

        if isinstance(src, (list, tuple)):
            self.cgraphs = [cg for cg in src if cg is not None]
            if len(self.cgraphs) == 1:
                self.g = self.cgraphs[0]
            return

        if _is_cgraph_like(src):
            self.cgraphs = [src]
            self.g = src
            return

        self.cgraphs = [src]
        self.g = src

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

    def calculate(
        self,
        obj1_type: Optional[str] = None,
        obj1_id: Optional[Union[int, str]] = None,
        obj2_type: Optional[str] = None,
        obj2_id: Optional[Union[int, str]] = None,
        *,
        wavelength: Optional[int] = None,
        obj1_side: Optional[int] = None,
        obj1_port: Optional[int] = None,
        obj2_side: Optional[int] = None,
        obj2_port: Optional[int] = None,
        direction: Optional[str] = None,
        max_paths: Optional[int] = None,
    ):
        """Расчёт затухания. Всегда MultiPathReport.

        direction:
          * ``"upstream"`` — от OLT/device к абоненту
          * ``"downstream"`` — от абонента к OLT/device
          * ``None`` / ``"unknown"`` — как найден путь (от first object)

        max_paths=None — все терминалы; для full_cgraph берётся кратчайший путь
        (уникальный в дереве PON). all_simple_paths — только при between_objects
        и max_paths>1.
        """
        prev_wl = self.wavelength
        if wavelength is not None:
            self.wavelength = int(wavelength)
        try:
            has_obj1 = obj1_type is not None and obj1_id is not None and obj1_id != ""
            if not has_obj1:
                return self._calculate_all_graphs(direction=direction, max_paths=max_paths)

            self._require_fiber_port(
                obj1_type, obj1_id, obj1_port, obj2_type, obj2_id, obj2_port,
                obj1_side=obj1_side, obj2_side=obj2_side,
            )
            self._select_cgraph_for_objects(
                obj1_type, obj1_id, obj2_type, obj2_id,
                obj1_side=obj1_side, obj1_port=obj1_port,
                obj2_side=obj2_side, obj2_port=obj2_port,
            )
            self._ensure_cgraph(
                obj1_type, obj1_id, obj2_type, obj2_id,
                obj1_side=obj1_side, obj1_port=obj1_port,
                obj2_side=obj2_side, obj2_port=obj2_port,
            )
            if self.g is not None and self.g not in self.cgraphs:
                self.cgraphs.append(self.g)

            paths = self.find_paths(
                obj1_type, obj1_id, obj2_type, obj2_id,
                obj1_side=obj1_side, obj1_port=obj1_port,
                obj2_side=obj2_side, obj2_port=obj2_port,
                max_paths=max_paths,
            )
            if not paths:
                raise AttenuationError(
                    f"нет пути между {obj1_type}:{obj1_id}"
                    + (f" и {obj2_type}:{obj2_id}" if obj2_type else "")
                )
            reports = [self._report_from_vpath(p, direction=direction) for p in paths]
            return MultiPathReport(
                branches=reports,
                wavelength_nm=self.wavelength,
                from_label=reports[0].from_label if reports else "",
                to_label=reports[-1].to_label if reports else "",
                query={
                    "mode": "between_objects",
                    "obj1_type": obj1_type,
                    "obj1_id": obj1_id,
                    "obj1_side": obj1_side,
                    "obj1_port": obj1_port,
                    "obj2_type": obj2_type,
                    "obj2_id": obj2_id,
                    "obj2_side": obj2_side,
                    "obj2_port": obj2_port,
                    "direction": direction,
                    "wavelength_nm": self.wavelength,
                    "max_paths": max_paths,
                },
            )
        finally:
            self.wavelength = prev_wl

    def _calculate_all_graphs(
        self, *, direction: Optional[str] = None, max_paths: Optional[int] = None,
    ):
        graphs = list(self.cgraphs) if self.cgraphs else (
            [self.g] if self.g is not None else []
        )
        if not graphs:
            raise AttenuationError(
                "не указаны объекты для расчёта и CGraph не задан: "
                "передайте graph= (CGraph/NetworkTopology) в Attenuation(...) или "
                "obj1_type/obj1_id в calculate(...)"
            )
        if len(graphs) == 1:
            self.g = graphs[0]
            return self._calculate_full_cgraph(direction=direction, max_paths=max_paths)

        branches: List[PathReport] = []
        errors: List[str] = []
        for i, cg in enumerate(graphs):
            self.g = cg
            try:
                res = self._calculate_full_cgraph(direction=direction, max_paths=max_paths)
            except AttenuationError as e:
                errors.append(f"cgraph[{i}]: {e}")
                continue
            if isinstance(res, PathReport):
                branches.append(res)
            elif isinstance(res, MultiPathReport):
                branches.extend(res.branches)

        if not branches:
            detail = "; ".join(errors) if errors else "пусто"
            raise AttenuationError(
                f"не удалось посчитать ни один CGraph из {len(graphs)}: {detail}"
            )
        return MultiPathReport(
            branches=branches,
            wavelength_nm=self.wavelength,
            from_label="",
            to_label="",
            warnings=errors,
            query={
                "mode": "all_graphs",
                "cgraph_count": len(graphs),
                "direction": direction,
                "wavelength_nm": self.wavelength,
                "max_paths": max_paths,
            },
        )

    def _calculate_full_cgraph(
        self, *, direction: Optional[str] = None, max_paths: Optional[int] = None,
    ):
        """Затухания по всем значимым путям текущего CGraph."""
        if self.g is None or getattr(self.g, "vcount", lambda: 0)() == 0:
            raise AttenuationError("CGraph пуст — нечего считать")

        sources = self._vertices_of_types(_SOURCE_TYPES)
        sinks = self._dedupe_device_vertices(self._vertices_of_types(_SINK_TYPES))
        customers = self._vertices_of_types({TYPE_CUSTOMER})

        pair_sources = customers if customers else sources
        pair_sinks = sinks

        if not pair_sources or not pair_sinks:
            leaves = self._leaf_vertices()
            if len(leaves) >= 2:
                if not pair_sources:
                    pair_sources = leaves
                if not pair_sinks:
                    pair_sinks = leaves

        if not pair_sources:
            raise AttenuationError(
                "в CGraph нет терминальных вершин (customer/olt/…) для расчёта"
            )

        if not pair_sinks:
            pair_sinks = [v for v in self._leaf_vertices() if v not in set(pair_sources)]

        # Только кратчайшие пути: в PON-дереве путь customer↔OLT уникален;
        # all_simple_paths даёт экспоненциальную стоимость без выигрыша.
        collected: List[List[int]] = []
        seen = set()
        for s in pair_sources:
            targets = [t for t in pair_sinks if t != s]
            if not targets:
                continue
            for t in targets:
                sp = self.shortest_path(s, t)
                if sp and len(sp) >= 2:
                    key = tuple(sp)
                    if key not in seen:
                        seen.add(key)
                        collected.append(sp)
                if max_paths is not None and len(collected) >= max_paths:
                    break
            if max_paths is not None and len(collected) >= max_paths:
                break

        if not collected:
            linear = self._linear_cover_path()
            if linear and len(linear) >= 2:
                collected = [linear]

        if not collected:
            raise AttenuationError("не удалось найти пути в CGraph для расчёта затуханий")

        collected = self._dedupe_paths_by_endpoints(collected)
        reports = [self._report_from_vpath(p, direction=direction) for p in collected]
        return MultiPathReport(
            branches=reports,
            wavelength_nm=self.wavelength,
            from_label=reports[0].from_label if reports else "",
            to_label=reports[-1].to_label if reports else "",
            query={
                "mode": "full_cgraph",
                "direction": direction,
                "wavelength_nm": self.wavelength,
                "max_paths": max_paths,
                "path_count": len(reports),
            },
        )

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
