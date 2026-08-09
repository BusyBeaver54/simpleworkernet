# simpleworkernet/utils/topology/topology.py
"""NetworkTopology — высокоуровневый оркестратор топологии сети."""
from __future__ import annotations
from typing import Any, List, Optional, Set, Tuple, Union
from ...core.client import WorkerNetClient
from .cache import DataCache
from .constants import (
    DEVICE_TYPES, TYPE_CROSS, TYPE_CUSTOMER, TYPE_CWDM, TYPE_FIBER, TYPE_SPLITTER,
)
from .graphs import CGraph, FNGraph
from .keys import ObjKey
from .merge import merge_cgraphs, merge_fngraphs
from .topology_build_methods import NetworkTopologyBuildMixin

_logger = None

def _get_logger():
    global _logger
    if _logger is None:
        from ...core.logger import log
        _logger = log
    return _logger

def _normalize_set(value):
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return {int(value)}
    return set(value)

class NetworkTopology(NetworkTopologyBuildMixin):
    """Высокоуровневый API топологии: список CGraph и один FNGraph."""
    _data_version = "1.0"

    def __init__(self, client: WorkerNetClient, cache: Optional[DataCache] = None) -> None:
        self.client = client
        self.logger = _get_logger()
        self.cache = cache if cache is not None else DataCache()
        self.cgraphs: List[CGraph] = []
        self.fngraph: Optional[FNGraph] = None

    def _reset(self) -> None:
        self.cgraphs = []
        self.fngraph = None

    def _get_commutations(self, obj_type: str, obj_id: Union[int, str]) -> List[Any]:
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

    def _build_fngraph_from_cgraph(self, cgraph: CGraph) -> Optional[FNGraph]:
        if cgraph is None or cgraph.vcount() == 0:
            return None
        fn = FNGraph(self.client, commutation_graph=cgraph, cache=self.cache)
        fn.build(0)
        return fn if fn.vcount() > 0 else None

    def _build_cgraph(
        self, obj_type, obj_id, port=None, side=None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
        linear=False, linear_on_fail="raise",
    ) -> Optional[CGraph]:
        cg = CGraph(self.client, cache=self.cache)
        try:
            cg.build(
                obj_type, obj_id, port=port, side=side,
                included_fibers=included_fibers, excluded_fibers=excluded_fibers,
                excluded_nodes=excluded_nodes, linear=linear, linear_on_fail=linear_on_fail,
            )
            if cg.vcount() == 0 or not cg.is_connected():
                return None
            return cg
        except Exception as e:
            self.logger.error(f"Ошибка построения CGraph от {obj_type}:{obj_id}: {e}")
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
            merged = merge_fngraphs([self.fngraph, fn], self.client, self.cache)
            self._set_fngraph(merged if merged is not None else fn)

    def _find_cgraph_for_object(self, obj_key: ObjKey) -> Optional[CGraph]:
        for cg in self.cgraphs:
            for v in cg.vs:
                if v["obj_type"] == obj_key.obj_type and str(v["obj_id"]) == str(obj_key.id):
                    return cg
        return None

    def _get_objects_for_node(self, node_id: int):
        objects = []
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
            self.logger.warning(f"Ошибка поиска сплиттеров в узле {node_id}: {e}")
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
                if getattr(fib, "node1_id", None) == node_id or getattr(fib, "node2_id", None) == node_id:
                    objects.append((TYPE_FIBER, fid, None))
        except Exception as e:
            self.logger.warning(f"Ошибка поиска кабелей в узле {node_id}: {e}")
        return objects

    def get_linear(
        self, start_type, start_id, end_type=None, end_id=None, *,
        port=None, side=None, source="cgraph", cgraph_index=0,
        start_node_id=None, end_node_id=None,
    ) -> "NetworkTopology":
        """Линейный подграф из уже построенного CGraph или FNGraph."""
        from .errors import TopologyBuildError
        from .linear_extract import extract_linear_cgraph, extract_linear_fngraph
        new_topo = NetworkTopology(self.client, cache=self.cache)
        if source == "fngraph":
            if self.fngraph is None:
                raise TopologyBuildError("FNGraph не построен")
            sn = start_node_id
            if sn is None and start_type in ("node", "facility"):
                sn = int(start_id)
            if sn is None:
                raise TopologyBuildError("для source=fngraph укажите start_node_id")
            en = end_node_id
            if en is None and end_id is not None:
                try:
                    en = int(end_id)
                except (TypeError, ValueError):
                    en = None
            new_topo._set_fngraph(extract_linear_fngraph(self.fngraph, sn, en))
            return new_topo
        if not self.cgraphs:
            raise TopologyBuildError("Нет CGraph. Сначала build_from_*")
        if cgraph_index < 0 or cgraph_index >= len(self.cgraphs):
            raise TopologyBuildError(f"cgraph_index={cgraph_index} вне диапазона")
        linear_cg = extract_linear_cgraph(
            self.cgraphs[cgraph_index], start_type, start_id, end_type, end_id,
            port=port, side=side,
        )
        new_topo._add_cgraph(linear_cg)
        fn = new_topo._build_fngraph_from_cgraph(linear_cg)
        if fn is not None:
            new_topo._set_fngraph(fn)
        return new_topo

    def get_finish_by_node(self, node_id: int) -> List[Any]:
        result = []
        for cgraph in self.cgraphs:
            for v in cgraph.vs:
                if v.attributes().get("node_id") != node_id:
                    continue
                if v.attributes().get("terminate_vertex"):
                    result.extend(v.attributes().get("finish_data") or [])
        seen, unique = set(), []
        for item in result:
            cid = getattr(item, "connect_id", id(item))
            if cid not in seen:
                seen.add(cid)
                unique.append(item)
        return unique

    def get_finish_by_object(self, object_type: str, object_id: Union[int, str]):
        for cgraph in self.cgraphs:
            for v in cgraph.vs:
                if v["obj_type"] == object_type and str(v["obj_id"]) == str(object_id):
                    finish = v.attributes().get("finish_data") or []
                    return finish[0] if finish else None
        return None

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
        return list({
            int(e.attributes().get("fiber_id", 0))
            for e in self.fngraph.es
            if e.attributes().get("fiber_id") is not None
        })

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
            "version": NetworkTopology._data_version,
        }
        with open(filepath, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        self.logger.info(f"Топология сохранена в {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "NetworkTopology":
        import pickle
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        if data.get("version") != NetworkTopology._data_version:
            raise ValueError(
                f"Неподдерживаемая версия данных {data.get('version')}, "
                f"текущая {NetworkTopology._data_version}"
            )
        cache = DataCache.from_dict(data.get("cache", {}))
        client = WorkerNetClient("", data["client"]["apikey"])
        client._url = data["client"]["url"]
        topology = cls(client, cache=cache)
        for cg_data in data.get("cgraphs", []):
            topology.cgraphs.append(CGraph.from_dict(cg_data, client, cache))
        if data.get("fngraph"):
            topology.fngraph = FNGraph.from_dict(data["fngraph"], client, cache)
        topology.logger.info(f"Топология загружена из {filepath}")
        return topology

    def __repr__(self) -> str:
        fn = (
            "None" if self.fngraph is None
            else f"{self.fngraph.vcount()} nodes, {self.fngraph.ecount()} fibers"
        )
        return f"NetworkTopology(CGraphs: {len(self.cgraphs)}, FNGraph: {fn})"
