# simpleworkernet/utils/topology/context.py
"""Контекст построения графа — единый носитель состояния BFS."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from .keys import Interface, ObjKey

if TYPE_CHECKING:
    from ...core.client import WorkerNetClient
    from .cache import DataCache
    from .graphs.cgraph import CGraph


@dataclass
class BuildContext:
    client: "WorkerNetClient"
    cache: "DataCache"
    graph: "CGraph"

    included_fibers: Optional[Set[int]] = None
    excluded_fibers: Optional[Set[int]] = None
    excluded_nodes: Optional[Set[int]] = None

    start_node_id: Optional[int] = None
    start_obj_key: Optional[ObjKey] = None
    start_iface: Optional[Interface] = None

    allowed_ports: Optional[Set[int]] = None
    linear: bool = False
    linear_on_fail: str = "raise"
    linear_violated: bool = False

    visited: Set[Interface] = field(default_factory=set)
    queue: deque = field(default_factory=deque)
    finish_data: Dict[ObjKey, List[Any]] = field(default_factory=dict)

    def should_stop_at_fiber(
        self, fiber_id: int, current_node_id: Optional[int]
    ) -> bool:
        if self.excluded_fibers is not None and fiber_id in self.excluded_fibers:
            return True
        if self.included_fibers is not None:
            if (
                self.start_node_id is not None
                and current_node_id == self.start_node_id
            ):
                if fiber_id not in self.included_fibers:
                    return True
        return False

    def should_stop_at_node(self, node_id: int) -> bool:
        return (
            self.excluded_nodes is not None and node_id in self.excluded_nodes
        )

    def enqueue(self, iface: Interface, parent: Optional[ObjKey] = None) -> None:
        if iface not in self.visited:
            self.visited.add(iface)
            self.queue.append((iface, parent))

    def mark_linear_violation(self, msg: str = "") -> None:
        self.linear_violated = True
        if self.linear and self.linear_on_fail == "raise":
            from .errors import TopologyBuildError
            raise TopologyBuildError(
                f"линейный CGraph невозможен: {msg}" if msg
                else "линейный CGraph невозможен на данном участке"
            )
