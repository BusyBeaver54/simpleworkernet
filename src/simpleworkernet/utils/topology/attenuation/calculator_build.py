# simpleworkernet/utils/topology/attenuation/calculator_build.py
"""CGraph ensure/build for Attenuation."""
from __future__ import annotations
from typing import Any, Optional, Union
from .errors import AttenuationError

class AttenuationBuildMixin:
    def _ensure_cgraph(
        self,
        obj1_type: str,
        obj1_id: Union[int, str],
        obj2_type: str,
        obj2_id: Union[int, str],
        *,
        obj1_side=None,
        obj1_port=None,
        obj2_side=None,
        obj2_port=None,
    ) -> None:
        need_build = self.g is None
        if not need_build:
            h1 = self.find_vertices(obj1_type, obj1_id)
            h2 = self.find_vertices(obj2_type, obj2_id)
            if not h1 or not h2:
                need_build = True
        if not need_build:
            return
        if self.client is None:
            raise AttenuationError(
                "CGraph не задан и нет client — невозможно построить граф"
            )
        built = self._build_cgraph_from(
            obj1_type, obj1_id, side=obj1_side, port=obj1_port
        )
        if built is not None:
            self.g = built
            if self.find_vertices(obj2_type, obj2_id):
                return
        built2 = self._build_cgraph_from(
            obj2_type, obj2_id, side=obj2_side, port=obj2_port
        )
        if built2 is not None:
            self.g = built2
            if self.find_vertices(obj1_type, obj1_id) and self.find_vertices(
                obj2_type, obj2_id
            ):
                return
        if self.g is None:
            raise AttenuationError(
                f"не удалось построить CGraph для "
                f"{obj1_type}:{obj1_id} / {obj2_type}:{obj2_id}"
            )

    def _build_cgraph_from(
        self,
        obj_type: str,
        obj_id: Union[int, str],
        *,
        side: Optional[int] = None,
        port: Optional[int] = None,
    ) -> Any:
        from ..graphs.cgraph import CGraph
        cg = CGraph(self.client, cache=self.cache)
        try:
            cg.build(obj_type, obj_id, port=port, side=side)
        except TypeError:
            try:
                cg.build(obj_type, obj_id, port=port)
            except Exception:
                return None
        except Exception:
            return None
        if cg.vcount() == 0:
            return None
        return cg
