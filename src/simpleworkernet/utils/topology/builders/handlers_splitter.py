# simpleworkernet/utils/topology/builders/handlers_splitter.py
"""Splitter/CWDM handler with linear mode."""
from __future__ import annotations
from ..constants import TYPE_CWDM, TYPE_SPLITTER
from ..keys import Interface
from .handlers_util import split_finish, neighbor_key, link_and_maybe_enqueue

class SplitterCwdmHandler:
    _LINEAR_ARRIVE = {TYPE_SPLITTER: 2, TYPE_CWDM: 1}

    def process(self, obj, comms, current_iface, ctx):
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
