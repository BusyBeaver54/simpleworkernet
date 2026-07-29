# simpleworkernet/utils/topology/builders/base.py
"""GraphBuilder — оркестрация BFS с handlers."""

from __future__ import annotations

from typing import List, Optional, Set, Union

from ..constants import SIDE_TYPES, TYPE_CUSTOMER, TYPE_FIBER, TYPE_OLT
from ..context import BuildContext
from ..keys import Interface, ObjKey
from .handlers import get_handler


def _normalize_set(
    value: Optional[Union[int, List[int], Set[int]]],
) -> Optional[Set[int]]:
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return {int(value)}
    return set(value)


class GraphBuilder:
    """Строит CGraph от стартовых интерфейсов через handlers."""

    def __init__(self, graph) -> None:
        self.graph = graph
        self.logger = graph.logger

    def build(
        self,
        object_type: str,
        object_id: Union[int, str],
        port: Optional[int] = None,
        side: Optional[int] = None,
        included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
        excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
        excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None,
    ):
        g = self.graph
        self.logger.info(
            f"=== ПОСТРОЕНИЕ CGraph ОТ {object_type}:{object_id} "
            f"(port={port}, side={side}) ==="
        )

        start_obj = g.load_object(ObjKey(object_type, object_id))
        start_node = g.get_node_id_from_obj(start_obj) if start_obj else None

        ctx = BuildContext(
            client=g.client,
            cache=g.cache,
            graph=g,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
            start_node_id=start_node,
        )

        start_ifaces = self._resolve_start_interfaces(
            object_type, object_id, port, side
        )
        if not start_ifaces:
            self.logger.warning("Нет стартовых интерфейсов")
            return g

        ctx.start_obj_key = start_ifaces[0].obj
        ctx.start_iface = start_ifaces[0]

        for iface in sorted(
            start_ifaces, key=lambda x: (x.obj.obj_type, str(x.obj.id), x.side, x.port)
        ):
            ctx.enqueue(iface)

        while ctx.queue:
            current_iface, _parent = ctx.queue.popleft()
            obj = current_iface.obj
            comms = g.load_commutations(obj)
            if not comms:
                continue
            try:
                handler = get_handler(obj.obj_type)
            except ValueError as e:
                self.logger.warning(str(e))
                continue
            handler.process(obj, comms, current_iface, ctx)

        g._finish_data = ctx.finish_data
        self._mark_terminate_vertices(ctx)
        g.update_directed_flag()
        self.logger.info("=== ПОСТРОЕНИЕ ЗАВЕРШЕНО ===")
        return g

    def _resolve_start_interfaces(
        self,
        object_type: str,
        object_id: Union[int, str],
        port: Optional[int],
        side: Optional[int],
    ) -> List[Interface]:
        g = self.graph
        result: List[Interface] = []

        if object_type == TYPE_OLT and port is None:
            olt = g.load_object(ObjKey(TYPE_OLT, object_id))
            if olt is None:
                return []
            ifaces = getattr(olt, "ifaces", {}) or {}
            for port_num, info in ifaces.items():
                if info.get("ifType") == 6 or info.get("ifTypeText") == "gpon":
                    result.append(
                        Interface(ObjKey(TYPE_OLT, object_id), side=1, port=int(port_num))
                    )
            return result

        if object_type == TYPE_CUSTOMER and port is None:
            key = ObjKey(TYPE_CUSTOMER, object_id)
            for rec in g.load_commutations(key):
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                p = int(rec.clps_first) if rec.clps_first is not None else 0
                result.append(Interface(key, side=1, port=p))
            return result

        if object_type == TYPE_FIBER:
            key = ObjKey(TYPE_FIBER, object_id)
            comms = g.load_commutations(key)
            if port is not None:
                for rec in comms:
                    if getattr(rec, "clps_last", None) == "finish":
                        continue
                    iface_num = (
                        getattr(rec, "interface", None)
                        or getattr(rec, "iface", None)
                        or getattr(rec, "number", None)
                    )
                    if iface_num is not None and int(iface_num) == port:
                        s = side if side is not None else (
                            int(rec.clps_first) if rec.clps_first is not None else 1
                        )
                        fiber_id = int(rec.clps_mid) if rec.clps_mid is not None else 0
                        result.append(Interface(key, side=s, port=fiber_id))
                        break
            else:
                for rec in comms:
                    if getattr(rec, "clps_last", None) == "finish":
                        continue
                    s = int(rec.clps_first) if rec.clps_first is not None else 1
                    fiber_id = int(rec.clps_mid) if rec.clps_mid is not None else 0
                    result.append(Interface(key, side=s, port=fiber_id))
            return result

        key = ObjKey(object_type, object_id)
        s = side if (object_type in SIDE_TYPES and side is not None) else 1
        default_port = 0 if object_type == TYPE_CUSTOMER else 1
        p = port if port is not None else default_port
        result.append(Interface(key, side=s, port=p))
        return result

    def _mark_terminate_vertices(self, ctx: BuildContext) -> None:
        """Упрощённая разметка конечных вершин."""
        from ..constants import DEVICE_TYPES, TERMINAL_TYPES, TYPE_CROSS, TYPE_FIBER

        g = ctx.graph
        for v in g.vs:
            obj_type = v["obj_type"]
            obj_id = v["obj_id"]
            if obj_type in (TYPE_OLT, "switch") or obj_type in TERMINAL_TYPES:
                v["terminate_vertex"] = True
                v["finish_data"] = ctx.finish_data.get(ObjKey(obj_type, obj_id), [])
                continue
            # по умолчанию — конечная, если нет продолжения в графе
            v["terminate_vertex"] = g.g.degree(v.index) <= 1
            if v["terminate_vertex"]:
                v["finish_data"] = ctx.finish_data.get(ObjKey(obj_type, obj_id), [])
