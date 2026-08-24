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

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        from ...core.logger import log
        _logger = log
    return _logger


def _normalize_set(value: Any) -> Optional[set]:
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return {int(value)}
    return set(value)


class NetworkTopologyBuildMixin:
    def build_from_device(
        self, object_type: str, object_id: int, port: object = None,
        included_fibers: object = None, excluded_fibers: object = None,
        excluded_nodes: object = None,
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
        return self._finalize_build()

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
        return self._finalize_build()

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
                if side is None:
                    for s in (1, 2):
                        self._attach(self._build_cgraph(
                            TYPE_CROSS, object_id, port=p, side=s,
                            included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                        ))
                else:
                    try:
                        s0 = int(side)
                    except (TypeError, ValueError):
                        s0 = 1
                    opp = 2 if s0 == 1 else 1
                    self._attach(self._build_cgraph(
                        TYPE_CROSS, object_id, port=p, side=opp,
                        included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                    ))
            return self._finalize_build()
        # port задан
        if side is None:
            for s in (1, 2):
                self._attach(self._build_cgraph(
                    TYPE_CROSS, object_id, port=port, side=s,
                    included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
                ))
        else:
            try:
                s0 = int(side)
            except (TypeError, ValueError):
                s0 = 1
            opp = 2 if s0 == 1 else 1
            self._attach(self._build_cgraph(
                TYPE_CROSS, object_id, port=port, side=opp,
                included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
            ))
        return self._finalize_build()

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
            return self._finalize_build()
        self._attach(self._build_cgraph(
            TYPE_SPLITTER, object_id, port=port, side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        ))
        return self._finalize_build()

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
            return self._finalize_build()
        self._attach(self._build_cgraph(
            TYPE_CWDM, object_id, port=port, side=side,
            included_fibers=_normalize_set(included_fibers),
            excluded_fibers=_normalize_set(excluded_fibers),
            excluded_nodes=_normalize_set(excluded_nodes),
        ))
        return self._finalize_build()

    def build_from_fiber(
        self, object_id: int, port=None, side: Optional[int] = None,
        included_fibers=None, excluded_fibers=None, excluded_nodes=None,
    ) -> "NetworkTopology":
        """
        Кабель/волокно.
        - side is None → строим от обеих сторон (side=1 и side=2), графы объединяются.
        - side задан → строим в противоположную сторону (от выбранного конца наружу).
        - port is None → все ОВ кабеля (через expand в _build_cgraph / стартовые Interface).
        """
        self._reset()
        self.logger.info(f"=== BUILD FROM FIBER: cable={object_id}, port={port}, side={side} ===")
        inc = _normalize_set(included_fibers)
        exc_f = _normalize_set(excluded_fibers)
        exc_n = _normalize_set(excluded_nodes)

        def _attach_side(s):
            self._attach(self._build_cgraph(
                TYPE_FIBER, object_id, port=port, side=s,
                included_fibers=inc, excluded_fibers=exc_f, excluded_nodes=exc_n,
            ))

        if side is None:
            for s in (1, 2):
                _attach_side(s)
        else:
            try:
                s0 = int(side)
            except (TypeError, ValueError):
                s0 = 1
            # выбранная сторона — «где стоим»; строим в противоположную
            opp = 2 if s0 == 1 else 1
            self.logger.info(f"FIBER side={s0} → build opposite side={opp}")
            _attach_side(opp)
        return self._finalize_build()

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
            return self._finalize_build()
        self._set_fngraph(fn)
        for node_id in [v["node_id"] for v in fn.vs]:
            if exc_n is not None and node_id in exc_n:
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
        return self._finalize_build()

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
            return self._finalize_build()
        if exc_f is not None and object_id in exc_f:
            self.logger.warning(f"Кабель {object_id} в excluded_fibers")
            return self._finalize_build()
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
        return self._finalize_build()


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

    def _get_objects_for_node(self, node_id: int) -> List[Any]:
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
        self,
        object_type: Optional[str] = None,
        object_id: Optional[Union[int, str]] = None,
        port: Any = None,
        side: Optional[int] = None,
        source: str = "cgraph",
        cgraph_index: int = 0,
    ) -> Any:
        from .errors import TopologyBuildError
        from .linear import extract_linear_cgraph, extract_linear_fngraph
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
        """Commutation.Get_data (finish) для конечных вершин CGraph в node_id.

        Конечная вершина: ``terminate_vertex`` или degree==1 в CGraph.
        Источники записей: ``v["finish_data"]`` и ``cgraph._finish_data``
        (записи с clps_last='finish' при загрузке is_finish_data=1).
        """
        nid = int(node_id)
        out: List[Any] = []
        seen: set = set()

        def _add(items: Any) -> None:
            for rec in items or []:
                cid = getattr(rec, "connect_id", None)
                if cid is not None:
                    try:
                        key = int(cid)
                    except Exception:
                        key = cid
                    if key in seen:
                        continue
                    seen.add(key)
                out.append(rec)

        def _obj_pair(obj_type: Any, obj_id: Any) -> tuple:
            return (str(obj_type), str(obj_id))

        for cg in self.cgraphs:
            try:
                vs = cg.vs
            except Exception:
                continue

            term_objs: set = set()
            for v in vs:
                try:
                    vn = v["node_id"]
                    if vn is None or int(vn) != nid:
                        continue
                except Exception:
                    continue

                is_term = False
                try:
                    is_term = bool(v["terminate_vertex"])
                except Exception:
                    pass
                # leaf в CGraph тоже считаем конечной
                if not is_term:
                    try:
                        is_term = int(v.degree()) <= 1
                    except Exception:
                        pass

                items: List[Any] = []
                try:
                    items = list(v["finish_data"] or [])
                except Exception:
                    items = []

                if not is_term and not items:
                    continue
                try:
                    term_objs.add(_obj_pair(v["obj_type"], v["obj_id"]))
                except Exception:
                    pass
                _add(items)

            fd = getattr(cg, "_finish_data", None) or {}
            for key, items in fd.items():
                ot = getattr(key, "obj_type", None)
                oid = getattr(key, "id", None)
                if _obj_pair(ot, oid) in term_objs:
                    _add(items)
        return out


    def get_finish_by_object(self, object_type: str, object_id: Union[int, str]) -> List[Any]:
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

    def customer(self, customer_id: int) -> Optional[Any]:
        """Данные абонента: кэш или точечный API (Customer.get_data).

        При BFS/затуханиях API не вызывается (см. CGraph.load_object /
        ensure_api_obj) — только уже закэшированные объекты.
        """
        return self.cache.get_customer(self.client, int(customer_id))

    def node(self, node_id: int) -> Optional[Any]:
        return self.cache.get_node(self.client, node_id)

    def cable(self, cable_id: int) -> Optional[Any]:
        return self.fiber(cable_id)

    def fiber(self, fiber_id: int) -> Optional[Any]:
        return self.cache.get_fiber(self.client, fiber_id)

    def device(self, device_id: int, object_type: Optional[str] = None) -> Optional[Any]:
        """Устройство по id. object_type (olt/switch/onu/radio) опционален —
        без него API вызывается с object_type=all."""
        return self.cache.get_device(self.client, object_type, int(device_id))

    def splitter(self, splitter_id: int) -> Optional[Any]:
        return self.cache.get_splitter(self.client, splitter_id)

    def cwdm(self, cwdm_id: int) -> Optional[Any]:
        return self.cache.get_cwdm(self.client, cwdm_id)

    def cross(self, cross_uuid: str) -> Optional[Any]:
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
