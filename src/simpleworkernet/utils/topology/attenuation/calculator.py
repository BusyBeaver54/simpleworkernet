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
from . import splitter_load
from .models import PathReport
from .multipath import MultiPathReport
from .calculator_core import (
    AttenuationSegmentsMixin,
    AttenuationPathMixin,
    AttenuationEdgeMixin,
    AttenuationBuildMixin,
    AttenuationFNMixin,
    AttenuationFiberMixin,
    AttenuationPathsMixin,
    AttenuationGraphMixin,
    _label_vertex,
)
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
    AttenuationGraphMixin,
):
    def __init__(
        self,
        graph: Any = None,
        *,
        catalog: Optional[AttenuationCatalog] = None,
        wavelength: int = 1550,
        cache: Any = None,
        client: Any = None,
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
    ) -> Union[PathReport, MultiPathReport, List[Any]]:
        """Расчёт затухания. Всегда MultiPathReport."""
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
    ) -> List[Any]:
        graphs = list(self.cgraphs) if self.cgraphs else (
            [self.g] if self.g is not None else []
        )
        if not graphs:
            raise AttenuationError(
                "не указаны объекты для расчёта и CGraph не задан: "
                "передайте graph= в Attenuation(...) или obj1_type/obj1_id в calculate(...)"
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
    ) -> List[Any]:
        """Затухания по всем значимым путям текущего CGraph."""
        if self.g is None or getattr(self.g, "vcount", lambda: 0)() == 0:
            raise AttenuationError("CGraph пуст — нечего считать")

        try:
            splitter_load.preload_splitters_from_graph(self)
        except Exception:
            pass

        # Конечные точки = где заканчивается коммутация (любой тип объекта).
        # Билдер помечает их terminate_vertex=True; фоллбэк — degree==1 / TERMINAL_TYPES.
        ends = self._terminal_endpoints()
        if len(ends) < 2:
            raise AttenuationError(
                "в CGraph меньше двух конечных вершин (terminate_vertex/degree==1) "
                "для расчёта"
            )

        # Источники: устройства среди конечных точек (OLT в приоритете).
        # Если OLT не помечен как terminate — берём устройства из всего графа.
        device_ends = [
            v for v in ends
            if self.g.vs[v]["obj_type"] in _SINK_TYPES
        ]
        pair_sources = self._dedupe_device_vertices(device_ends)
        if not pair_sources:
            pair_sources = self._dedupe_device_vertices(
                self._vertices_of_types(_SINK_TYPES)
            )

        # Цели — все остальные конечные точки (fiber/splitter/cross/customer/…)
        src_set = set(pair_sources)
        pair_sinks = [v for v in ends if v not in src_set]

        if not pair_sources:
            pair_sources = ends[:1]
            pair_sinks = ends[1:]
        if not pair_sinks:
            pair_sinks = [v for v in ends if v not in set(pair_sources)]

        if not pair_sources or not pair_sinks:
            raise AttenuationError(
                "в CGraph нет пары конечных вершин для расчёта затуханий"
            )

        collected: List[List[int]] = []
        seen = set()
        for s in pair_sources:
            targets = [t for t in pair_sinks if t != s]
            if not targets:
                continue
            paths = self.shortest_paths_batch(s, targets)
            for sp in paths:
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
