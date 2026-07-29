# simpleworkernet/utils/topology/models.py
"""Типизированные представления вершин и рёбер."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class CGraphVertex:
    """Вершина графа коммутаций."""

    obj_type: str
    obj_id: str
    side: int
    port: int
    node_id: Optional[int] = None
    name: str = ""
    api_obj: Optional[Any] = None
    splitter_type: Optional[str] = None
    terminate_vertex: bool = False
    finish_data: List[Any] = field(default_factory=list)


@dataclass
class CGraphEdge:
    """Ребро графа коммутаций."""

    source: int
    target: int
    connect_id: int = 0
    is_internal: bool = False
    api_obj: Optional[Any] = None


@dataclass
class FNGraphVertex:
    """Вершина графа сооружений связи."""

    node_id: int
    name: str = ""
    api_obj: Optional[Any] = None
    address_id: Optional[int] = None
    coordinates: Optional[Any] = None
    type: Optional[str] = None
    number: Optional[str] = None
    comment: Optional[str] = None
    location: Optional[str] = None
    is_planned: Optional[bool] = None


@dataclass
class FNGraphEdge:
    """Ребро графа сооружений (кабель)."""

    source: int
    target: int
    fiber_id: int = 0
    api_obj: Optional[Any] = None
