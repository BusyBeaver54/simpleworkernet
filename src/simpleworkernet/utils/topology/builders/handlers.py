# simpleworkernet/utils/topology/builders/handlers.py
"""Handlers for CGraph BFS build (terminal, fiber, cross, splitter/cwdm)."""
from __future__ import annotations
from typing import Any, List, Optional, Protocol, Tuple, Union

from ..constants import (
    TERMINAL_TYPES,
    TYPE_CROSS,
    TYPE_CWDM,
    TYPE_CUSTOMER,
    TYPE_FIBER,
    TYPE_SPLITTER,
)
from ..keys import Interface, ObjKey


# ---------------------------------------------------------------------------
# util
# ---------------------------------------------------------------------------

def split_finish(comms: List[Any]) -> Tuple[List[Any], List[Any]]:
    normal, finish = [], []
    for rec in comms:
        if getattr(rec, "clps_last", None) == "finish":
            finish.append(rec)
        else:
            normal.append(rec)
    return normal, finish

def find_record_for_iface(comms: List[Any], iface: Interface) -> Optional[Any]:
    is_terminal = iface.obj.obj_type in TERMINAL_TYPES
    for rec in comms:
        if is_terminal:
            if rec.clps_first is not None and int(rec.clps_first) == iface.port:
                return rec
        else:
            if (rec.clps_first is not None and int(rec.clps_first) == iface.side
                    and rec.clps_mid is not None and int(rec.clps_mid) == iface.port):
                return rec
    return None

def neighbor_key(record: Any) -> Optional[ObjKey]:
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

def iface_for_neighbor(ctx: Any, neighbor: ObjKey, connect_id: Any) -> Interface:
    g = ctx.graph
    if neighbor.obj_type == TYPE_CUSTOMER:
        return Interface(neighbor, side=1, port=0)
    if neighbor.obj_type in TERMINAL_TYPES:
        for rec in g.load_commutations(neighbor) or []:
            if int(rec.connect_id) == int(connect_id):
                port = int(rec.clps_first) if rec.clps_first is not None else 0
                return Interface(neighbor, side=1, port=port)
        return Interface(neighbor, side=1, port=0)
    for rec in g.load_commutations(neighbor) or []:
        if int(rec.connect_id) == int(connect_id):
            side = int(rec.clps_first) if rec.clps_first is not None else 1
            port = int(rec.clps_mid) if rec.clps_mid is not None else 0
            return Interface(neighbor, side, port)
    return Interface(neighbor, side=1, port=0)

def link_and_maybe_enqueue(
    ctx: Any,
    current_iface: Interface,
    neighbor_key_obj: ObjKey,
    connect_id: Any,
    parent_node_id: Optional[int],
) -> None:
    g = ctx.graph
    neighbor_iface = iface_for_neighbor(ctx, neighbor_key_obj, connect_id)
    node_for_v2 = parent_node_id if neighbor_key_obj.obj_type == TYPE_CUSTOMER else None
    g.add_iface_edge(current_iface, neighbor_iface, connect_id, node_id_for_vertex2=node_for_v2)
    if neighbor_key_obj.obj_type == TYPE_FIBER:
        fiber_id = int(neighbor_key_obj.id)
        n_idx = g._vertex_index.get(neighbor_iface)
        n_node = g.vs[n_idx]["node_id"] if n_idx is not None else None
        if ctx.should_stop_at_fiber(fiber_id, n_node):
            return
    n_obj = g.load_object(neighbor_key_obj)
    n_node = g.get_node_id_from_obj(n_obj)
    if n_node is not None and ctx.should_stop_at_node(n_node):
        return
    if neighbor_key_obj.obj_type != TYPE_CUSTOMER:
        ctx.enqueue(neighbor_iface, current_iface.obj)


# ---------------------------------------------------------------------------
# splitter / cwdm
# ---------------------------------------------------------------------------

