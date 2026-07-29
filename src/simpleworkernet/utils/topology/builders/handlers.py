# simpleworkernet/utils/topology/builders/handlers.py
"""
Strategy-handlers для типов объектов при BFS-построении CGraph.

Каждый handler инкапсулирует правила сторон, internal-рёбер и обхода.
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, TYPE_CHECKING

from ..constants import (
    TERMINAL_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_CWDM,
    TYPE_FIBER,
    TYPE_SPLITTER,
)
from ..keys import Interface, ObjKey

if TYPE_CHECKING:
    from ..context import BuildContext


class ObjectHandler(Protocol):
    def process(
        self,
        obj: ObjKey,
        comms: List[Any],
        current_iface: Interface,
        ctx: "BuildContext",
    ) -> None: ...


def _split_finish(comms: List[Any]):
    normal, finish = [], []
    for rec in comms:
        if getattr(rec, "clps_last", None) == "finish":
            finish.append(rec)
        else:
            normal.append(rec)
    return normal, finish


def _find_record_for_iface(comms: List[Any], iface: Interface) -> Optional[Any]:
    is_terminal = iface.obj.obj_type in TERMINAL_TYPES
    for rec in comms:
        if is_terminal:
            if rec.clps_first is not None and int(rec.clps_first) == iface.port:
                return rec
        else:
            if (
                rec.clps_first is not None
                and int(rec.clps_first) == iface.side
                and rec.clps_mid is not None
                and int(rec.clps_mid) == iface.port
            ):
                return rec
    return None


def _neighbor_key(record: Any) -> Optional[ObjKey]:
    t = record.object_type
    if not t:
        return None
    if t == TYPE_CROSS:
        if record.object_uuid is None:
            return None
        return ObjKey(t, record.object_uuid)
    if record.object_id is None:
        return None
    return ObjKey(t, record.object_id)


def _iface_for_neighbor(
    ctx: "BuildContext",
    neighbor: ObjKey,
    connect_id: int,
) -> Interface:
    g = ctx.graph
    if neighbor.obj_type == TYPE_CUSTOMER:
        return Interface(neighbor, side=1, port=0)

    if neighbor.obj_type in TERMINAL_TYPES:
        comms = g.load_commutations(neighbor)
        for rec in comms or []:
            if int(rec.connect_id) == int(connect_id):
                port = int(rec.clps_first) if rec.clps_first is not None else 0
                return Interface(neighbor, side=1, port=port)
        return Interface(neighbor, side=1, port=0)

    comms = g.load_commutations(neighbor)
    for rec in (comms or []):
        if int(rec.connect_id) == int(connect_id):
            side = int(rec.clps_first) if rec.clps_first is not None else 1
            port = int(rec.clps_mid) if rec.clps_mid is not None else 0
            return Interface(neighbor, side, port)
    return Interface(neighbor, side=1, port=0)


def _link_and_maybe_enqueue(
    ctx: "BuildContext",
    current_iface: Interface,
    neighbor_key: ObjKey,
    connect_id: int,
    parent_node_id: Optional[int],
) -> None:
    g = ctx.graph
    neighbor_iface = _iface_for_neighbor(ctx, neighbor_key, connect_id)
    node_for_v2 = parent_node_id if neighbor_key.obj_type == TYPE_CUSTOMER else None
    g.add_iface_edge(
        current_iface, neighbor_iface, connect_id, node_id_for_vertex2=node_for_v2
    )

    if neighbor_key.obj_type == TYPE_FIBER:
        fiber_id = int(neighbor_key.id)
        n_idx = g._vertex_index.get(neighbor_iface)
        n_node = g.vs[n_idx]["node_id"] if n_idx is not None else None
        if ctx.should_stop_at_fiber(fiber_id, n_node):
            return

    n_obj = g.load_object(neighbor_key)
    n_node = g.get_node_id_from_obj(n_obj)
    if n_node is not None and ctx.should_stop_at_node(n_node):
        return

    if neighbor_key.obj_type != TYPE_CUSTOMER:
        ctx.enqueue(neighbor_iface, current_iface.obj)


class TerminalHandler:
    """OLT / switch / ONU / customer."""

    def process(
        self,
        obj: ObjKey,
        comms: List[Any],
        current_iface: Interface,
        ctx: "BuildContext",
    ) -> None:
        g = ctx.graph
        normal, finish = _split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)

        node_id = None
        idx = g._vertex_index.get(current_iface)
        if idx is not None:
            node_id = g.vs[idx].attributes().get("node_id")
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return

        record = _find_record_for_iface(normal, current_iface)
        if record is None:
            return
        nk = _neighbor_key(record)
        if nk is None:
            return
        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        _link_and_maybe_enqueue(
            ctx, current_iface, nk, record.connect_id, parent_node
        )


class CrossHandler:
    """Кросс — только активный порт + internal side1↔side2."""

    def process(
        self,
        obj: ObjKey,
        comms: List[Any],
        current_iface: Interface,
        ctx: "BuildContext",
    ) -> None:
        g = ctx.graph
        normal, finish = _split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)

        idx = g._vertex_index.get(current_iface)
        node_id = g.vs[idx].attributes().get("node_id") if idx is not None else None
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return

        if ctx.start_obj_key == obj and ctx.start_iface is not None:
            active_port = ctx.start_iface.port
        else:
            active_port = current_iface.port

        iface1 = Interface(obj, 1, active_port)
        iface2 = Interface(obj, 2, active_port)
        g.add_iface_edge(iface1, iface2, 0, is_internal=True)

        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        for rec in normal:
            port = int(rec.clps_mid) if rec.clps_mid is not None else 0
            if port != active_port:
                continue
            nk = _neighbor_key(rec)
            if nk is None:
                continue
            side = int(rec.clps_first) if rec.clps_first is not None else 1
            obj_iface = Interface(obj, side, active_port)
            _link_and_maybe_enqueue(ctx, obj_iface, nk, rec.connect_id, parent_node)


class FiberHandler:
    """Кабель — транзит через противоположную сторону."""

    def process(
        self,
        obj: ObjKey,
        comms: List[Any],
        current_iface: Interface,
        ctx: "BuildContext",
    ) -> None:
        g = ctx.graph
        normal, finish = _split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)

        idx = g._vertex_index.get(current_iface)
        node_id = g.vs[idx].attributes().get("node_id") if idx is not None else None
        if ctx.should_stop_at_fiber(int(obj.id), node_id):
            return
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return

        record = _find_record_for_iface(normal, current_iface)
        if record is None:
            return
        nk = _neighbor_key(record)
        if nk is None:
            return
        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        _link_and_maybe_enqueue(
            ctx, current_iface, nk, record.connect_id, parent_node
        )

        opposite_side = 2 if current_iface.side == 1 else 1
        opposite_iface = Interface(obj, opposite_side, current_iface.port)
        g.add_iface_edge(current_iface, opposite_iface, 0, is_internal=True)

        opp_rec = _find_record_for_iface(normal, opposite_iface)
        if opp_rec is None:
            return
        nk2 = _neighbor_key(opp_rec)
        if nk2 is None:
            return
        _link_and_maybe_enqueue(
            ctx, opposite_iface, nk2, opp_rec.connect_id, parent_node
        )


class SplitterCwdmHandler:
    """Сплиттер / CWDM — полносвязные internal + все внешние."""

    def process(
        self,
        obj: ObjKey,
        comms: List[Any],
        current_iface: Interface,
        ctx: "BuildContext",
    ) -> None:
        g = ctx.graph
        normal, finish = _split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)

        idx = g._vertex_index.get(current_iface)
        node_id = g.vs[idx].attributes().get("node_id") if idx is not None else None
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return

        ports_s1, ports_s2 = set(), set()
        for rec in normal:
            s = int(rec.clps_first) if rec.clps_first is not None else 0
            p = int(rec.clps_mid) if rec.clps_mid is not None else 0
            if s == 1:
                ports_s1.add(p)
            elif s == 2:
                ports_s2.add(p)

        for p1 in ports_s1:
            for p2 in ports_s2:
                g.add_iface_edge(
                    Interface(obj, 1, p1), Interface(obj, 2, p2), 0, is_internal=True
                )

        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        for rec in normal:
            nk = _neighbor_key(rec)
            if nk is None:
                continue
            side = int(rec.clps_first) if rec.clps_first is not None else 1
            port = int(rec.clps_mid) if rec.clps_mid is not None else 0
            obj_iface = Interface(obj, side, port)
            _link_and_maybe_enqueue(ctx, obj_iface, nk, rec.connect_id, parent_node)


_HANDLERS = {
    TYPE_CROSS: CrossHandler(),
    TYPE_FIBER: FiberHandler(),
    TYPE_SPLITTER: SplitterCwdmHandler(),
    TYPE_CWDM: SplitterCwdmHandler(),
}

_TERMINAL = TerminalHandler()


def get_handler(obj_type: str) -> ObjectHandler:
    if obj_type in TERMINAL_TYPES:
        return _TERMINAL
    handler = _HANDLERS.get(obj_type)
    if handler is None:
        raise ValueError(f"Нет handler для типа {obj_type}")
    return handler
