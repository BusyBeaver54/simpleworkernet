# simpleworkernet/utils/topology/builders/handlers.py
"""Handlers for CGraph BFS build."""
from __future__ import annotations
from typing import Protocol
from ..constants import TERMINAL_TYPES, TYPE_CROSS, TYPE_CWDM, TYPE_FIBER, TYPE_SPLITTER
from ..keys import Interface
from .handlers_util import (
    split_finish, find_record_for_iface, neighbor_key, link_and_maybe_enqueue,
)

class ObjectHandler(Protocol):
    def process(self, obj, comms, current_iface, ctx) -> None: ...

class TerminalHandler:
    def process(self, obj, comms, current_iface, ctx):
        normal, finish = split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)
        idx = ctx.graph._vertex_index.get(current_iface)
        node_id = ctx.graph.vs[idx].attributes().get("node_id") if idx is not None else None
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return
        record = find_record_for_iface(normal, current_iface)
        if record is None:
            return
        nk = neighbor_key(record)
        if nk is None:
            return
        parent_node = ctx.graph.get_node_id_from_obj(ctx.graph.load_object(obj))
        link_and_maybe_enqueue(ctx, current_iface, nk, record.connect_id, parent_node)

class CrossHandler:
    def process(self, obj, comms, current_iface, ctx):
        g = ctx.graph
        normal, finish = split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)
        idx = g._vertex_index.get(current_iface)
        node_id = g.vs[idx].attributes().get("node_id") if idx is not None else None
        if node_id is not None and ctx.should_stop_at_node(node_id):
            return
        active_port = (
            ctx.start_iface.port
            if ctx.start_obj_key == obj and ctx.start_iface is not None
            else current_iface.port
        )
        g.add_iface_edge(Interface(obj, 1, active_port), Interface(obj, 2, active_port), 0, is_internal=True)
        parent_node = g.get_node_id_from_obj(g.load_object(obj))
        for rec in normal:
            port = int(rec.clps_mid) if rec.clps_mid is not None else 0
            if port != active_port:
                continue
            nk = neighbor_key(rec)
            if nk is None:
                continue
            side = int(rec.clps_first) if rec.clps_first is not None else 1
            link_and_maybe_enqueue(ctx, Interface(obj, side, active_port), nk, rec.connect_id, parent_node)

class FiberHandler:
    def process(self, obj, comms, current_iface, ctx):
        g = ctx.graph
        normal, finish = split_finish(comms)
        if finish:
            ctx.finish_data.setdefault(obj, []).extend(finish)
        idx = g._vertex_index.get(current_iface)
        node_id = g.vs[idx].attributes().get("node_id") if idx is not None else None
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
        link_and_maybe_enqueue(ctx, current_iface, nk, record.connect_id, parent_node)
        opposite_side = 2 if current_iface.side == 1 else 1
        opposite_iface = Interface(obj, opposite_side, current_iface.port)
        g.add_iface_edge(current_iface, opposite_iface, 0, is_internal=True)
        opp_rec = find_record_for_iface(normal, opposite_iface)
        if opp_rec is None:
            return
        nk2 = neighbor_key(opp_rec)
        if nk2 is None:
            return
        link_and_maybe_enqueue(ctx, opposite_iface, nk2, opp_rec.connect_id, parent_node)

def get_handler(obj_type: str):
    from .handlers_splitter import SplitterCwdmHandler
    if obj_type in TERMINAL_TYPES:
        return TerminalHandler()
    if obj_type in (TYPE_SPLITTER, TYPE_CWDM):
        return SplitterCwdmHandler()
    m = {TYPE_CROSS: CrossHandler(), TYPE_FIBER: FiberHandler()}
    h = m.get(obj_type)
    if h is None:
        raise ValueError(f"Нет handler для типа {obj_type}")
    return h