class SplitterCwdmHandler:
    _LINEAR_ARRIVE = {TYPE_SPLITTER: 2, TYPE_CWDM: 1}

    def process(self, obj: Any, comms: List[Any], current_iface: Interface, ctx: Any) -> None:
        g = ctx.graph
        normal, finish = split_finish(comms)
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
        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        linear_ok = True
        if getattr(ctx, "linear", False):
            expect = self._LINEAR_ARRIVE.get(obj.obj_type, 2)
            if int(current_iface.side) != expect:
                linear_ok = False
                ctx.mark_linear_violation(
                    f"{obj.obj_type}:{obj.id} side={current_iface.side}, need {expect}"
                )
        if getattr(ctx, "linear", False) and linear_ok:
            opp_side = 1 if current_iface.side == 2 else 2
            opp_ports = ports_s1 if opp_side == 1 else ports_s2
            for p in opp_ports:
                g.add_iface_edge(
                    current_iface, Interface(obj, opp_side, p), 0, is_internal=True
                )
            for rec in normal:
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if s != opp_side:
                    continue
                nk = neighbor_key(rec)
                if nk is None:
                    continue
                link_and_maybe_enqueue(
                    ctx, Interface(obj, s, p), nk, rec.connect_id, parent_node
                )
            return
        for p1 in ports_s1:
            for p2 in ports_s2:
                g.add_iface_edge(
                    Interface(obj, 1, p1), Interface(obj, 2, p2), 0, is_internal=True
                )
        for rec in normal:
            nk = neighbor_key(rec)
            if nk is None:
                continue
            side = int(rec.clps_first) if rec.clps_first is not None else 1
            port = int(rec.clps_mid) if rec.clps_mid is not None else 0
            link_and_maybe_enqueue(
                ctx, Interface(obj, side, port), nk, rec.connect_id, parent_node
            )


# ---------------------------------------------------------------------------
# object handlers
# ---------------------------------------------------------------------------

class ObjectHandler(Protocol):
    def process(
        self,
        obj: Any,
        comms: List[Any],
        current_iface: Interface,
        ctx: Any,
    ) -> None: ...


class TerminalHandler:
    def process(
        self,
        obj: Any,
        comms: List[Any],
        current_iface: Interface,
        ctx: Any,
    ) -> None:
        normal, finish = split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)
        idx = ctx.graph._vertex_index.get(current_iface)
        node_id = (
            ctx.graph.vs[idx].attributes().get("node_id")
            if idx is not None
            else None
        )
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return
        record = find_record_for_iface(normal, current_iface)
        if record is None:
            return
        nk = neighbor_key(record)
        if nk is None:
            return
        parent_node = ctx.graph.get_node_id_from_obj(ctx.graph.load_object(obj))
        link_and_maybe_enqueue(
            ctx, current_iface, nk, record.connect_id, parent_node
        )


class CrossHandler:
    def process(
        self,
        obj: Any,
        comms: List[Any],
        current_iface: Interface,
        ctx: Any,
    ) -> None:
        g = ctx.graph
        normal, finish = split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)
        idx = g._vertex_index.get(current_iface)
        node_id = (
            g.vs[idx].attributes().get("node_id") if idx is not None else None
        )
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return
        active_port = (
            ctx.start_iface.port
            if ctx.start_obj_key == obj and ctx.start_iface is not None
            else current_iface.port
        )
        g.add_iface_edge(
            Interface(obj, 1, active_port),
            Interface(obj, 2, active_port),
            0,
            is_internal=True,
        )
        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        for rec in normal:
            port = int(rec.clps_mid) if rec.clps_mid is not None else 0
            if port != active_port:
                continue
            nk = neighbor_key(rec)
            if nk is None:
                continue
            side = int(rec.clps_first) if rec.clps_first is not None else 1
            link_and_maybe_enqueue(
                ctx,
                Interface(obj, side, active_port),
                nk,
                rec.connect_id,
                parent_node,
            )


class FiberHandler:
    def process(
        self,
        obj: Any,
        comms: List[Any],
        current_iface: Interface,
        ctx: Any,
    ) -> None:
        g = ctx.graph
        normal, finish = split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)
        idx = g._vertex_index.get(current_iface)
        node_id = (
            g.vs[idx].attributes().get("node_id") if idx is not None else None
        )
        if ctx.should_stop_at_fiber(int(obj.id), node_id):
            return
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return
        record = find_record_for_iface(normal, current_iface)
        if record is None:
            return
        nk = neighbor_key(record)
        if nk is None:
            return
        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        link_and_maybe_enqueue(
            ctx, current_iface, nk, record.connect_id, parent_node
        )
        opposite_side = 2 if current_iface.side == 1 else 1
        opposite_iface = Interface(obj, opposite_side, current_iface.port)
        g.add_iface_edge(current_iface, opposite_iface, 0, is_internal=True)
        opp_rec = find_record_for_iface(normal, opposite_iface)
        if opp_rec is None:
            return
        nk2 = neighbor_key(opp_rec)
        if nk2 is None:
            return
        link_and_maybe_enqueue(
            ctx, opposite_iface, nk2, opp_rec.connect_id, parent_node
        )


def get_handler(obj_type: str) -> ObjectHandler:
    if obj_type in TERMINAL_TYPES:
        return TerminalHandler()
    if obj_type in (TYPE_SPLITTER, TYPE_CWDM):
        return SplitterCwdmHandler()
    mapping = {
        TYPE_CROSS: CrossHandler(),
        TYPE_FIBER: FiberHandler(),
    }
    h = mapping.get(obj_type)
    if h is None:
        raise ValueError(f"Нет handler для типа {obj_type}")
    return h
