# simpleworkernet/utils/topology/attenuation/calculator_build.py
"""CGraph ensure/build for Attenuation."""
from __future__ import annotations
from typing import Any, List, Optional, Union
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
        def has_obj(g, otype, oid) -> bool:
            if g is None:
                return False
            for v in g.vs:
                if v["obj_type"] == otype and str(v["obj_id"]) == str(oid):
                    return True
            return False

        need_build = self.g is None or not (
            has_obj(self.g, obj1_type, obj1_id) and has_obj(self.g, obj2_type, obj2_id)
        )
        if not need_build:
            return
        if self.client is None:
            raise AttenuationError(
                "CGraph не задан и нет client — невозможно построить граф"
            )

        from ..constants import TYPE_FIBER

        if obj1_type == TYPE_FIBER and obj2_type == TYPE_FIBER:
            cg = self._build_cgraph_via_fngraph(
                int(obj1_id), int(obj2_id),
                port1=obj1_port, port2=obj2_port,
                side1=obj1_side, side2=obj2_side,
            )
            if cg is not None and has_obj(cg, obj1_type, obj1_id) and has_obj(
                cg, obj2_type, obj2_id
            ):
                self.g = cg
                return

        g1 = self._build_cgraph_from(
            obj1_type, obj1_id, side=obj1_side, port=obj1_port
        )
        if g1 is not None and has_obj(g1, obj1_type, obj1_id) and has_obj(
            g1, obj2_type, obj2_id
        ):
            self.g = g1
            return

        g2 = self._build_cgraph_from(
            obj2_type, obj2_id, side=obj2_side, port=obj2_port
        )
        if g2 is not None and has_obj(g2, obj1_type, obj1_id) and has_obj(
            g2, obj2_type, obj2_id
        ):
            self.g = g2
            return

        candidates = [g for g in (g1, g2) if g is not None]
        if len(candidates) == 2:
            try:
                from ..merge import merge_cgraphs
                merged = merge_cgraphs(candidates, self.client, self.cache)
                if (
                    merged is not None
                    and has_obj(merged, obj1_type, obj1_id)
                    and has_obj(merged, obj2_type, obj2_id)
                ):
                    self.g = merged
                    return
            except Exception:
                pass

        for g in (g1, g2, self.g):
            if g is not None and (
                has_obj(g, obj1_type, obj1_id) or has_obj(g, obj2_type, obj2_id)
            ):
                self.g = g
                break

        if self.g is None:
            raise AttenuationError(
                f"не удалось построить CGraph для "
                f"{obj1_type}:{obj1_id} / {obj2_type}:{obj2_id}"
            )
        if not has_obj(self.g, obj1_type, obj1_id):
            raise AttenuationError(
                f"объект не найден в графе после построения: {obj1_type}:{obj1_id} "
                f"(есть {obj2_type}:{obj2_id}, но связать не удалось)"
            )
        if not has_obj(self.g, obj2_type, obj2_id):
            raise AttenuationError(
                f"объект не найден в графе после построения: {obj2_type}:{obj2_id} "
                f"(есть {obj1_type}:{obj1_id}, но связать не удалось)"
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

    def _require_fiber_port(
        self, obj1_type, obj1_id, obj1_port, obj2_type, obj2_id, obj2_port,
        obj1_side=None, obj2_side=None,
    ) -> None:
        from ..constants import TYPE_FIBER
        if obj1_type == TYPE_FIBER and obj2_type == TYPE_FIBER:
            if obj1_port is None and obj2_port is None:
                raise AttenuationError(
                    "для расчёта между кабелями укажите номер ОВ (port) "
                    f"хотя бы у одного конца (fiber:{obj1_id} / fiber:{obj2_id})"
                )
            if obj1_side is None or obj2_side is None:
                raise AttenuationError(
                    "для расчёта между кабелями укажите side (сторону) "
                    f"у обоих концов (fiber:{obj1_id} side={obj1_side}, "
                    f"fiber:{obj2_id} side={obj2_side})"
                )

    def _pick_endpoint_pair(
        self,
        obj1_type, obj1_id, obj2_type, obj2_id,
        *,
        obj1_side=None, obj1_port=None,
        obj2_side=None, obj2_port=None,
    ):
        def candidates(otype, oid, side, port):
            hits = self.find_vertices(otype, oid, side=side, port=port)
            if hits:
                return hits
            if port is not None:
                hits = self.find_vertices(otype, oid, side=side)
                if hits:
                    return hits
            return self.find_vertices(otype, oid)

        c1 = candidates(obj1_type, obj1_id, obj1_side, obj1_port)
        c2 = candidates(obj2_type, obj2_id, obj2_side, obj2_port)
        if not c1:
            raise AttenuationError(
                f"объект не найден в графе: {obj1_type}:{obj1_id}"
                + (f" side={obj1_side}" if obj1_side is not None else "")
                + (f" port={obj1_port}" if obj1_port is not None else "")
            )
        if not c2:
            raise AttenuationError(
                f"объект не найден в графе: {obj2_type}:{obj2_id}"
                + (f" side={obj2_side}" if obj2_side is not None else "")
                + (f" port={obj2_port}" if obj2_port is not None else "")
            )

        best = None
        for a in c1:
            for b in c2:
                if a == b:
                    return a, b
                path = self.shortest_path(a, b)
                if not path or len(path) < 2:
                    continue
                score = len(path)
                if obj1_side is not None:
                    try:
                        if int(self.g.vs[a]["side"]) == int(obj1_side):
                            score -= 0.01
                    except Exception:
                        pass
                if obj2_side is not None:
                    try:
                        if int(self.g.vs[b]["side"]) == int(obj2_side):
                            score -= 0.01
                    except Exception:
                        pass
                if best is None or score < best[0]:
                    best = (score, a, b)
        if best is not None:
            return best[1], best[2]
        raise AttenuationError(
            f"нет связи в CGraph между {obj1_type}:{obj1_id} и {obj2_type}:{obj2_id}"
        )
