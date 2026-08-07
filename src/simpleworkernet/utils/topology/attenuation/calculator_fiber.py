# simpleworkernet/utils/topology/attenuation/calculator_fiber.py
"""Fiber load helpers for attenuation FN corridor."""
from __future__ import annotations
from typing import Any, List, Optional, Set

def _log():
    try:
        from ....core.logger import log
        return log
    except Exception:
        return None

class AttenuationFiberMixin:
    def _load_fiber(self, fiber_id: int) -> Any:
        fid = int(fiber_id)
        fiber = None
        if self.cache is not None and self.client is not None:
            try:
                fiber = self.cache.get_fiber(self.client, fid)
            except Exception as e:
                lg = _log()
                if lg: lg.debug(f"cache.get_fiber({fid}) failed: {e}")
        if fiber is None and self.client is not None:
            try:
                result = self.client.Fiber.get_list(object_id=fid)
                items = result if isinstance(result, list) else (
                    getattr(result, "items", None) or getattr(result, "data", None)
                    or (result.to_list() if hasattr(result, "to_list") else []) or []
                )
                if items: fiber = items[0]
            except Exception as e:
                lg = _log()
                if lg: lg.debug(f"Fiber.get_list({fid}) failed: {e}")
        return fiber

    def _fiber_attr(self, fiber: Any, name: str):
        if fiber is None: return None
        v = getattr(fiber, name, None)
        if v is None and isinstance(fiber, dict): v = fiber.get(name)
        return v

    def _fiber_nodes(self, fiber_id: int) -> List[int]:
        fiber = self._load_fiber(fiber_id)
        if fiber is None: return []
        nodes = []
        for attr in ("node1_id", "node2_id"):
            n = self._fiber_attr(fiber, attr)
            if n is not None: nodes.append(int(n))
        return nodes

    def _fiber_side_node(self, fiber_id: int, side: int) -> Optional[int]:
        """side 1 → node1_id, side 2 → node2_id."""
        fiber = self._load_fiber(fiber_id)
        if fiber is None: return None
        side = int(side)
        attr = "node1_id" if side == 1 else "node2_id" if side == 2 else None
        if attr is None: return None
        n = self._fiber_attr(fiber, attr)
        return int(n) if n is not None else None

    def _fiber_code(self, fiber_id: int) -> int:
        fiber = self._load_fiber(fiber_id)
        if fiber is None: return int(fiber_id)
        code = self._fiber_attr(fiber, "code")
        return int(code) if code is not None else int(fiber_id)

    def _fibers_at_node(self, node_id: int) -> Set[int]:
        out: Set[int] = set()
        if self.client is None: return out
        try:
            result = self.client.Fiber.get_list(node_id=int(node_id))
            items = result.to_list() if hasattr(result, "to_list") else (
                result if isinstance(result, list) else
                getattr(result, "items", None) or getattr(result, "data", None) or []
            )
            for f in items or []:
                fid = self._fiber_attr(f, "code") or self._fiber_attr(f, "id")
                if fid is not None: out.add(int(fid))
        except Exception as e:
            lg = _log()
            if lg: lg.debug(f"Fiber.get_list(node_id={node_id}) failed: {e}")
        return out
