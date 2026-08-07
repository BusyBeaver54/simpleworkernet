# simpleworkernet/utils/topology/attenuation/calculator_fn.py
"""FNGraph corridor → CGraph for fiber↔fiber attenuation."""
from __future__ import annotations
from typing import Any, List, Optional, Set

def _log():
    try:
        from ....core.logger import log
        return log
    except Exception:
        return None

class AttenuationFNMixin:
    def _load_fiber(self, fiber_id: int) -> Any:
        fid = int(fiber_id)
        fiber = None
        if self.cache is not None and self.client is not None:
            try:
                fiber = self.cache.get_fiber(self.client, fid)
            except Exception as e:
                lg = _log()
                if lg:
                    lg.debug(f"cache.get_fiber({fid}) failed: {e}")
        if fiber is None and self.client is not None:
            try:
                result = self.client.Fiber.get_list(object_id=fid)
                items = result if isinstance(result, list) else (
                    getattr(result, "items", None)
                    or getattr(result, "data", None)
                    or []
                )
                if items:
                    fiber = items[0]
            except Exception as e:
                lg = _log()
                if lg:
                    lg.debug(f"Fiber.get_list({fid}) failed: {e}")
        return fiber

    def _fiber_nodes(self, fiber_id: int) -> List[int]:
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return []
        nodes = []
        for attr in ("node1_id", "node2_id"):
            n = getattr(fiber, attr, None)
            if n is None and isinstance(fiber, dict):
                n = fiber.get(attr)
            if n is not None:
                nodes.append(int(n))
        return nodes

    def _fiber_code(self, fiber_id: int) -> Optional[int]:
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return int(fiber_id)
        code = getattr(fiber, "code", None)
        if code is None and isinstance(fiber, dict):
            code = fiber.get("code")
        return int(code) if code is not None else int(fiber_id)

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
        from ..graphs.cgraph import CGraph
        from ..graphs.fngraph import FNGraph

        lg = _log()
        nodes1 = self._fiber_nodes(fiber1_id)
        nodes2 = self._fiber_nodes(fiber2_id)
        if lg:
            lg.info(
                f"FN-corridor: fiber {fiber1_id} nodes={nodes1}, "
                f"fiber {fiber2_id} nodes={nodes2}"
            )
        if not nodes1 or not nodes2:
            if lg:
                lg.warning("FN-corridor: не удалось получить node_id кабелей")
            return None

        fn = FNGraph(self.client, cache=self.cache)
        built = False
        for start in nodes1 + nodes2:
            try:
                fn = FNGraph(self.client, cache=self.cache)
                fn.build(start)
                if fn.vcount() > 0:
                    built = True
                    break
            except Exception as e:
                if lg:
                    lg.debug(f"FNGraph.build({start}) failed: {e}")
        if not built or fn.vcount() == 0:
            if lg:
                lg.warning("FN-corridor: FNGraph пустой")
            return None

        node_to_v = {int(v["node_id"]): v.index for v in fn.vs}
        if lg:
            lg.info(f"FN-corridor: FNGraph {fn.vcount()} nodes, {fn.ecount()} edges")

        best_path = None
        for n1 in nodes1:
            for n2 in nodes2:
                if n1 not in node_to_v or n2 not in node_to_v:
                    continue
                try:
                    paths = fn.get_shortest_paths(node_to_v[n1], node_to_v[n2])
                except Exception as e:
                    if lg:
                        lg.debug(f"FN path {n1}->{n2}: {e}")
                    continue
                if paths and paths[0]:
                    if best_path is None or len(paths[0]) < len(best_path):
                        best_path = paths[0]
        if not best_path:
            if lg:
                lg.warning(
                    f"FN-corridor: нет пути FN между nodes {nodes1} и {nodes2}"
                )
            return None
        if lg:
            path_nodes = [fn.vs[i]["node_id"] for i in best_path]
            lg.info(f"FN-corridor: path nodes={path_nodes}")

        corridor: Set[int] = {
            int(fiber1_id), int(fiber2_id),
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
        if lg:
            lg.info(f"FN-corridor: included_fibers={sorted(corridor)}")

        port = port1 if port1 is not None else port2

        for start_fid, p, s in (
            (fiber1_id, port1 if port1 is not None else port, side1),
            (fiber2_id, port2 if port2 is not None else port, side2),
            (fiber1_id, port, None),
            (fiber2_id, port, None),
        ):
            if p is None:
                continue
            cg = CGraph(self.client, cache=self.cache)
            try:
                cg.build(
                    "fiber", start_fid,
                    port=p, side=s,
                    included_fibers=corridor,
                )
            except Exception as e:
                if lg:
                    lg.debug(f"CGraph via FN from {start_fid}: {e}")
                continue
            if cg.vcount() == 0:
                continue
            ids = {str(v["obj_id"]) for v in cg.vs if v["obj_type"] == "fiber"}
            if str(fiber1_id) in ids and str(fiber2_id) in ids:
                if lg:
                    lg.info(
                        f"FN-corridor: CGraph ok from fiber:{start_fid} "
                        f"v={cg.vcount()} e={cg.ecount()}"
                    )
                return cg
            if lg:
                lg.debug(
                    f"FN-corridor: CGraph from {start_fid} missing endpoint, "
                    f"fibers={ids}"
                )

        for start_fid, p, s in (
            (fiber1_id, port1 if port1 is not None else port, side1),
            (fiber2_id, port2 if port2 is not None else port, side2),
        ):
            if p is None:
                continue
            cg = CGraph(self.client, cache=self.cache)
            try:
                cg.build("fiber", start_fid, port=p, side=s)
            except Exception as e:
                if lg:
                    lg.debug(f"CGraph open from {start_fid}: {e}")
                continue
            if cg.vcount() == 0:
                continue
            ids = {str(v["obj_id"]) for v in cg.vs if v["obj_type"] == "fiber"}
            if str(fiber1_id) in ids and str(fiber2_id) in ids:
                if lg:
                    lg.info(f"CGraph open ok from fiber:{start_fid}")
                return cg
        return None
