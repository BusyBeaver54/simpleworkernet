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


def _as_list(result) -> list:
    if result is None:
        return []
    if isinstance(result, list):
        return result
    if hasattr(result, "to_list"):
        try:
            return list(result.to_list() or [])
        except Exception:
            pass
    for attr in ("items", "data", "results", "objects"):
        v = getattr(result, attr, None)
        if v is not None:
            return list(v) if not isinstance(v, list) else v
    if hasattr(result, "node1_id") or hasattr(result, "code") or (
        isinstance(result, dict) and ("node1_id" in result or "code" in result)
    ):
        return [result]
    return []


class AttenuationFiberMixin:
    def _load_fiber(self, fiber_id: int) -> Any:
        """client.Fiber.get_list(object_id=...) → объект с node1_id/node2_id."""
        fid = int(fiber_id)
        lg = _log()
        fiber = None

        if self.cache is not None and self.client is not None:
            try:
                fiber = self.cache.get_fiber(self.client, fid)
            except Exception as e:
                if lg:
                    lg.debug(f"cache.get_fiber({fid}) failed: {e}")

        if fiber is not None:
            if (
                self._fiber_attr(fiber, "node1_id") is not None
                or self._fiber_attr(fiber, "node2_id") is not None
            ):
                return fiber
            fiber = None

        if self.client is None:
            return None

        try:
            result = self.client.Fiber.get_list(object_id=fid)
            items = _as_list(result)
            if items:
                fiber = items[0]
                if lg:
                    lg.info(
                        f"Fiber.get_list(object_id={fid}) → "
                        f"node1_id={self._fiber_attr(fiber, 'node1_id')} "
                        f"node2_id={self._fiber_attr(fiber, 'node2_id')} "
                        f"code={self._fiber_attr(fiber, 'code')}"
                    )
                return fiber
        except Exception as e:
            if lg:
                lg.warning(f"Fiber.get_list(object_id={fid}) failed: {e}")

        if lg:
            lg.warning(f"не удалось загрузить fiber object_id={fid}")
        return None

    def _fiber_attr(self, fiber: Any, name: str):
        if fiber is None:
            return None
        v = getattr(fiber, name, None)
        if v is None and isinstance(fiber, dict):
            v = fiber.get(name)
        if v is None and hasattr(fiber, "__dict__"):
            v = fiber.__dict__.get(name)
        return v

    def _fiber_nodes(self, fiber_id: int) -> List[int]:
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return []
        nodes = []
        for attr in ("node1_id", "node2_id"):
            n = self._fiber_attr(fiber, attr)
            if n is not None:
                nodes.append(int(n))
        return nodes

    def _fiber_side_node(self, fiber_id: int, side: int) -> Optional[int]:
        """side 1 → node1_id, side 2 → node2_id."""
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return None
        side = int(side)
        if side == 1:
            n = self._fiber_attr(fiber, "node1_id")
        elif side == 2:
            n = self._fiber_attr(fiber, "node2_id")
        else:
            return None
        if n is None:
            lg = _log()
            if lg:
                lg.warning(
                    f"fiber {fiber_id}: нет node для side={side} "
                    f"(node1_id={self._fiber_attr(fiber, 'node1_id')}, "
                    f"node2_id={self._fiber_attr(fiber, 'node2_id')})"
                )
            return None
        return int(n)

    def _fiber_code(self, fiber_id: int) -> int:
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return int(fiber_id)
        code = self._fiber_attr(fiber, "code")
        return int(code) if code is not None else int(fiber_id)

    def _fibers_at_node(self, node_id: int) -> Set[int]:
        out: Set[int] = set()
        if self.client is None:
            return out
        try:
            result = self.client.Fiber.get_list(node_id=int(node_id))
            for f in _as_list(result):
                fid = self._fiber_attr(f, "code") or self._fiber_attr(f, "id")
                if fid is not None:
                    out.add(int(fid))
        except Exception as e:
            lg = _log()
            if lg:
                lg.debug(f"Fiber.get_list(node_id={node_id}) failed: {e}")
        return out
