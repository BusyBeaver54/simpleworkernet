# simpleworkernet/utils/topology/attenuation/calculator.py
"""Attenuation — calculate() between two objects."""
from __future__ import annotations
from typing import Any, List, Optional, Tuple, Union
from ..keys import Interface
from .catalog import AttenuationCatalog
from .models import PathReport
from .calculator_segments import AttenuationSegmentsMixin, _label_vertex
from .calculator_path import AttenuationPathMixin
from .calculator_build import AttenuationBuildMixin
from .errors import AttenuationError

VertexRef = Union[int, Interface, Tuple[str, Union[int, str], int, int], str]

class Attenuation(AttenuationBuildMixin, AttenuationSegmentsMixin, AttenuationPathMixin):
    def __init__(
        self,
        cgraph: Any = None,
        *,
        catalog: Optional[AttenuationCatalog] = None,
        wavelength: int = 1550,
        cache: Any = None,
        client: Any = None,
        use_max: bool = False,
    ) -> None:
        self.g = cgraph
        self.catalog = catalog or AttenuationCatalog.with_defaults()
        self.wavelength = int(wavelength)
        self.use_max = bool(use_max)
        self.cache = cache if cache is not None else getattr(cgraph, "cache", None)
        self.client = client if client is not None else getattr(cgraph, "client", None)

    def calculate(
        self,
        obj1_type: str,
        obj1_id: Union[int, str],
        obj2_type: str,
        obj2_id: Union[int, str],
        *,
        wavelength: Optional[int] = None,
        obj1_side: Optional[int] = None,
        obj1_port: Optional[int] = None,
        obj2_side: Optional[int] = None,
        obj2_port: Optional[int] = None,
        direction: Optional[str] = None,
        use_max: Optional[bool] = None,
    ) -> PathReport:
        """Затухание между двумя объектами.

        Если CGraph не задан — строится от одного из концов (нужен client).
        Если вершины не найдены или пути нет — AttenuationError.
        """
        prev_wl = self.wavelength
        prev_max = self.use_max
        if wavelength is not None:
            self.wavelength = int(wavelength)
        if use_max is not None:
            self.use_max = bool(use_max)
        try:
            self._ensure_cgraph(
                obj1_type, obj1_id, obj2_type, obj2_id,
                obj1_side=obj1_side, obj1_port=obj1_port,
                obj2_side=obj2_side, obj2_port=obj2_port,
            )
            v1 = self.find_vertex(obj1_type, obj1_id, side=obj1_side, port=obj1_port)
            if v1 is None:
                hits = self.find_vertices(obj1_type, obj1_id)
                v1 = hits[0] if hits else None
            v2 = self.find_vertex(obj2_type, obj2_id, side=obj2_side, port=obj2_port)
            if v2 is None:
                hits = self.find_vertices(obj2_type, obj2_id)
                v2 = hits[0] if hits else None
            if v1 is None:
                raise AttenuationError(f"объект не найден в графе: {obj1_type}:{obj1_id}")
            if v2 is None:
                raise AttenuationError(f"объект не найден в графе: {obj2_type}:{obj2_id}")
            vpath = self.shortest_path(v1, v2)
            if not vpath or len(vpath) < 2:
                if v1 == v2:
                    return PathReport(
                        wavelength_nm=self.wavelength,
                        from_label=_label_vertex(self._vertex_attrs(v1)),
                        to_label=_label_vertex(self._vertex_attrs(v2)),
                        total_db=0.0,
                        vertex_path=[v1],
                    )
                raise AttenuationError(
                    f"нет связи в CGraph между {obj1_type}:{obj1_id} и {obj2_type}:{obj2_id}"
                )
            return self._report_from_vpath(vpath, direction=direction)
        finally:
            self.wavelength = prev_wl
            self.use_max = prev_max

    def _vertex_attrs(self, idx: int) -> dict:
        v = self.g.vs[idx]
        return {k: v[k] for k in v.attributes()}

    def find_vertices(
        self,
        obj_type: Optional[str] = None,
        obj_id: Optional[Union[int, str]] = None,
        *,
        side: Optional[int] = None,
        port: Optional[int] = None,
        node_id: Optional[int] = None,
    ) -> List[int]:
        found: List[int] = []
        for v in self.g.vs:
            if obj_type is not None and v["obj_type"] != obj_type:
                continue
            if obj_id is not None and str(v["obj_id"]) != str(obj_id):
                continue
            if side is not None and int(v["side"]) != int(side):
                continue
            if port is not None and int(v["port"]) != int(port):
                continue
            if node_id is not None and v["node_id"] != node_id:
                continue
            found.append(v.index)
        return found

    def find_vertex(
        self,
        obj_type: Optional[str] = None,
        obj_id: Optional[Union[int, str]] = None,
        **kwargs: Any,
    ) -> Optional[int]:
        hits = self.find_vertices(obj_type, obj_id, **kwargs)
        return hits[0] if hits else None

    def resolve_vertex(self, ref: VertexRef) -> Optional[int]:
        if isinstance(ref, int):
            return ref if 0 <= ref < self.g.vcount() else None
        if isinstance(ref, Interface):
            return self.find_vertex(
                ref.obj.obj_type, ref.obj.id, side=ref.side, port=ref.port
            )
        if isinstance(ref, tuple) and len(ref) >= 2:
            obj_type, obj_id = ref[0], ref[1]
            side = ref[2] if len(ref) > 2 else None
            port = ref[3] if len(ref) > 3 else None
            return self.find_vertex(obj_type, obj_id, side=side, port=port)
        if isinstance(ref, str) and ":" in ref:
            parts = ref.split(":")
            obj_type = parts[0]
            obj_id = parts[1]
            side = int(parts[2]) if len(parts) > 2 else None
            port = int(parts[3]) if len(parts) > 3 else None
            return self.find_vertex(obj_type, obj_id, side=side, port=port)
        return None

    def shortest_path(self, source: int, target: int) -> List[int]:
        try:
            path = self.g.get_shortest_paths(source, to=target, output="vpath")
            if path and path[0]:
                return list(path[0])
        except Exception:
            pass
        return []

    def path(
        self,
        source: VertexRef,
        target: VertexRef,
        *,
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
