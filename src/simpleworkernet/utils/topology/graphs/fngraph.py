# simpleworkernet/utils/topology/graphs/fngraph.py
"""FNGraph — граф сооружений связи (узлы + кабели)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Union

from ....core.client import WorkerNetClient
from ..cache import DataCache
from ..constants import DEVICE_TYPES, TYPE_FIBER, TYPE_OLT
from ..models import FNGraphEdge, FNGraphVertex
from .base import BaseGraph

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        from ....core.logger import log

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


class FNGraph(BaseGraph):
    """Граф сооружений: вершины — node_id, рёбра — fiber_id."""

    def __init__(
        self,
        client: WorkerNetClient,
        commutation_graph: Optional[Any] = None,
        cache: Optional[DataCache] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(directed=False, **kwargs)
        self.client = client
        self.logger = _get_logger()
        self.cache = cache if cache is not None else DataCache()
        self._commutation_graph = commutation_graph
        self._vertex_index: Dict[int, int] = {}
        self._node_fibers_cache: Dict[int, List[Any]] = {}
        self._built = False
        self._included_fibers: Optional[Set[int]] = None
        self._excluded_fibers: Optional[Set[int]] = None
        self._excluded_nodes: Optional[Set[int]] = None

    def _load_node(self, node_id: int) -> Optional[Any]:
        return self.cache.get_node(self.client, node_id)

    def _load_fiber(self, fiber_id: int) -> Optional[Any]:
        return self.cache.get_fiber(self.client, fiber_id)

    def _load_fibers_for_node(self, node_id: int) -> List[Any]:
        if node_id in self._node_fibers_cache:
            return self._node_fibers_cache[node_id]
        try:
            result = self.client.Fiber.get_list(node_id=node_id)
            fibers = result.to_list() if result else []
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кабелей для узла {node_id}: {e}")
            fibers = []
        self._node_fibers_cache[node_id] = fibers
        for fiber in fibers:
            fiber_id = getattr(fiber, "code", None)
            if fiber_id is not None:
                self.cache.set_object(TYPE_FIBER, fiber_id, fiber)
        return fibers

    def _add_node_vertex(self, node_id: int) -> int:
        if node_id in self._vertex_index:
            return self._vertex_index[node_id]
        node_obj = self._load_node(node_id)
        attrs: Dict[str, Any] = {
            "node_id": node_id,
            "name": f"node:{node_id}",
            "api_obj": node_obj,
        }
        if node_obj is not None:
            for attr in (
                "address_id",
                "coordinates",
                "type",
                "number",
                "comment",
                "location",
                "is_planned",
            ):
                if hasattr(node_obj, attr):
                    attrs[attr] = getattr(node_obj, attr)
        idx = self.add_vertex(**attrs).index
        self._vertex_index[node_id] = idx
        return idx

    def _add_fiber_edge(self, node1_id: int, node2_id: int, fiber_id: int) -> None:
        if node1_id == node2_id:
            return
        idx1 = self._add_node_vertex(node1_id)
        idx2 = self._add_node_vertex(node2_id)
        fiber_obj = self._load_fiber(fiber_id)
        self.add_edge(idx1, idx2, fiber_id=fiber_id, api_obj=fiber_obj)

    def _preferred_start_node_from_cgraph(self) -> Optional[int]:
        """Стартовое сооружение: node_id точки построения CGraph.

        Приоритет:
          1) node_id первой вершины типа OLT / device
          2) node_id первой любой вершины с node_id
        """
        cg = self._commutation_graph
        if cg is None or cg.vcount() == 0:
            return None

        # 1) device / OLT — старт build_from_device
        for prefer in (TYPE_OLT, *sorted(DEVICE_TYPES - {TYPE_OLT})):
            for v in cg.vs:
                if str(v["obj_type"]) != prefer:
                    continue
                nid = v.attributes().get("node_id")
                if nid is not None:
                    try:
                        return int(nid)
                    except (TypeError, ValueError):
                        pass

        # 2) первая вершина с node_id (обычно vs[0] = старт BFS)
        for v in cg.vs:
            nid = v.attributes().get("node_id")
            if nid is not None:
                try:
                    return int(nid)
                except (TypeError, ValueError):
                    pass
        return None

    def _order_edge_nodes(
        self, a: int, b: int, preferred_start: Optional[int] = None
    ) -> tuple:
        """Порядок концов ребра: уже известные вершины / start первыми."""
        a_known = a in self._vertex_index
        b_known = b in self._vertex_index
        if a_known and not b_known:
            return a, b
        if b_known and not a_known:
            return b, a
        if preferred_start is not None:
            if a == preferred_start:
                return a, b
            if b == preferred_start:
                return b, a
        # оба новые или оба известны — стабильный порядок по id
        return (a, b) if a <= b else (b, a)

    def _build_from_commutation_graph(self) -> None:
        if self._commutation_graph is None:
            self.logger.error("CGraph не передан")
            return
        cg = self._commutation_graph
        fiber_groups: Dict[int, Set[int]] = defaultdict(set)

        for v in cg.vs:
            if v["obj_type"] != TYPE_FIBER:
                continue
            try:
                fiber_id = int(v["obj_id"])
            except (TypeError, ValueError):
                continue
            if self._included_fibers is not None and fiber_id not in self._included_fibers:
                continue
            if self._excluded_fibers is not None and fiber_id in self._excluded_fibers:
                continue
            node_id = v.attributes().get("node_id")
            if node_id is not None:
                if self._excluded_nodes is not None and int(node_id) in self._excluded_nodes:
                    continue
                fiber_groups[fiber_id].add(int(node_id))

        # если в CGraph только одна сторона кабеля (один node_id) —
        # добираем пару node1/node2 из объекта Fiber
        for fiber_id, nodes in list(fiber_groups.items()):
            if len(nodes) >= 2:
                continue
            fiber = self._load_fiber(fiber_id)
            if fiber is None:
                continue
            n1 = getattr(fiber, "node1_id", None)
            n2 = getattr(fiber, "node2_id", None)
            if n1 is None or n2 is None:
                continue
            n1, n2 = int(n1), int(n2)
            if self._excluded_nodes is not None:
                if n1 in self._excluded_nodes or n2 in self._excluded_nodes:
                    continue
            fiber_groups[fiber_id] = {n1, n2}

        preferred_start = self._preferred_start_node_from_cgraph()
        if preferred_start is not None:
            if self._excluded_nodes is None or preferred_start not in self._excluded_nodes:
                # сооружение старта (OLT и т.п.) — всегда вершина 0
                self._add_node_vertex(preferred_start)

        # BFS по сооружениям от preferred_start, чтобы порядок vs
        # соответствовал обходу от точки построения, а не hash-order set
        adj: Dict[int, List[tuple]] = defaultdict(list)  # node -> [(neighbor, fiber_id)]
        for fiber_id, nodes in fiber_groups.items():
            node_list = list(nodes)
            if len(node_list) == 2:
                a, b = node_list[0], node_list[1]
                adj[a].append((b, fiber_id))
                adj[b].append((a, fiber_id))
            elif len(node_list) > 2:
                ordered = sorted(node_list)
                for a, b in zip(ordered, ordered[1:]):
                    adj[a].append((b, fiber_id))
                    adj[b].append((a, fiber_id))

        edges_added = 0
        added_edges: Set[tuple] = set()  # frozenset nodes + fiber_id

        def _add_unique(n1: int, n2: int, fiber_id: int) -> None:
            nonlocal edges_added
            key = (fiber_id, frozenset((n1, n2)))
            if key in added_edges:
                return
            a, b = self._order_edge_nodes(n1, n2, preferred_start)
            self._add_fiber_edge(a, b, fiber_id)
            added_edges.add(key)
            edges_added += 1

        if preferred_start is not None and preferred_start in adj:
            visited_nodes: Set[int] = set()
            queue = deque([preferred_start])
            while queue:
                current = queue.popleft()
                if current in visited_nodes:
                    continue
                visited_nodes.add(current)
                for neighbor, fiber_id in adj.get(current, []):
                    _add_unique(current, neighbor, fiber_id)
                    if neighbor not in visited_nodes:
                        queue.append(neighbor)
            # компоненты, не связанные со start (на всякий случай)
            for fiber_id, nodes in fiber_groups.items():
                node_list = list(nodes)
                if len(node_list) >= 2:
                    for a, b in zip(sorted(node_list), sorted(node_list)[1:]):
                        _add_unique(a, b, fiber_id)
                elif len(node_list) == 2:
                    _add_unique(node_list[0], node_list[1], fiber_id)
        else:
            for fiber_id, nodes in fiber_groups.items():
                node_list = sorted(nodes)
                if len(node_list) == 2:
                    _add_unique(node_list[0], node_list[1], fiber_id)
                elif len(node_list) > 2:
                    for a, b in zip(node_list, node_list[1:]):
                        _add_unique(a, b, fiber_id)

        self.logger.info(
            "FNGraph from CGraph: fibers=%s edges=%s vertices=%s start_node=%s",
            len(fiber_groups), edges_added, self.vcount(), preferred_start,
        )

    def _build_from_api(self, start_node_id: int) -> None:
        visited: Set[int] = set()
        queue = deque([start_node_id])
        # стартовый узел — всегда вершина 0
        self._add_node_vertex(start_node_id)
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            if self._excluded_nodes is not None and current in self._excluded_nodes:
                continue
            self._add_node_vertex(current)
            for fiber in self._load_fibers_for_node(current):
                fiber_id = getattr(fiber, "code", None)
                if fiber_id is None:
                    continue
                if self._included_fibers is not None and fiber_id not in self._included_fibers:
                    continue
                if self._excluded_fibers is not None and fiber_id in self._excluded_fibers:
                    continue
                node1 = getattr(fiber, "node1_id", None)
                node2 = getattr(fiber, "node2_id", None)
                if node1 is None or node2 is None:
                    continue
                neighbor = node2 if node1 == current else node1 if node2 == current else None
                if neighbor is None:
                    continue
                if self._excluded_nodes is not None and neighbor in self._excluded_nodes:
                    continue
                # current уже в индексе → останется первым концом
                self._add_fiber_edge(current, neighbor, fiber_id)
                if neighbor not in visited:
                    queue.append(neighbor)

    def build(
        self,
        start_node_id: int,
        included_fibers: Optional[Union[int, List[int], Set[int]]] = None,
        excluded_fibers: Optional[Union[int, List[int], Set[int]]] = None,
        excluded_nodes: Optional[Union[int, List[int], Set[int]]] = None,
    ) -> "FNGraph":
        self.logger.info("=== ПОСТРОЕНИЕ ГРАФА FN ===")
        self._included_fibers = _normalize_set(included_fibers)
        self._excluded_fibers = _normalize_set(excluded_fibers)
        self._excluded_nodes = _normalize_set(excluded_nodes)

        if self._commutation_graph is not None:
            self._build_from_commutation_graph()
        else:
            self._build_from_api(start_node_id)

        self._built = True
        self.logger.info("=== ПОСТРОЕНИЕ FN ЗАВЕРШЕНО ===")
        return self

    def get_vertices(self) -> List[FNGraphVertex]:
        result = []
        for v in self.vs:
            a = v.attributes()
            result.append(
                FNGraphVertex(
                    node_id=v["node_id"],
                    name=a.get("name", ""),
                    api_obj=a.get("api_obj"),
                    address_id=a.get("address_id"),
                    coordinates=a.get("coordinates"),
                    type=a.get("type"),
                    number=a.get("number"),
                    comment=a.get("comment"),
                    location=a.get("location"),
                    is_planned=a.get("is_planned"),
                )
            )
        return result

    def get_edges(self) -> List[FNGraphEdge]:
        result = []
        for e in self.es:
            a = e.attributes()
            result.append(
                FNGraphEdge(
                    source=e.source,
                    target=e.target,
                    fiber_id=a.get("fiber_id", 0),
                    api_obj=a.get("api_obj"),
                )
            )
        return result

    def to_dict(self) -> dict:
        vertices = [{k: v[k] for k in v.attributes()} for v in self.vs]
        edges = []
        for e in self.es:
            attrs = {k: e[k] for k in e.attributes()}
            attrs["source"] = e.source
            attrs["target"] = e.target
            edges.append(attrs)
        return {
            "vertices": vertices,
            "edges": edges,
            "vertex_index": self._vertex_index,
        }

    @classmethod
    def from_dict(
        cls, data: dict, client: WorkerNetClient, cache: DataCache
    ) -> "FNGraph":
        fngraph = cls(client, cache=cache)
        fngraph._vertex_index = data.get("vertex_index", {})
        for attrs in data.get("vertices", []):
            fngraph.add_vertex(**attrs)
        for edge_attrs in data.get("edges", []):
            source = edge_attrs.pop("source")
            target = edge_attrs.pop("target")
            fngraph.add_edge(source, target, **edge_attrs)
        return fngraph

    def __repr__(self) -> str:
        return f"FNGraph(nodes={self.vcount()}, fibers={self.ecount()})"
