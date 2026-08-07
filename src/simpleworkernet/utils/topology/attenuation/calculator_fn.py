# simpleworkernet/utils/topology/attenuation/calculator_fn.py
"""FNGraph corridor → CGraph for fiber↔fiber attenuation."""
from __future__ import annotations
from typing import Any, List, Set

class AttenuationFNMixin:
    def _fiber_nodes(self, fiber_id: int) -> List[int]:
        fiber = None
        if self.cache is not None:
            try:
                fiber = self.cache.get_fiber(self.client, int(fiber_id))
            except Exception:
                fiber = None
        if fiber is None:
            return []
        nodes = []
        for attr in ("node1_id", "node2_id"):
            n = getattr(fiber, attr, None)
            if n is not None:
                nodes.append(int(n))
        return nodes

    def _build_cgraph_via_fngraph(
        self,
        fiber1_id: int,
        fiber2_id: int,
        *,
        port1=None,
        port2=None,
        side1=None,
        side2=None,
    ) -> Any:
        """FNGraph между сооружениями кабелей → CGraph по ОВ коридора."""
        from ..graphs.cgraph import CGraph
        from ..graphs.fngraph import FNGraph

        nodes1 = self._fiber_nodes(fiber1_id)
        nodes2 = self._fiber_nodes(fiber2_id)
        if not nodes1 or not nodes2:
            return None

        fn = FNGraph(self.client, cache=self.cache)
        try:
            fn.build(nodes1[0])
        except Exception:
            return None
        if fn.vcount() == 0:
            return None

        node_to_v = {int(v["node_id"]): v.index for v in fn.vs}

        best_path = None
        for n1 in nodes1:
            for n2 in nodes2:
                if n1 not in node_to_v or n2 not in node_to_v:
                    continue
                try:
                    paths = fn.get_shortest_paths(node_to_v[n1], target=node_to_v[n2])
                except Exception:
                    continue
                if paths and paths[0]:
                    if best_path is None or len(paths[0]) < len(best_path):
                        best_path = paths[0]
        if not best_path:
            return None

        corridor: Set[int] = {int(fiber1_id), int(fiber2_id)}
        for a, b in zip(best_path, best_path[1:]):
            try:
                eid = fn.get_eid(a, b, error=False)
            except Exception:
                eid = -1
            if eid is None or eid < 0:
                continue
            fid = fn.es[eid].attributes().get("fiber_id")
            if fid is not None:
                corridor.add(int(fid))

        port = port1 if port1 is not None else port2
        side = side1 if side1 is not None else side2

        cg = CGraph(self.client, cache=self.cache)
        try:
            cg.build(
                "fiber", fiber1_id,
                port=port, side=side,
                included_fibers=corridor,
            )
        except Exception:
            try:
                cg.build(
                    "fiber", fiber2_id,
                    port=port2 if port2 is not None else port,
                    side=side2 if side2 is not None else side,
                    included_fibers=corridor,
                )
            except Exception:
                return None
        if cg.vcount() == 0:
            return None
        return cg
