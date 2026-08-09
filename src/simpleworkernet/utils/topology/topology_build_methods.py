# simpleworkernet/utils/topology/topology_build_methods.py
"""build_from_* для NetworkTopology."""
from __future__ import annotations
from typing import Optional
from .constants import TYPE_CROSS, TYPE_CUSTOMER, TYPE_CWDM, TYPE_FIBER, TYPE_SPLITTER
from .keys import ObjKey
from .merge import merge_cgraphs
from .graphs import FNGraph

def _normalize_set(value):
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return {int(value)}
    return set(value)

class NetworkTopologyBuildMixin:
    def build_from_device(
        self, object_type: str, object_id: int, port=None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
        linear: bool = False, linear_on_fail: str = "raise",
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM DEVICE: {object_type}:{object_id} (port={port}) ===")
        self._attach(self._build_cgraph(
            object_type, object_id, port=port,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
            linear=linear, linear_on_fail=linear_on_fail,
        ))
        return self

    def build_from_customer(
        self, object_id: int,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM CUSTOMER: {object_id} ===")
        self._attach(self._build_cgraph(
            TYPE_CUSTOMER, object_id, port=None,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        ))
        return self

    def build_from_cross(
        self, object_id: str, port=None, side: Optional[int] = None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM CROSS: {object_id} (port={port}, side={side}) ===")
        inc = _normalize_set(included_fibers)
        exc_f = _normalize_set(excluded_fibers)
        exc_n = _normalize_set(excluded_nodes)
        if port is None:
            ports = set()
            for rec in self._get_commutations(TYPE_CROSS, object_id):
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if p > 0:
                    ports.add(p)
            for p in ports:
                self._attach(self._build_cgraph(
                    TYPE_CROSS, object_id, port=p, side=None,
                    included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                ))
            return self
        self._attach(self._build_cgraph(
            TYPE_CROSS, object_id, port=port, side=side,
            included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
        ))
        return self

    def build_from_splitter(
        self, object_id: int, port=None, side: Optional[int] = None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM SPLITTER: {object_id} (port={port}, side={side}) ===")
        if port is None and side is None:
            interfaces = set()
            for rec in self._get_commutations(TYPE_SPLITTER, object_id):
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                interfaces.add((s, p))
            graphs = []
            for s, p in interfaces:
                g = self._build_cgraph(
                    TYPE_SPLITTER, object_id, port=p, side=s,
                    included_fibers=_normalize_set(included_fibers),
                    excluded_fibers=_normalize_set(excluded_fibers),
                    excluded_nodes=_normalize_set(excluded_nodes),
                )
                if g is not None and g.is_connected():
                    graphs.append(g)
            if graphs:
                merged = merge_cgraphs(graphs, self.client, self.cache)
                if merged is not None:
                    self._attach(merged)
                else:
                    for g in graphs:
                        self._attach(g)
            return self
        self._attach(self._build_cgraph(
            TYPE_SPLITTER, object_id, port=port, side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        ))
        return self

    def build_from_cwdm(
        self, object_id: int, port=None, side: Optional[int] = None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM CWDM: {object_id} (port={port}, side={side}) ===")
        if port is None and side is None:
            interfaces = set()
            for rec in self._get_commutations(TYPE_CWDM, object_id):
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                interfaces.add((s, p))
            graphs = []
            for s, p in interfaces:
                g = self._build_cgraph(
                    TYPE_CWDM, object_id, port=p, side=s,
                    included_fibers=_normalize_set(included_fibers),
                    excluded_fibers=_normalize_set(excluded_fibers),
                    excluded_nodes=_normalize_set(excluded_nodes),
                )
                if g is not None and g.is_connected():
                    graphs.append(g)
            if graphs:
                merged = merge_cgraphs(graphs, self.client, self.cache)
                if merged is not None:
                    self._attach(merged)
                else:
                    for g in graphs:
                        self._attach(g)
            return self
        self._attach(self._build_cgraph(
            TYPE_CWDM, object_id, port=port, side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        ))
        return self

    def build_from_fiber(
        self, object_id: int, port=None, side: Optional[int] = None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM FIBER: cable={object_id}, port={port}, side={side} ===")
        self._attach(self._build_cgraph(
            TYPE_FIBER, object_id, port=port, side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        ))
        return self

    def build_from_node(
        self, object_id: int,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM NODE: {object_id} ===")
        inc = _normalize_set(included_fibers)
        exc_f = _normalize_set(excluded_fibers)
        exc_n = _normalize_set(excluded_nodes)
        fn = FNGraph(self.client, cache=self.cache)
        fn.build(object_id, included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n)
        if fn.vcount() == 0:
            self.logger.warning(f"Не удалось построить FNGraph от узла {object_id}")
            return self
        self._set_fngraph(fn)
        for node_id in [v["node_id"] for v in fn.vs]:
            if exc_n is not None and node_id in exp_n if False else (exc_n is not None and node_id in exc_n):
                continue
            for obj_type, obj_id, port_info in self._get_objects_for_node(node_id):
                if self._find_cgraph_for_object(ObjKey(obj_type, obj_id)) is not None:
                    continue
                try:
                    if obj_type == TYPE_CROSS:
                        ports = set()
                        for rec in self._get_commutations(TYPE_CROSS, obj_id):
                            if getattr(rec, "clps_last", None) == "finish":
                                continue
                            p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                            if p > 0:
                                ports.add(p)
                        for p in ports or [None]:
                            cg = self._build_cgraph(
                                TYPE_CROSS, obj_id, port=p, side=None,
                                included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                            )
                            if cg is not None:
                                self._add_cgraph(cg)
                    elif obj_type == TYPE_FIBER:
                        fiber_ports = set()
                        for rec in self._get_commutations(TYPE_FIBER, obj_id):
                            if getattr(rec, "clps_last", None) == "finish":
                                continue
                            fid = int(rec.clps_mid) if rec.clps_mid is not None else 0
                            if fid > 0:
                                fiber_ports.add(fid)
                        for fp in fiber_ports:
                            cg = self._build_cgraph(
                                TYPE_FIBER, obj_id, port=fp, side=None,
                                included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                            )
                            if cg is not None:
                                self._add_cgraph(cg)
                    else:
                        cg = self._build_cgraph(
                            obj_type, obj_id, port=port_info,
                            included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                        )
                        if cg is not None:
                            self._add_cgraph(cg)
                except Exception as e:
                    self.logger.warning(f"Ошибка построения от {obj_type}:{obj_id}: {e}")
        return self

    def build_from_cable(
        self, object_id: int,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        self._reset()
        self.logger.info(f"=== BUILD FROM CABLE: {object_id} ===")
        inc = _normalize_set(included_fibers)
        exc_f = _normalize_set(excluded_fibers)
        if inc is not None and object_id not in inc:
            self.logger.warning(f"Кабель {object_id} не в included_fibers")
            return self
        if exc_f is not None and object_id in exc_f:
            self.logger.warning(f"Кабель {object_id} в excluded_fibers")
            return self
        fiber_ports = set()
        for rec in self._get_commutations(TYPE_FIBER, object_id):
            if getattr(rec, "clps_last", None) == "finish":
                continue
            fid = int(rec.clps_mid) if rec.clps_mid is not None else 0
            if fid > 0:
                fiber_ports.add(fid)
        for fp in fiber_ports:
            self._attach(self._build_cgraph(
                TYPE_FIBER, object_id, port=fp, side=None,
                included_fibers=inc, excluded_fibers=exc_f,
                excluded_nodes=_normalize_set(excluded_nodes),
            ))
        return self
