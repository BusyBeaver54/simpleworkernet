# simpleworkernet/utils/topology/attenuation/calculator_fn.py
"""FNGraph corridor → CGraph for fiber↔fiber."""
from __future__ import annotations
from typing import Any, Set

from ..constants import TYPE_FIBER


def _log():
    try:
        from ....core.logger import log
        return log
    except Exception:
        return None


class AttenuationFNMixin:
    def _build_cgraph_via_fngraph(
        self, fiber1_id: int, fiber2_id: int, *,
        port1=None, port2=None, side1=None, side2=None,
    ) -> Any:
        from ..graphs.cgraph import CGraph
        from ..graphs.fngraph import FNGraph
        lg = _log()
        fiber1_id, fiber2_id = int(fiber1_id), int(fiber2_id)

        start_node = self._fiber_side_node(fiber1_id, side1) if side1 is not None else None
        end_node = self._fiber_side_node(fiber2_id, side2) if side2 is not None else None
        if start_node is None:
            ns = self._fiber_nodes(fiber1_id)
            start_node = ns[0] if ns else None
        if end_node is None:
            ns = self._fiber_nodes(fiber2_id)
            end_node = ns[-1] if ns else None
        if lg:
            lg.info(
                f"FN-corridor: fiber {fiber1_id} side={side1} → node {start_node}; "
                f"fiber {fiber2_id} side={side2} → node {end_node}"
            )
        if start_node is None or end_node is None:
            if lg:
                lg.warning("FN-corridor: нет node_id для сторон кабелей")
            return None

        fn = FNGraph(self.client, cache=self.cache)
        try:
            fn.build(start_node)
        except Exception as e:
            if lg:
                lg.warning(f"FNGraph.build({start_node}) failed: {e}")
            return None
        if fn.vcount() == 0:
            if lg:
                lg.warning("FN-corridor: FNGraph пустой")
            return None

        node_to_v = {int(v["node_id"]): v.index for v in fn.vs}
        if start_node not in node_to_v or end_node not in node_to_v:
            try:
                fn2 = FNGraph(self.client, cache=self.cache)
                fn2.build(end_node)
                if fn2.vcount() > 0:
                    fn = fn2
                    node_to_v = {int(v["node_id"]): v.index for v in fn.vs}
            except Exception:
                pass
        if start_node not in node_to_v or end_node not in node_to_v:
            if lg:
                lg.warning(f"FN-corridor: узлы {start_node}/{end_node} не в FNGraph")
            return None

        try:
            paths = fn.get_shortest_paths(node_to_v[start_node], node_to_v[end_node])
        except Exception as e:
            if lg:
                lg.warning(f"FN path failed: {e}")
            return None
        if not paths or not paths[0]:
            if lg:
                lg.warning(f"FN-corridor: нет пути {start_node} → {end_node}")
            return None
        best_path = paths[0]
        if lg:
            lg.info(f"FN-corridor: path nodes={[fn.vs[i]['node_id'] for i in best_path]}")

        corridor: Set[int] = {
            fiber1_id, fiber2_id,
            self._fiber_code(fiber1_id), self._fiber_code(fiber2_id),
        }
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

        end_cables = self._fibers_at_node(end_node)
        excluded: Set[int] = {fid for fid in end_cables if fid not in corridor}
        if lg:
            lg.info(
                f"FN-corridor: included={sorted(corridor)}, "
                f"excluded_at_end={sorted(excluded)[:30]}"
            )

        port = port1 if port1 is not None else port2
        attempts = [
            (fiber1_id, port1 if port1 is not None else port, side1),
            (fiber2_id, port2 if port2 is not None else port, side2),
        ]
        for start_fid, p, s in attempts:
            if p is None:
                continue
            for use_exc in (True, False):
                cg = CGraph(self.client, cache=self.cache)
                try:
                    kw = dict(port=p, side=s, included_fibers=corridor)
                    if use_exc and excluded:
                        kw["excluded_fibers"] = excluded
                    cg.build(TYPE_FIBER, start_fid, **kw)
                except Exception as e:
                    if lg:
                        lg.debug(f"CGraph from {start_fid}: {e}")
                    continue
                if cg.vcount() == 0:
                    continue
                ids = {
                    str(v["obj_id"])
                    for v in cg.vs
                    if v["obj_type"] == TYPE_FIBER
                }
                if str(fiber1_id) in ids and str(fiber2_id) in ids:
                    if lg:
                        lg.info(
                            f"FN-corridor: CGraph ok from fiber:{start_fid} "
                            f"v={cg.vcount()}"
                        )
                    return cg
        return None
