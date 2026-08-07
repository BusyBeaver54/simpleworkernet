# simpleworkernet/utils/topology/builders/base.py
"""GraphBuilder — оркестрация BFS с handlers."""

from __future__ import annotations

from typing import List, Optional, Set, Union

from ..constants import (
    SIDE_TYPES,
    TERMINAL_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_CWDM,
    TYPE_FIBER,
    TYPE_OLT,
    TYPE_SPLITTER,
    TYPE_SWITCH,
)
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
            start_ifaces,
            key=lambda x: (x.obj.obj_type, str(x.obj.id), x.side, x.port),
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
                        Interface(
                            ObjKey(TYPE_OLT, object_id), side=1, port=int(port_num)
                        )
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
            # Interface: side=clps_first (1|2), port=clps_mid (номер ОВ в кабеле)
            key = ObjKey(TYPE_FIBER, object_id)
            comms = g.load_commutations(key)
            for rec in comms:
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                fiber_num = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if side is not None and int(s) != int(side):
                    continue
                if port is not None and int(fiber_num) != int(port):
                    continue
                result.append(Interface(key, side=s, port=fiber_num))
            if not result and side is not None and port is not None:
                result.append(Interface(key, side=int(side), port=int(port)))
            return result

        key = ObjKey(object_type, object_id)
        s = side if (object_type in SIDE_TYPES and side is not None) else 1
        default_port = 0 if object_type == TYPE_CUSTOMER else 1
        p = port if port is not None else default_port
        result.append(Interface(key, side=s, port=p))
        return result

    def _mark_terminate_vertices(self, ctx: BuildContext) -> None:
        g = ctx.graph

        def neighbor_key(record):
            t = getattr(record, "object_type", None)
            if not t:
                return None
            if t == TYPE_CROSS:
                uuid = getattr(record, "object_uuid", None)
                return ObjKey(t, uuid) if uuid else None
            oid = getattr(record, "object_id", None)
            return ObjKey(t, oid) if oid is not None else None

        for v in g.vs:
            obj_type = v["obj_type"]
            obj_id = v["obj_id"]
            side = v.attributes().get("side", 1)
            port = v.attributes().get("port", 0)
            obj_key = ObjKey(obj_type, obj_id)

            if obj_type in (TYPE_OLT, TYPE_SWITCH) or obj_type in TERMINAL_TYPES:
                v["terminate_vertex"] = True
                v["finish_data"] = ctx.finish_data.get(obj_key, [])
                continue

            comms = g.load_commutations(obj_key)
            if not comms:
                v["terminate_vertex"] = True
                v["finish_data"] = ctx.finish_data.get(obj_key, [])
                continue

            if obj_type in (TYPE_CROSS, TYPE_FIBER):
                opposite_side = 2 if side == 1 else 1
                opposite_record = None
                for rec in comms:
                    if (
                        rec.clps_first is not None
                        and int(rec.clps_first) == opposite_side
                        and rec.clps_mid is not None
                        and int(rec.clps_mid) == port
                    ):
                        opposite_record = rec
                        break
                if opposite_record is None:
                    v["terminate_vertex"] = True
                    v["finish_data"] = ctx.finish_data.get(obj_key, [])
                    continue
                nk = neighbor_key(opposite_record)
                if nk is None:
                    v["terminate_vertex"] = True
                    v["finish_data"] = ctx.finish_data.get(obj_key, [])
                    continue
                is_term = nk.obj_type in TERMINAL_TYPES
                v["terminate_vertex"] = is_term
                v["finish_data"] = (
                    ctx.finish_data.get(obj_key, []) if is_term else []
                )
                continue

            if obj_type in (TYPE_SPLITTER, TYPE_CWDM):
                has_non_term = False
                for rec in comms:
                    nk = neighbor_key(rec)
                    if nk is not None and nk.obj_type not in TERMINAL_TYPES:
                        has_non_term = True
                        break
                v["terminate_vertex"] = not has_non_term
                v["finish_data"] = (
                    ctx.finish_data.get(obj_key, []) if not has_non_term else []
                )
                continue

            v["terminate_vertex"] = True
            v["finish_data"] = ctx.finish_data.get(obj_key, [])
