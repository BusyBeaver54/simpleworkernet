# simpleworkernet/utils/topology/topology.py
"""
Topology — высокоуровневый оркестратор.

Публичный API совместим с прежним utils.topology.Topology.
"""

from __future__ import annotations

from typing import Any, List, Optional, Set, Union

from ...core.client import WorkerNetClient
from .cache import DataCache
from .constants import (
    DEVICE_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_CWDM,
    TYPE_FIBER,
    TYPE_SPLITTER,
)
from .graphs import CGraph, FNGraph
from .keys import ObjKey
from .linear import LinearPathFinder

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        from ...core.logger import log

        _logger = log
    return _logger


def _normalize_set(
    value: Optional[Union[int, List[int], Set[int]]],
) -> Optional[Set[int]]:
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return {int(value)}
    return set(value)


class Topology:
    """
    Высокоуровневый API топологии.

    Хранит список связных CGraph и один FNGraph.
    DataCache — инстанс (можно шарить).
    """

    _data_version = "1.0"

    def __init__(
        self, client: WorkerNetClient, cache: Optional[DataCache] = None
    ) -> None:
        self.client = client
        self.logger = _get_logger()
        self.cache = cache if cache is not None else DataCache()
        self.cgraphs: List[CGraph] = []
        self.fngraph: Optional[FNGraph] = None

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        self.cgraphs = []
        self.fngraph = None

    def _get_commutations(
        self, obj_type: str, obj_id: Union[int, str]
    ) -> List[Any]:
        return self.cache.get_commutations_by_object(
            self.client, obj_type, obj_id, is_finish_data=0
        )

    def _add_cgraph(self, cgraph: Optional[CGraph]) -> None:
        if cgraph is None or cgraph.vcount() == 0:
            return
        if not cgraph.is_connected():
            self.logger.warning("Граф не связный, не добавляем")
            return
        self.cgraphs.append(cgraph)

    def _set_fngraph(self, fngraph: Optional[FNGraph]) -> None:
        if fngraph is None or fngraph.vcount() == 0:
            return
        if not fngraph.is_connected():
            self.logger.warning("FNGraph не связный, не устанавливаем")
            return
        self.fngraph = fngraph

    def _build_fngraph_from_cgraph(
        self, cgraph: CGraph
    ) -> Optional[FNGraph]:
        if cgraph is None or cgraph.vcount() == 0:
            return None
        fn = FNGraph(
            self.client, commutation_graph=cgraph, cache=self.cache
        )
        fn.build(0)
        return fn if fn.vcount() > 0 else None

    def _build_cgraph(
        self,
        obj_type: str,
        obj_id: Union[int, str],
        port: Optional[int] = None,
        side: Optional[int] = None,
        included_fibers: Optional[Set[int]] = None,
        excluded_fibers: Optional[Set[int]] = None,
        excluded_nodes: Optional[Set[int]] = None,
    ) -> Optional[CGraph]:
        cg = CGraph(self.client, cache=self.cache)
        try:
            cg.build(
                obj_type,
                obj_id,
                port=port,
                side=side,
                included_fibers=included_fibers,
                excluded_fibers=excluded_fibers,
                excluded_nodes=excluded_nodes,
            )
            if cg.vcount() == 0 or not cg.is_connected():
                return None
            return cg
        except Exception as e:
            self.logger.error(
                f"Ошибка построения CGraph от {obj_type}:{obj_id}: {e}"
            )
            return None

    def _attach(self, cgraph: Optional[CGraph]) -> None:
        if cgraph is None:
            return
        self._add_cgraph(cgraph)
        fn = self._build_fngraph_from_cgraph(cgraph)
        if fn is not None:
            if self.fngraph is None:
                self._set_fngraph(fn)
            else:
                # простое объединение узлов/рёбер при пересечении
                self._set_fngraph(fn)  # TODO: merge при необходимости

    # ------------------------------------------------------------------
    # build_from_*
    # ------------------------------------------------------------------

    def build_from_device(
        self,
        object_type: str,
        object_id: int,
        port: Optional[int] = None,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(
            f"=== BUILD FROM DEVICE: {object_type}:{object_id} (port={port}) ==="
        )
        cg = self._build_cgraph(
            object_type,
            object_id,
            port=port,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        )
        self._attach(cg)
        return self

    def build_from_customer(
        self,
        object_id: int,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(f"=== BUILD FROM CUSTOMER: {object_id} ===")
        cg = self._build_cgraph(
            TYPE_CUSTOMER,
            object_id,
            port=None,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        )
        self._attach(cg)
        return self

    def build_from_cross(
        self,
        object_id: str,
        port: Optional[int] = None,
        side: Optional[int] = None,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(
            f"=== BUILD FROM CROSS: {object_id} (port={port}, side={side}) ==="
        )
        inc = _normalize_set(included_fibers)
        exc_f = _normalize_set(excluded_fibers)
        exc_n = _normalize_set(excluded_nodes)

        if port is None:
            comms = self._get_commutations(TYPE_CROSS, object_id)
            ports = set()
            for rec in comms:
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                if p > 0:
                    ports.add(p)
            for p in ports:
                cg = self._build_cgraph(
                    TYPE_CROSS, object_id, port=p, side=None,
                    included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                )
                self._attach(cg)
            return self

        cg = self._build_cgraph(
            TYPE_CROSS, object_id, port=port, side=side,
            included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
        )
        self._attach(cg)
        return self

    def build_from_splitter(
        self,
        object_id: int,
        port: Optional[int] = None,
        side: Optional[int] = None,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(
            f"=== BUILD FROM SPLITTER: {object_id} (port={port}, side={side}) ==="
        )
        cg = self._build_cgraph(
            TYPE_SPLITTER,
            object_id,
            port=port,
            side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        )
        self._attach(cg)
        return self

    def build_from_cwdm(
        self,
        object_id: int,
        port: Optional[int] = None,
        side: Optional[int] = None,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(
            f"=== BUILD FROM CWDM: {object_id} (port={port}, side={side}) ==="
        )
        cg = self._build_cgraph(
            TYPE_CWDM,
            object_id,
            port=port,
            side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        )
        self._attach(cg)
        return self

    def build_from_fiber(
        self,
        object_id: int,
        port: int,
        side: Optional[int] = None,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(
            f"=== BUILD FROM FIBER: cable={object_id}, port={port}, side={side} ==="
        )
        cg = self._build_cgraph(
            TYPE_FIBER,
            object_id,
            port=port,
            side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        )
        self._attach(cg)
        return self

    def build_from_node(
        self,
        object_id: int,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(f"=== BUILD FROM NODE: {object_id} ===")
        inc = _normalize_set(included_fibers)
        exc_f = _normalize_set(excluded_fibers)
        exc_n = _normalize_set(excluded_nodes)

        fn = FNGraph(self.client, cache=self.cache)
        fn.build(
            object_id,
            included_fibers=inc,
            excluded_fibers=exc_f,
            excluded_nodes=exc_n,
        )
        if fn.vcount() == 0:
            self.logger.warning(f"Не удалось построить FNGraph от узла {object_id}")
            return self
        self._set_fngraph(fn)
        # TODO: полный обход объектов в узлах (как в старой версии)
        return self

    def build_from_cable(
        self,
        object_id: int,
        included_fibers=None,
        excluded_fibers=None,
        excluded_nodes=None,
    ) -> "Topology":
        self._reset()
        self.logger.info(f"=== BUILD FROM CABLE: {object_id} ===")
        comms = self._get_commutations(TYPE_FIBER, object_id)
        fiber_ports = set()
        for rec in comms:
            if getattr(rec, "clps_last", None) == "finish":
                continue
            fid = int(rec.clps_mid) if rec.clps_mid is not None else 0
            if fid > 0:
                fiber_ports.add(fid)
        for fp in fiber_ports:
            cg = self._build_cgraph(
                TYPE_FIBER,
                object_id,
                port=fp,
                side=None,
                included_fibers=_normalize_set(included_fibers),
                excluded_fibers=_normalize_set(excluded_fibers),
                excluded_nodes=_normalize_set(excluded_nodes),
            )
            self._attach(cg)
        return self

    # ------------------------------------------------------------------
    # linear
    # ------------------------------------------------------------------

    def topology_from_commutation(
        self,
        last_object_type: str,
        last_object_id: Union[int, str],
        port: Optional[int] = None,
        side: Optional[int] = None,
        first_object_type: Optional[str] = None,
        first_object_id: Optional[Union[int, str]] = None,
    ) -> "Topology":
        finder = LinearPathFinder(self)
        linear_cg = finder.trace(
            last_object_type,
            last_object_id,
            port=port,
            side=side,
            first_object_type=first_object_type,
            first_object_id=first_object_id,
        )
        new_topo = Topology(self.client, cache=self.cache)
        new_topo._add_cgraph(linear_cg)
        fn = new_topo._build_fngraph_from_cgraph(linear_cg)
        if fn is not None:
            new_topo._set_fngraph(fn)
        return new_topo

    # ------------------------------------------------------------------
    # getters
    # ------------------------------------------------------------------

    def _collect_ids(self, obj_type: str) -> List:
        ids = set()
        for cg in self.cgraphs:
            for v in cg.vs:
                if v["obj_type"] == obj_type:
                    ids.add(v["obj_id"])
        return list(ids)

    def get_customers(self) -> List[int]:
        return [int(i) for i in self._collect_ids(TYPE_CUSTOMER)]

    def get_nodes(self) -> List[int]:
        if self.fngraph is None:
            return []
        return [int(v["node_id"]) for v in self.fngraph.vs]

    def get_cables(self) -> List[int]:
        if self.fngraph is None:
            return []
        return list(
            {
                int(e.attributes().get("fiber_id", 0))
                for e in self.fngraph.es
                if e.attributes().get("fiber_id") is not None
            }
        )

    def get_fibers(self) -> List[int]:
        return [int(i) for i in self._collect_ids(TYPE_FIBER)]

    def get_devices(self) -> List[int]:
        ids = set()
        for cg in self.cgraphs:
            for v in cg.vs:
                if v["obj_type"] in DEVICE_TYPES:
                    ids.add(int(v["obj_id"]))
        return list(ids)

    def get_splitters(self) -> List[int]:
        return [int(i) for i in self._collect_ids(TYPE_SPLITTER)]

    def get_cwdms(self) -> List[int]:
        return [int(i) for i in self._collect_ids(TYPE_CWDM)]

    def get_crosses(self) -> List[str]:
        return [str(i) for i in self._collect_ids(TYPE_CROSS)]

    def customer(self, customer_id: int):
        return self.cache.get_customer(self.client, customer_id)

    def node(self, node_id: int):
        return self.cache.get_node(self.client, node_id)

    def cable(self, cable_id: int):
        return self.cache.get_fiber(self.client, cable_id)

    def device(self, device_id: int):
        for t in DEVICE_TYPES:
            obj = self.cache.get_device(self.client, t, device_id)
            if obj is not None:
                return obj
        return None

    def splitter(self, splitter_id: int):
        return self.cache.get_splitter(self.client, splitter_id)

    def cwdm(self, cwdm_id: int):
        return self.cache.get_cwdm(self.client, cwdm_id)

    def cross(self, cross_uuid: str):
        return self.cache.get_cross(self.client, cross_uuid)

    def __repr__(self) -> str:
        fn = (
            "None"
            if self.fngraph is None
            else f"{self.fngraph.vcount()} nodes, {self.fngraph.ecount()} fibers"
        )
        return f"Topology(CGraphs: {len(self.cgraphs)}, FNGraph: {fn})"
