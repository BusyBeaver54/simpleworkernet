# simpleworkernet/utils/topology/attenuation/calculator.py
"""Attenuation — calculate() between objects or over entire CGraph."""
from __future__ import annotations
from typing import Any, List, Optional, Tuple, Union
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
        self, cgraph: Any = None, *, catalog: Optional[AttenuationCatalog] = None,
        wavelength: int = 1550, cache: Any = None, client: Any = None, use_max: bool = False,
    ) -> None:
        self.g = cgraph
        if catalog is not None:
            self.catalog = catalog
        else:
            loaded = None
            client_ref = client if client is not None else getattr(cgraph, "client", None)
            if client_ref is not None:
                try:
                    from .template import load_attenuation_catalog
                    loaded = load_attenuation_catalog(client_ref)
                except Exception:
                    loaded = None
            self.catalog = loaded or AttenuationCatalog.with_defaults()
        self.wavelength = int(wavelength)
        self.use_max = bool(use_max)
        self.cache = cache if cache is not None else getattr(cgraph, "cache", None)
        self.client = client if client is not None else getattr(cgraph, "client", None)

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
        use_max: Optional[bool] = None,
        max_paths: int = 50,
    ):
        """Расчёт затухания.

        Варианты вызова
        ---------------
        1. ``calculate(obj1_type, obj1_id, obj2_type=..., obj2_id=...)``
           Путь между двумя объектами (obj2 необязателен → авто OLT/switch…).

        2. ``calculate()`` при ``Attenuation(cgraph=...)``
           Затухания по всему переданному CGraph:
           пути customer→olt (и др. терминалы); при одной ветви — PathReport,
           при нескольких — MultiPathReport.

        3. ``calculate()`` без CGraph и без obj1 → ``AttenuationError``.

        Returns
        -------
        PathReport | MultiPathReport
        """
        prev_wl, prev_max = self.wavelength, self.use_max
        if wavelength is not None:
            self.wavelength = int(wavelength)
        if use_max is not None:
            self.use_max = bool(use_max)
        try:
            has_obj1 = obj1_type is not None and obj1_id is not None and obj1_id != ""

            # --- режим «весь CGraph» ---
            if not has_obj1:
                if self.g is None:
                    raise AttenuationError(
                        "не указаны объекты для расчёта и CGraph не задан: "
                        "передайте cgraph= в Attenuation(...) или "
                        "obj1_type/obj1_id в calculate(...)"
                    )
                return self._calculate_full_cgraph(
                    direction=direction, max_paths=max_paths,
                )

            # --- обычный режим: obj1 → obj2 (obj2 optional) ---
            self._require_fiber_port(
                obj1_type, obj1_id, obj1_port, obj2_type, obj2_id, obj2_port,
                obj1_side=obj1_side, obj2_side=obj2_side,
            )

            self._ensure_cgraph(
                obj1_type, obj1_id, obj2_type, obj2_id,
                obj1_side=obj1_side, obj1_port=obj1_port,
                obj2_side=obj2_side, obj2_port=obj2_port,
            )

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

            reports = [
                self._report_from_vpath(p, direction=direction) for p in paths
            ]
            if len(reports) == 1:
                return reports[0]
            return MultiPathReport(
                branches=reports,
                wavelength_nm=self.wavelength,
                from_label=reports[0].from_label if reports else "",
                to_label=reports[0].to_label if reports else "",
            )
        finally:
            self.wavelength, self.use_max = prev_wl, prev_max

    def _calculate_full_cgraph(
        self,
        *,
        direction: Optional[str] = None,
        max_paths: int = 50,
    ):
        """Затухания по всем значимым путям текущего CGraph."""
        if self.g is None or getattr(self.g, "vcount", lambda: 0)() == 0:
            raise AttenuationError("CGraph пуст — нечего считать")

        sources = self._vertices_of_types(_SOURCE_TYPES)
        sinks = self._vertices_of_types(_SINK_TYPES)
        customers = self._vertices_of_types({TYPE_CUSTOMER})

        # предпочтительно customer → olt/switch
        pair_sources = customers if customers else sources
        pair_sinks = sinks

        # если терминалов мало — берём «листья» (степень 1)
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

        # если sinks пусты — пути от sources до остальных leaves
        if not pair_sinks:
            pair_sinks = [
                v for v in self._leaf_vertices()
                if v not in set(pair_sources)
            ]

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
                for p in self.all_simple_paths(
                    s, t, cutoff=200, max_paths=max_paths,
                ):
                    if len(p) < 2:
                        continue
                    key = tuple(p)
                    if key not in seen:
                        seen.add(key)
                        collected.append(p)
                    if len(collected) >= max_paths:
                        break
            if len(collected) >= max_paths:
                break

        # линейный граф: один путь по всем вершинам
        if not collected:
            linear = self._linear_cover_path()
            if linear and len(linear) >= 2:
                collected = [linear]

        if not collected:
            raise AttenuationError(
                "не удалось найти пути в CGraph для расчёта затуханий"
            )

        reports = [
            self._report_from_vpath(p, direction=direction) for p in collected
        ]
        if len(reports) == 1:
            return reports[0]
        return MultiPathReport(
            branches=reports,
            wavelength_nm=self.wavelength,
            from_label=reports[0].from_label if reports else "",
            to_label=reports[-1].to_label if reports else "",
        )

    def _vertices_of_types(self, types) -> List[int]:
        if self.g is None:
            return []
        out: List[int] = []
        for v in self.g.vs:
            if v["obj_type"] in types:
                out.append(int(v.index))
        return out

    def _leaf_vertices(self) -> List[int]:
        """Вершины со степенью 1 (концы линейных участков)."""
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
        """Если граф линеен — путь от одного листа до другого."""
        leaves = self._leaf_vertices()
        if len(leaves) != 2:
            # попробовать is_linear
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
