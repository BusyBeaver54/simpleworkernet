# simpleworkernet/utils/topology/graphs/cgraph.py
"""CGraph — граф коммутаций (интерфейсы + рёбра-коммутации)."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Union

from ....core.client import WorkerNetClient
from ..cache import DataCache
from ..constants import (
    DEVICE_TYPES,
    SIDE_TYPES,
    TERMINAL_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_CWDM,
    TYPE_FIBER,
    TYPE_OLT,
    TYPE_SPLITTER,
    TYPE_SWITCH,
)
from ..context import BuildContext
from ..keys import Interface, ObjKey
from ..models import CGraphEdge, CGraphVertex
from .base import BaseGraph

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        from ....core.logger import log

        _logger = log
    return _logger


class CGraph(BaseGraph):
    """
    Граф коммутаций: вершины — Interface, рёбра — коммутации.

    Использует composition (BaseGraph) и BuildContext + handlers для BFS.
    """

    def __init__(
        self,
        client: WorkerNetClient,
        cache: Optional[DataCache] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()
        self.cache = cache if cache is not None else DataCache()
        self._vertex_index: Dict[Interface, int] = {}
        self._directed: bool = False
        self._finish_data: Dict[ObjKey, List[Any]] = {}

    # ------------------------------------------------------------------
    # Загрузка
    # ------------------------------------------------------------------

    def load_object(self, obj_key: ObjKey) -> Optional[Any]:
        t, oid = obj_key.obj_type, obj_key.id
        if t in DEVICE_TYPES:
            return self.cache.get_device(self.client, t, int(oid))
        if t == TYPE_CROSS:
            return self.cache.get_cross(self.client, str(oid))
        if t == TYPE_SPLITTER:
            return self.cache.get_splitter(self.client, int(oid))
        if t == TYPE_FIBER:
            return self.cache.get_fiber(self.client, int(oid))
        if t == TYPE_CUSTOMER:
            # для ускорения построений абонентов не тянем
            return None
        if t == TYPE_CWDM:
            return self.cache.get_cwdm(self.client, int(oid))
        return None

    def load_commutations(self, obj_key: ObjKey) -> List[Any]:
        return self.cache.get_commutations_by_object(
            self.client, obj_key.obj_type, obj_key.id, is_finish_data=1
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_node_id_from_obj(
        self, obj: Any, side: Optional[int] = None
    ) -> Optional[int]:
        if obj is None:
            return None
        if hasattr(obj, "node1_id") and hasattr(obj, "node2_id"):
            if side == 1:
                return getattr(obj, "node1_id", None)
            if side == 2:
                return getattr(obj, "node2_id", None)
            return getattr(obj, "node1_id", None)
        return getattr(obj, "node_id", None)

    def get_splitter_type(self, obj: Any) -> Optional[str]:
        if obj is None:
            return None
        pin = getattr(obj, "port_count_in", 0) or 0
        pout = getattr(obj, "port_count_out", 0) or 0
        if pin == 0 or pout == 0:
            return None
        return f"{pin}x{pout}"

    # ------------------------------------------------------------------
    # Вершины / рёбра
    # ------------------------------------------------------------------

    def add_iface_vertex(
        self,
        iface: Interface,
        obj: Optional[Any] = None,
        node_id_override: Optional[int] = None,
    ) -> int:
        if iface in self._vertex_index:
            return self._vertex_index[iface]

        if obj is None:
            obj = self.load_object(iface.obj)

        node_id = node_id_override
        if node_id is None and obj is not None:
            side_for_node = iface.side if iface.obj.obj_type == TYPE_FIBER else None
            node_id = self.get_node_id_from_obj(obj, side_for_node)

        splitter_type = None
        if iface.obj.obj_type == TYPE_SPLITTER and obj is not None:
            splitter_type = self.get_splitter_type(obj)

        attrs = {
            "obj_type": iface.obj.obj_type,
            "obj_id": str(iface.obj.id),
            "side": iface.side,
            "port": iface.port,
            "node_id": node_id,
            "name": str(iface),
            "api_obj": obj,
            "splitter_type": splitter_type,
            "terminate_vertex": False,
            "finish_data": [],
        }
        idx = self.add_vertex(**attrs).index
        self._vertex_index[iface] = idx
        return idx

    def add_iface_edge(
        self,
        iface1: Interface,
        iface2: Interface,
        connect_id: int,
        node_id_for_vertex2: Optional[int] = None,
        is_internal: bool = False,
    ) -> None:
        obj1 = self.load_object(iface1.obj)
        obj2 = self.load_object(iface2.obj)
        idx1 = self.add_iface_vertex(iface1, obj=obj1)
        idx2 = self.add_iface_vertex(
            iface2, obj=obj2, node_id_override=node_id_for_vertex2
        )
        if self.are_connected(idx1, idx2):
            return
        self.add_edge(
            idx1,
            idx2,
            connect_id=connect_id,
            is_internal=is_internal,
            api_obj=None,
        )

    # ------------------------------------------------------------------
    # Построение (точка входа)
    # ------------------------------------------------------------------

    def build(
        self,
        object_type: str,
        object_id: Union[int, str],
        port: Optional[int] = None,
        side: Optional[int] = None,
        included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
        excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
        excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None,
        *,
        linear: bool = False,
    ) -> "CGraph":
        """
        Строит граф от объекта.

        Делегирует BFS в builders (handlers).

        linear=False (по умолчанию) — обычный обход.
        linear=True — строить линейный граф; если однозначно нельзя
        (ветвление и т.п.) — TopologyBuildError.
        """
        from ..builders.base import GraphBuilder

        builder = GraphBuilder(self)
        return builder.build(
            object_type=object_type,
            object_id=object_id,
            port=port,
            side=side,
            included_fibers=included_fibers,
            excluded_fibers=excluded_fibers,
            excluded_nodes=excluded_nodes,
            linear=bool(linear),
            linear_on_fail="raise",
        )

    def update_directed_flag(self) -> None:
        has_splitter = any(v["obj_type"] == TYPE_SPLITTER for v in self.vs)
        has_cwdm = any(v["obj_type"] == TYPE_CWDM for v in self.vs)
        has_customer = any(v["obj_type"] == TYPE_CUSTOMER for v in self.vs)
        self._directed = has_splitter or has_cwdm or has_customer

    @property
    def directed(self) -> bool:
        return self._directed

    # ------------------------------------------------------------------
    # Удобный доступ
    # ------------------------------------------------------------------

    def get_vertices(self) -> List[CGraphVertex]:
        result = []
        for v in self.vs:
            attrs = v.attributes()
            result.append(
                CGraphVertex(
                    obj_type=v["obj_type"],
                    obj_id=v["obj_id"],
                    side=attrs.get("side", 1),
                    port=attrs.get("port", 0),
                    node_id=attrs.get("node_id"),
                    name=attrs.get("name", ""),
                    api_obj=attrs.get("api_obj"),
                    splitter_type=attrs.get("splitter_type"),
                    terminate_vertex=attrs.get("terminate_vertex", False),
                    finish_data=attrs.get("finish_data", []),
                )
            )
        return result

    def get_edges(self) -> List[CGraphEdge]:
        result = []
        for e in self.es:
            attrs = e.attributes()
            result.append(
                CGraphEdge(
                    source=e.source,
                    target=e.target,
                    connect_id=attrs.get("connect_id", 0),
                    is_internal=attrs.get("is_internal", False),
                    api_obj=attrs.get("api_obj"),
                )
            )
        return result

    def get_vertex(self, index: int) -> Optional[CGraphVertex]:
        if index < 0 or index >= self.vcount():
            return None
        return self.get_vertices()[index]

    def get_edge(self, index: int) -> Optional[CGraphEdge]:
        if index < 0 or index >= self.ecount():
            return None
        return self.get_edges()[index]

    # ------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        vertices = []
        for v in self.vs:
            attrs = {k: v[k] for k in v.attributes()}
            if "api_obj" in attrs:
                try:
                    if hasattr(attrs["api_obj"], "dict"):
                        attrs["api_obj"] = attrs["api_obj"].dict()
                    else:
                        attrs["api_obj"] = str(attrs["api_obj"])
                except Exception:
                    attrs["api_obj"] = None
            vertices.append(attrs)

        edges = []
        for e in self.es:
            attrs = {k: e[k] for k in e.attributes()}
            attrs["source"] = e.source
            attrs["target"] = e.target
            edges.append(attrs)

        vertex_index = {
            (iface.obj.obj_type, iface.obj.id, iface.side, iface.port): idx
            for iface, idx in self._vertex_index.items()
        }

        return {
            "vertices": vertices,
            "edges": edges,
            "vertex_index": vertex_index,
            "directed": self._directed,
        }

    @classmethod
    def from_dict(
        cls, data: dict, client: WorkerNetClient, cache: DataCache
    ) -> "CGraph":
        cgraph = cls(client, cache=cache)
        cgraph._directed = data.get("directed", False)
        for attrs in data.get("vertices", []):
            cgraph.add_vertex(**attrs)
        for edge_attrs in data.get("edges", []):
            source = edge_attrs.pop("source")
            target = edge_attrs.pop("target")
            cgraph.add_edge(source, target, **edge_attrs)
        for (obj_type, obj_id, side, port), idx in data.get(
            "vertex_index", {}
        ).items():
            iface = Interface(ObjKey(obj_type, obj_id), side, port)
            cgraph._vertex_index[iface] = idx
        return cgraph

    def __repr__(self) -> str:
        return (
            f"CGraph(interfaces={self.vcount()}, "
            f"commutations={self.ecount()}, directed={self._directed})"
        )
