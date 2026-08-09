# simpleworkernet/utils/topology/builders/handlers_util.py
"""Shared helpers for topology handlers."""
from __future__ import annotations
from ..constants import TERMINAL_TYPES, TYPE_CROSS, TYPE_CUSTOMER, TYPE_FIBER
from ..keys import Interface, ObjKey

def split_finish(comms):
    normal, finish = [], []
    for rec in comms:
        if getattr(rec, "clps_last", None) == "finish":
            finish.append(rec)
        else:
            normal.append(rec)
    return normal, finish

def find_record_for_iface(comms, iface):
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

def neighbor_key(record):
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

def iface_for_neighbor(ctx, neighbor, connect_id):
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

def link_and_maybe_enqueue(ctx, current_iface, neighbor_key_obj, connect_id, parent_node_id):
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
