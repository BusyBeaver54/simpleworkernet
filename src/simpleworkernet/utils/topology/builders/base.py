# simpleworkernet/utils/topology/builders/base.py
"""GraphBuilder — BFS, единый port, linear-режим."""
from __future__ import annotations
from typing import List, Optional, Set, Union
from ..constants import (
    SIDE_TYPES, TERMINAL_TYPES, DEVICE_TYPES,
    TYPE_CROSS, TYPE_CUSTOMER, TYPE_CWDM, TYPE_FIBER,
    TYPE_OLT, TYPE_SPLITTER, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
)
from ..context import BuildContext
from ..keys import Interface, ObjKey
from ..ports_spec import expand_ports, filter_ports
from .handlers import get_handler

def _normalize_set(value):
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return {int(value)}
    return set(int(x) for x in value)

class GraphBuilder:
    def __init__(self, graph) -> None:
        self.graph = graph
        self.logger = graph.logger

    def build(
        self, object_type, object_id, port=None,
        side=None, included_fibers=None, excluded_fibers=None, excluded_nodes=None,
        linear=False, linear_on_fail="raise",
    ):
        g = self.graph
        allowed = expand_ports(port)
        self.logger.info(
            f"=== CGraph {object_type}:{object_id} port={port!r} "
            f"side={side} linear={linear} ==="
        )
        start_obj = g.load_object(ObjKey(object_type, object_id))
        start_node = g.get_node_id_from_obj(start_obj, side=side) if start_obj else None
        ctx = BuildContext(
            client=g.client, cache=g.cache, graph=g,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
            start_node_id=start_node, allowed_ports=allowed,
            linear=bool(linear),
            linear_on_fail=linear_on_fail if linear_on_fail in ("raise", "continue") else "raise",
        )
        start_ifaces = self._resolve_start_interfaces(object_type, object_id, allowed, side)
        if not start_ifaces:
            self.logger.warning("Нет стартовых интерфейсов")
            return g
        ctx.start_obj_key = start_ifaces[0].obj
        ctx.start_iface = start_ifaces[0]
        for iface in sorted(start_ifaces, key=lambda x: (x.obj.obj_type, str(x.obj.id), x.side, x.port)):
            ctx.enqueue(iface)
        while ctx.queue:
            current_iface, _parent = ctx.queue.popleft()
            obj = current_iface.obj
            comms = g.load_commutations(obj) or []
            try:
                handler = get_handler(obj.obj_type)
            except ValueError as e:
                self.logger.warning(str(e))
                continue
            handler.process(obj, comms, current_iface, ctx)
        g._finish_data = ctx.finish_data
        self._mark_terminate_vertices(ctx)
        g.update_directed_flag()
        self.logger.info(f"CGraph: v={g.vcount()} e={g.ecount()} linear_violated={ctx.linear_violated}")
        return g

    def _resolve_start_interfaces(self, object_type, object_id, allowed, side):
        g = self.graph
        obj_key = ObjKey(object_type, object_id)
        comms = g.load_commutations(obj_key) or []
        normal = [r for r in comms if getattr(r, "clps_last", None) != "finish"]

        if object_type in TERMINAL_TYPES or object_type in DEVICE_TYPES:
            ports = set()
            for rec in normal:
                if rec.clps_first is not None:
                    ports.add(int(rec.clps_first))
            if not ports and object_type == TYPE_OLT:
                obj = g.load_object(obj_key)
                ifaces = getattr(obj, "ifaces", None) or {}
                if isinstance(ifaces, dict):
                    for port_num, info in ifaces.items():
                        if isinstance(info, dict) and (
                            info.get("ifType") == 6 or info.get("ifTypeText") == "gpon"
                        ):
                            ports.add(int(port_num))
                elif isinstance(ifaces, list):
                    for iface in ifaces:
                        if getattr(iface, "ifType", None) == 6:
                            num = getattr(iface, "ifNumber", None) or getattr(iface, "number", None)
                            if num is not None:
                                ports.add(int(num))
            use = filter_ports(ports, allowed)
            if not use and allowed:
                use = sorted(allowed)
            return [Interface(obj_key, 1, p) for p in use]

        if object_type == TYPE_CROSS:
            by_side = {1: set(), 2: set()}
            for rec in normal:
                s = int(rec.clps_first) if rec.clps_first is not None else 0
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if s in (1, 2):
                    by_side[s].add(p)
            sides = [side] if side in (1, 2) else [1, 2]
            result = []
            for s in sides:
                use = filter_ports(by_side.get(s, set()), allowed)
                if not use and allowed:
                    use = sorted(allowed)
                for p in use:
                    result.append(Interface(obj_key, s, p))
            return result

        if object_type in (TYPE_SPLITTER, TYPE_CWDM):
            by_side = {1: set(), 2: set()}
            for rec in normal:
                s = int(rec.clps_first) if rec.clps_first is not None else 0
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if s in (1, 2):
                    by_side[s].add(p)
            sides = [side] if side in (1, 2) else [1, 2]
            result = []
            for s in sides:
                use = filter_ports(by_side.get(s, set()), allowed)
                if not use and allowed:
                    use = sorted(allowed)
                for p in use:
                    result.append(Interface(obj_key, s, p))
            return result

        if object_type == TYPE_FIBER:
            sides = [int(side)] if side is not None else [1, 2]
            if allowed is not None:
                use_ports = sorted(allowed)
            else:
                found = set()
                for rec in normal:
                    if rec.clps_mid is not None:
                        found.add(int(rec.clps_mid))
                use_ports = sorted(found) if found else [1]
            return [Interface(obj_key, s, p) for s in sides for p in use_ports]

        if object_type in SIDE_TYPES:
            s = side if side in (1, 2) else 1
            use = sorted(allowed) if allowed else [0]
            return [Interface(obj_key, s, p) for p in use]
        return [Interface(obj_key, 1, 0)]

    def _mark_terminate_vertices(self, ctx) -> None:
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
            obj_type, obj_id = v["obj_type"], v["obj_id"]
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
                    if (rec.clps_first is not None and int(rec.clps_first) == opposite_side
                            and rec.clps_mid is not None and int(rec.clps_mid) == port):
                        opposite_record = rec
                        break
                if opposite_record is None:
                    v["terminate_vertex"] = True
                    v["finish_data"] = ctx.finish_data.get(obj_key, [])
                    continue
                nk = neighbor_key(opposite_record)
                is_term = nk is None or nk.obj_type in TERMINAL_TYPES
                v["terminate_vertex"] = is_term
                v["finish_data"] = ctx.finish_data.get(obj_key, []) if is_term else []
                continue
            if obj_type in (TYPE_SPLITTER, TYPE_CWDM):
                has_non_term = any(
                    (nk := neighbor_key(rec)) is not None and nk.obj_type not in TERMINAL_TYPES
                    for rec in comms
                )
                v["terminate_vertex"] = not has_non_term
                v["finish_data"] = ctx.finish_data.get(obj_key, []) if not has_non_term else []
                continue
            v["terminate_vertex"] = True
            v["finish_data"] = ctx.finish_data.get(obj_key, [])
