# simpleworkernet/utils/topology/attenuation/calculator_build.py
"""CGraph ensure/build for Attenuation."""
from __future__ import annotations
from typing import Any, Optional, Union
from .errors import AttenuationError

class AttenuationBuildMixin:
    def _ensure_cgraph(
        self, obj1_type, obj1_id, obj2_type, obj2_id,
        *, obj1_side=None, obj1_port=None, obj2_side=None, obj2_port=None,
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
        from .calculator_pairs import pair_plan

        plan = pair_plan(obj1_type, obj2_type)

        if plan.strategy == "fn_corridor" or (
            obj1_type == TYPE_FIBER and obj2_type == TYPE_FIBER
        ):
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

        if plan.strategy == "from_b":
            order = [
                ("b", obj2_type, obj2_id, obj2_side, obj2_port),
                ("a", obj1_type, obj1_id, obj1_side, obj1_port),
            ]
        elif plan.strategy == "from_a":
            order = [
                ("a", obj1_type, obj1_id, obj1_side, obj1_port),
                ("b", obj2_type, obj2_id, obj2_side, obj2_port),
            ]
        else:
            order = [
                ("a", obj1_type, obj1_id, obj1_side, obj1_port),
                ("b", obj2_type, obj2_id, obj2_side, obj2_port),
            ]

        built = {}
        for key, ot, oid, side, port in order:
            g = self._build_cgraph_from(ot, oid, side=side, port=port)
            built[key] = g
            if g is not None and has_obj(g, obj1_type, obj1_id) and has_obj(
                g, obj2_type, obj2_id
            ):
                self.g = g
                return

        g1, g2 = built.get("a"), built.get("b")
        candidates = [g for g in (g1, g2) if g is not None]
        if len(candidates) == 2:
            try:
                from ..merge import merge_cgraphs
                merged = merge_cgraphs(candidates, self.client, self.cache)
                if merged is not None and has_obj(merged, obj1_type, obj1_id) and has_obj(
                    merged, obj2_type, obj2_id
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
                f"не удалось построить CGraph для {obj1_type}:{obj1_id} / {obj2_type}:{obj2_id}"
            )
        if not has_obj(self.g, obj1_type, obj1_id):
            raise AttenuationError(
                f"объект не найден в графе после построения: {obj1_type}:{obj1_id}"
            )
        if not has_obj(self.g, obj2_type, obj2_id):
            raise AttenuationError(
                f"объект не найден в графе после построения: {obj2_type}:{obj2_id}"
            )

    def _build_cgraph_from(self, obj_type, obj_id, *, side=None, port=None) -> Any:
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
    ):
        from .calculator_pairs import validate_pair_inputs
        return validate_pair_inputs(
            obj1_type, obj1_id, obj1_side, obj1_port,
            obj2_type, obj2_id, obj2_side, obj2_port,
        )

    def _pick_endpoint_pair(
        self, obj1_type, obj1_id, obj2_type, obj2_id,
        *, obj1_side=None, obj1_port=None, obj2_side=None, obj2_port=None,
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
            raise AttenuationError(f"объект не найден в графе: {obj1_type}:{obj1_id}")
        if not c2:
            raise AttenuationError(f"объект не найден в графе: {obj2_type}:{obj2_id}")
        best = None
        for a in c1:
            for b in c2:
                if a == b:
                    return a, b
                path = self.shortest_path(a, b)
                if not path or len(path) < 2:
                    continue
                score = len(path)
                if best is None or score < best[0]:
                    best = (score, a, b)
        if best is not None:
            return best[1], best[2]
        raise AttenuationError(
            f"нет связи в CGraph между {obj1_type}:{obj1_id} и {obj2_type}:{obj2_id}"
        )
