# simpleworkernet/utils/topology/topology.py
"""
Topology — высокоуровневый оркестратор.

Публичный API совместим с прежним utils.topology.Topology.
"""

from __future__ import annotations

from typing import Any, List, Optional, Set, Tuple, Union

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
from .merge import merge_cgraphs, merge_fngraphs

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
        if fn is None:
            return
        if self.fngraph is None:
            self._set_fngraph(fn)
        else:
            merged = merge_fngraphs(
                [self.fngraph, fn], self.client, self.cache
            )
            if merged is not None:
                self._set_fngraph(merged)
            else:
                # если merge несвязный — оставляем более новый
                self._set_fngraph(fn)

    def _find_cgraph_for_object(self, obj_key: ObjKey) -> Optional[CGraph]:
        for cg in self.cgraphs:
            for v in cg.vs:
                if v["obj_type"] == obj_key.obj_type and str(v["obj_id"]) == str(
                    obj_key.id
                ):
                    return cg
        return None

    def _get_objects_for_node(
        self, node_id: int
    ) -> List[Tuple[str, Union[int, str], Optional[Any]]]:
        """Список объектов в узле: (obj_type, obj_id, port_info)."""
        objects: List[Tuple[str, Union[int, str], Optional[Any]]] = []

        try:
            for dev_id, dev in self.cache.get_all_devices(self.client).items():
                if getattr(dev, "node_id", None) == node_id:
                    obj_type = getattr(dev, "object_type", None)
                    if obj_type and dev_id:
                        objects.append((obj_type, dev_id, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска устройств в узле {node_id}: {e}")

        try:
            for sid, sp in self.cache.get_all_splitters(self.client).items():
                if getattr(sp, "node_id", None) == node_id:
                    objects.append((TYPE_SPLITTER, sid, None))
        except Exception as e:
            self.logger.warning(
                f"Ошибка поиска сплиттеров в узле {node_id}: {e}"
            )

        try:
            for cid, cw in self.cache.get_all_cwdms(self.client).items():
                if getattr(cw, "node_id", None) == node_id:
                    objects.append((TYPE_CWDM, cid, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска CWDM в узле {node_id}: {e}")

        try:
            for uuid, cr in self.cache.get_all_crosses(self.client).items():
                if getattr(cr, "node_id", None) == node_id:
                    objects.append((TYPE_CROSS, uuid, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска кроссов в узле {node_id}: {e}")

        try:
            for fid, fib in self.cache.get_all_fibers(self.client).items():
                if (
                    getattr(fib, "node1_id", None) == node_id
                    or getattr(fib, "node2_id", None) == node_id
                ):
                    objects.append((TYPE_FIBER, fid, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска кабелей в узле {node_id}: {e}")

        return objects

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
                    TYPE_CROSS,
                    object_id,
                    port=p,
                    side=None,
                    included_fibers=inc,
                    excluded_fibers=exc_f,
                    excluded_nodes=exc_n,
                )
                self._attach(cg)
            return self

        cg = self._build_cgraph(
            TYPE_CROSS,
            object_id,
            port=port,
            side=side,
            included_fibers=inc,
            excluded_fibers=exc_f,
            excluded_nodes=exc_n,
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

        if port is None and side is None:
            comms = self._get_commutations(TYPE_SPLITTER, object_id)
            interfaces = set()
            for rec in comms:
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                interfaces.add((s, p))
            graphs = []
            for s, p in interfaces:
                g = self._build_cgraph(
                    TYPE_SPLITTER,
                    object_id,
                    port=p,
                    side=s,
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

        if port is None and side is None:
            comms = self._get_commutations(TYPE_CWDM, object_id)
            interfaces = set()
            for rec in comms:
                if getattr(rec, "clps_last", None) == "finish":
                    continue
                s = int(rec.clps_first) if rec.clps_first is not None else 1
                p = int(rec.clps_mid) if rec.clps_mid is not None else 0
                interfaces.add((s, p))
            graphs = []
            for s, p in interfaces:
                g = self._build_cgraph(
                    TYPE_CWDM,
                    object_id,
                    port=p,
                    side=s,
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
            self.logger.warning(
                f"Не удалось построить FNGraph от узла {object_id}"
            )
            return self
        self._set_fngraph(fn)

        node_ids = [v["node_id"] for v in fn.vs]
        for node_id in node_ids:
            if exc_n is not None and node_id in exc_n:
                continue
            self.logger.debug(f"Поиск объектов в узле {node_id}")
            for obj_type, obj_id, port_info in self._get_objects_for_node(
                node_id
            ):
                obj_key = ObjKey(obj_type, obj_id)
                if self._find_cgraph_for_object(obj_key) is not None:
                    self.logger.debug(
                        f"Объект {obj_key} уже есть в графе, пропускаем"
                    )
                    continue
                try:
                    if obj_type == TYPE_CROSS:
                        # строим от всех портов кросса
                        comms = self._get_commutations(TYPE_CROSS, obj_id)
                        ports = set()
                        for rec in comms:
                            if getattr(rec, "clps_last", None) == "finish":
                                continue
                            p = (
                                int(rec.clps_mid)
                                if rec.clps_mid is not None
                                else 0
                            )
                            if p > 0:
                                ports.add(p)
                        for p in ports or [None]:
                            cg = self._build_cgraph(
                                TYPE_CROSS,
                                obj_id,
                                port=p,
                                side=None,
                                included_fibers=inc,
                                excluded_fibers=exc_f,
                                excluded_nodes=exc_n,
                            )
                            if cg is not None:
                                self._add_cgraph(cg)
                    elif obj_type == TYPE_FIBER:
                        # кабель: все волокна
                        comms = self._get_commutations(TYPE_FIBER, obj_id)
                        fiber_ports = set()
                        for rec in comms:
                            if getattr(rec, "clps_last", None) == "finish":
                                continue
                            fid = (
                                int(rec.clps_mid)
                                if rec.clps_mid is not None
                                else 0
                            )
                            if fid > 0:
                                fiber_ports.add(fid)
                        for fp in fiber_ports:
                            cg = self._build_cgraph(
                                TYPE_FIBER,
                                obj_id,
                                port=fp,
                                side=None,
                                included_fibers=inc,
                                excluded_fibers=exc_f,
                                excluded_nodes=exc_n,
                            )
                            if cg is not None:
                                self._add_cgraph(cg)
                    else:
                        cg = self._build_cgraph(
                            obj_type,
                            obj_id,
                            port=port_info,
                            included_fibers=inc,
                            excluded_fibers=exc_f,
                            excluded_nodes=exc_n,
                        )
                        if cg is not None:
                            self._add_cgraph(cg)
                except Exception as e:
                    self.logger.warning(
                        f"Ошибка построения от {obj_type}:{obj_id}: {e}"
                    )
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
        inc = _normalize_set(included_fibers)
        exc_f = _normalize_set(excluded_fibers)
        if inc is not None and object_id not in inc:
            self.logger.warning(f"Кабель {object_id} не в included_fibers")
            return self
        if exc_f is not None and object_id in exc_f:
            self.logger.warning(f"Кабель {object_id} в excluded_fibers")
            return self

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
                included_fibers=inc,
                excluded_fibers=exc_f,
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
    # finish data
    # ------------------------------------------------------------------

    def get_finish_by_node(self, node_id: int) -> List[Any]:
        result = []
        for cgraph in self.cgraphs:
            for v in cgraph.vs:
                if v.attributes().get("node_id") != node_id:
                    continue
                if v.attributes().get("terminate_vertex"):
                    finish = v.attributes().get("finish_data") or []
                    result.extend(finish)
        seen = set()
        unique = []
        for item in result:
            cid = getattr(item, "connect_id", id(item))
            if cid not in seen:
                seen.add(cid)
                unique.append(item)
        return unique

    def get_finish_by_object(
        self, object_type: str, object_id: Union[int, str]
    ) -> Optional[Any]:
        for cgraph in self.cgraphs:
            for v in cgraph.vs:
                if v["obj_type"] == object_type and str(v["obj_id"]) == str(
                    object_id
                ):
                    finish = v.attributes().get("finish_data") or []
                    return finish[0] if finish else None
        return None

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

    def fiber(self, fiber_id: int):
        return self.cache.get_fiber(self.client, fiber_id)

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

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def save_to_file(self, filepath: str) -> None:
        import pickle

        data = {
            "client": {
                "url": getattr(self.client, "_url", ""),
                "apikey": getattr(self.client, "_apikey", ""),
            },
            "cgraphs": [cg.to_dict() for cg in self.cgraphs],
            "fngraph": self.fngraph.to_dict() if self.fngraph else None,
            "cache": self.cache.to_dict(),
            "version": Topology._data_version,
        }
        with open(filepath, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        self.logger.info(f"Топология сохранена в {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "Topology":
        import pickle

        with open(filepath, "rb") as f:
            data = pickle.load(f)

        if data.get("version") != Topology._data_version:
            raise ValueError(
                f"Неподдерживаемая версия данных {data.get('version')}, "
                f"текущая {Topology._data_version}"
            )

        cache = DataCache.from_dict(data.get("cache", {}))
        client = WorkerNetClient("", data["client"]["apikey"])
        client._url = data["client"]["url"]

        topology = cls(client, cache=cache)
        for cg_data in data.get("cgraphs", []):
            cg = CGraph.from_dict(cg_data, client, cache)
            topology.cgraphs.append(cg)
        if data.get("fngraph"):
            topology.fngraph = FNGraph.from_dict(
                data["fngraph"], client, cache
            )
        topology.logger.info(f"Топология загружена из {filepath}")
        return topology

    def __repr__(self) -> str:
        fn = (
            "None"
            if self.fngraph is None
            else f"{self.fngraph.vcount()} nodes, {self.fngraph.ecount()} fibers"
        )
        return f"Topology(CGraphs: {len(self.cgraphs)}, FNGraph: {fn})"
