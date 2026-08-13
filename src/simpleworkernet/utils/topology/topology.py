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
        self.cache = (
            cache if cache is not None
            else DataCache(client)
        )
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
        """Добавить CGraph. Несвязный → разбить на связные компоненты.

        Каждый порт OLT — своё дерево; не смешиваем в одном CGraph.
        Warning оставляем для отладки.
        """
        if cgraph is None or cgraph.vcount() == 0:
            return
        if cgraph.is_connected():
            self.cgraphs.append(cgraph)
            return
        parts = self._split_cgraph_components(cgraph)
        if not parts:
            self.logger.warning(
                "CGraph не связный (v=%s e=%s) и не удалось разбить — пропускаем",
                cgraph.vcount(), cgraph.ecount(),
            )
            return
        self.logger.warning(
            "CGraph не связный (v=%s e=%s) → %s связных компонент",
            cgraph.vcount(), cgraph.ecount(), len(parts),
        )
        for part in parts:
            if part.vcount() > 0:
                self.cgraphs.append(part)

    def _split_cgraph_components(self, cgraph: CGraph) -> List[CGraph]:
        """Разбить несвязный CGraph на список связных подграфов."""
        if cgraph is None or cgraph.vcount() == 0:
            return []
        try:
            membership = cgraph.g.components().membership
        except Exception:
            try:
                membership = cgraph._g.components().membership
            except Exception as e:
                self.logger.warning("components() failed: %s", e)
                return []
        groups: dict = {}
        for vid, cid in enumerate(membership):
            groups.setdefault(int(cid), []).append(int(vid))
        if len(groups) <= 1:
            return [cgraph]
        out: List[CGraph] = []
        for vids in groups.values():
            if not vids:
                continue
            try:
                sub = cgraph.g.subgraph(vids)
            except Exception:
                try:
                    sub = cgraph._g.subgraph(vids)
                except Exception:
                    continue
            part = CGraph(self.client, cache=self.cache)
            part._g = sub
            if hasattr(cgraph, "_directed"):
                part._directed = getattr(cgraph, "_directed", False)
            if hasattr(cgraph, "_finish_data"):
                part._finish_data = getattr(cgraph, "_finish_data", None)
            if part.vcount() > 0:
                out.append(part)
        return out

    def _set_fngraph(self, fngraph: Optional[FNGraph]) -> None:
        """Промежуточная установка без проверки связности (финал — _finalize_build)."""
        if fngraph is None or fngraph.vcount() == 0:
            return
        self.fngraph = fngraph

    def _build_fngraph_from_cgraph(self, cgraph: CGraph) -> Optional[FNGraph]:
        if cgraph is None or cgraph.vcount() == 0:
            return None
        fn = FNGraph(self.client, commutation_graph=cgraph, cache=self.cache)
        fn.build(0)
        if fn.vcount() == 0:
            self.logger.warning(
                "FNGraph пустой после CGraph (v=%s e=%s)",
                cgraph.vcount(), cgraph.ecount(),
            )
            return None
        return fn

    def _rebuild_fngraph_from_all_cgraphs(self) -> None:
        fns: List[FNGraph] = []
        for cg in self.cgraphs:
            fn = self._build_fngraph_from_cgraph(cg)
            if fn is not None:
                fns.append(fn)
        if not fns:
            self.fngraph = None
            return
        if len(fns) == 1:
            self.fngraph = fns[0]
        else:
            self.fngraph = merge_fngraphs(fns, client=self.client, cache=self.cache)

    def _finalize_build(self) -> "NetworkTopology":
        from .errors import TopologyBuildError
        self._rebuild_fngraph_from_all_cgraphs()
        if self.fngraph is None or self.fngraph.vcount() == 0:
            self.logger.warning("FNGraph пуст после финализации")
            return self
        if not self.fngraph.is_connected():
            self.logger.warning(
                "FNGraph не связный (v=%s e=%s)",
                self.fngraph.vcount(), self.fngraph.ecount(),
            )
        else:
            self.logger.info(
                "FNGraph OK: v=%s e=%s (из %s CGraph)",
                self.fngraph.vcount(), self.fngraph.ecount(), len(self.cgraphs),
            )
        return self

    def _build_cgraph(
        self, obj_type, obj_id, port=None, side=None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
        linear=False, linear_on_fail="raise",
    ) -> Optional[CGraph]:
        """Построить CGraph. Несколько портов → отдельный связный граф на порт."""
        from .ports_spec import expand_ports
        ports = expand_ports(port)
        if ports is not None and len(ports) > 1:
            graphs = self._build_cgraphs_per_port(
                obj_type, obj_id, ports=ports, side=side,
                included_fibers=included_fibers, excluded_fibers=excluded_fibers,
                excluded_nodes=excluded_nodes, linear=linear, linear_on_fail=linear_on_fail,
            )
            if not graphs:
                return None
            if len(graphs) == 1:
                return graphs[0]
            for g in graphs:
                self._add_cgraph(g)
            return None

        cg = CGraph(self.client, cache=self.cache)
        try:
            cg.build(
                obj_type, obj_id, port=port, side=side,
                included_fibers=included_fibers, excluded_fibers=excluded_fibers,
                excluded_nodes=excluded_nodes, linear=linear, linear_on_fail=linear_on_fail,
            )
            if cg.vcount() == 0:
                self.logger.warning(
                    "CGraph пустой от %s:%s (port=%r)", obj_type, obj_id, port
                )
                return None
            return cg
        except Exception as e:
            self.logger.error(f"Ошибка построения CGraph от {obj_type}:{obj_id}: {e}")
            return None

    def _build_cgraphs_per_port(
        self, obj_type, obj_id, *, ports, side=None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
        linear=False, linear_on_fail="raise",
    ) -> List[CGraph]:
        """Один связный CGraph на каждый порт (OLT multi-port)."""
        out: List[CGraph] = []
        for p in sorted(ports):
            cg = CGraph(self.client, cache=self.cache)
            try:
                cg.build(
                    obj_type, obj_id, port=p, side=side,
                    included_fibers=included_fibers, excluded_fibers=excluded_fibers,
                    excluded_nodes=excluded_nodes, linear=linear,
                    linear_on_fail=linear_on_fail,
                )
            except Exception as e:
                self.logger.error(
                    "Ошибка CGraph от %s:%s port=%s: %s", obj_type, obj_id, p, e
                )
                continue
            if cg.vcount() == 0:
                self.logger.debug(
                    "CGraph пустой от %s:%s port=%s — пропускаем", obj_type, obj_id, p
                )
                continue
            out.append(cg)
        return out

    def _attach(self, cgraph: Optional[CGraph]) -> None:
        if cgraph is None:
            return
        self._add_cgraph(cgraph)

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

    def get_linear(self, object_type=None, object_id=None, port=None, side=None, source="cgraph", cgraph_index=0):
        from .errors import TopologyBuildError
        from .linear_extract import extract_linear_cgraph, extract_linear_fngraph
        if source == "fngraph":
            if self.fngraph is None:
                raise TopologyBuildError("FNGraph не построен")
            return extract_linear_fngraph(self.fngraph, object_type, object_id, port=port, side=side)
        if not self.cgraphs:
            raise TopologyBuildError("Нет CGraph")
        idx = int(cgraph_index) if cgraph_index is not None else 0
        if idx < 0 or idx >= len(self.cgraphs):
            raise TopologyBuildError(f"cgraph_index={idx} вне диапазона 0..{len(self.cgraphs)-1}")
        return extract_linear_cgraph(
            self.cgraphs[idx], object_type, object_id, port=port, side=side,
        )

    def get_finish_by_node(self, node_id: int) -> List[Any]:
        out = []
        for cg in self.cgraphs:
            fd = getattr(cg, "_finish_data", None) or {}
            for key, items in fd.items():
                out.extend(items or [])
        return out

    def get_finish_by_object(self, object_type: str, object_id: Union[int, str]):
        out = []
        for cg in self.cgraphs:
            fd = getattr(cg, "_finish_data", None) or {}
            for key, items in fd.items():
                if getattr(key, "obj_type", None) == object_type and str(getattr(key, "id", "")) == str(object_id):
                    out.extend(items or [])
        return out

    def _collect_ids(self, obj_type: str) -> List:
        ids = set()
        for cg in self.cgraphs:
            for v in cg.vs:
                if v["obj_type"] == obj_type:
                    ids.add(v["obj_id"])
        return sorted(ids, key=lambda x: str(x))

    def get_customers(self) -> List[int]:
        return [int(x) for x in self._collect_ids(TYPE_CUSTOMER)]

    def get_nodes(self) -> List[int]:
        ids = set()
        if self.fngraph is not None:
            for v in self.fngraph.vs:
                nid = v["node_id"] if "node_id" in v.attributes() else None
                if nid is not None:
                    ids.add(int(nid))
        return sorted(ids)

    def get_cables(self) -> List[int]:
        return self.get_fibers()

    def get_fibers(self) -> List[int]:
        return [int(x) for x in self._collect_ids(TYPE_FIBER)]

    def get_devices(self) -> List[int]:
        ids = set()
        for cg in self.cgraphs:
            for v in cg.vs:
                if v["obj_type"] in DEVICE_TYPES:
                    ids.add(int(v["obj_id"]))
        return sorted(ids)

    def get_splitters(self) -> List[int]:
        return [int(x) for x in self._collect_ids(TYPE_SPLITTER)]

    def get_cwdms(self) -> List[int]:
        return [int(x) for x in self._collect_ids(TYPE_CWDM)]

    def get_crosses(self) -> List[str]:
        return [str(x) for x in self._collect_ids(TYPE_CROSS)]

    def customer(self, customer_id: int):
        """Данные абонента: кэш или точечный API (Customer.get_data).

        При BFS/затуханиях API не вызывается (см. CGraph.load_object /
        ensure_api_obj) — только уже закэшированные объекты.
        """
        return self.cache.get_customer(self.client, int(customer_id))

    def node(self, node_id: int):
        return self.cache.get_node(self.client, node_id)

    def cable(self, cable_id: int):
        return self.fiber(cable_id)

    def fiber(self, fiber_id: int):
        return self.cache.get_fiber(self.client, fiber_id)

    def device(self, device_id: int):
        return self.cache.get_device(self.client, None, device_id)

    def splitter(self, splitter_id: int):
        return self.cache.get_splitter(self.client, splitter_id)

    def cwdm(self, cwdm_id: int):
        return self.cache.get_cwdm(self.client, cwdm_id)

    def cross(self, cross_uuid: str):
        return self.cache.get_cross(self.client, cross_uuid)

    def save_to_file(self, filepath: str) -> None:
        import pickle
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load_from_file(cls, filepath: str) -> "NetworkTopology":
        import pickle
        with open(filepath, "rb") as f:
            return pickle.load(f)

    def __repr__(self) -> str:
        return (
            f"NetworkTopology(cgraphs={len(self.cgraphs)}, "
            f"fngraph_v={self.fngraph.vcount() if self.fngraph else 0})"
        )
