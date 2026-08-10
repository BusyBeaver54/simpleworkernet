# simpleworkernet/utils/topology/attenuation/calculator.py
"""Attenuation — calculate() between two objects."""
from __future__ import annotations
from typing import Any, List, Optional, Tuple, Union
from ..keys import Interface
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
            # все значения затуханий — из JSON пользователя (~/.config/.../attenuation_<host>.json)
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
        self, obj1_type: str, obj1_id: Union[int, str], obj2_type: str, obj2_id: Union[int, str],
        *, wavelength: Optional[int] = None, obj1_side: Optional[int] = None, obj1_port: Optional[int] = None,
        obj2_side: Optional[int] = None, obj2_port: Optional[int] = None,
        direction: Optional[str] = None, use_max: Optional[bool] = None,
    ):
        """PathReport (1 путь) или MultiPathReport (несколько ветвей)."""
        prev_wl, prev_max = self.wavelength, self.use_max
        if wavelength is not None:
            self.wavelength = int(wavelength)
        if use_max is not None:
            self.use_max = bool(use_max)
        try:
            plan = self._require_fiber_port(
                obj1_type, obj1_id, obj1_port, obj2_type, obj2_id, obj2_port,
                obj1_side=obj1_side, obj2_side=obj2_side,
            )
            if plan is not None:
                obj1_side, obj1_port, obj2_side, obj2_port = plan

            self._ensure_cgraph(
                obj1_type, obj1_id, obj2_type, obj2_id,
                obj1_side=obj1_side, obj1_port=obj1_port,
                obj2_side=obj2_side, obj2_port=obj2_port,
            )
            paths = self.find_paths(
                obj1_type, obj1_id, obj2_type, obj2_id,
                obj1_side=obj1_side, obj1_port=obj1_port,
                obj2_side=obj2_side, obj2_port=obj2_port,
            )
            if not paths:
                raise AttenuationError(
                    f"нет пути между {obj1_type}:{obj1_id} и {obj2_type}:{obj2_id}"
                )
            reports = [
                self._report_from_vpath(p, direction=direction) for p in paths
            ]
            if len(reports) == 1:
                return reports[0]
            return MultiPathReport(reports=reports, wavelength_nm=self.wavelength)
        finally:
            self.wavelength, self.use_max = prev_wl, prev_max

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
