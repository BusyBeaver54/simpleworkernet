# simpleworkernet/utils/topology/linear.py
"""Построение линейной цепочки (LinearPathFinder)."""

from __future__ import annotations
from typing import Any, List, Optional, Set, Tuple, Union
from .constants import TYPE_CUSTOMER, TYPE_FIBER, TYPE_SPLITTER, TYPE_CROSS, TYPE_CWDM, DEVICE_TYPES, SIDE_TYPES
from .keys import Interface, ObjKey
from .errors import TopologyBuildError


class LinearPathFinder:
    """Извлекает линейный подграф из уже построенных CGraph."""

    def __init__(self, topology: Any) -> None:
        self.topology = topology
        self.client = getattr(topology, "client", None)
        self.cache = getattr(topology, "cache", None)

    def trace(
        self,
        start_type: str,
        start_id: Union[int, str],
        *,
        port: Optional[int] = None,
        side: Optional[int] = None,
        cgraph_index: int = 0,
    ):
        """Линейный CGraph от стартового объекта."""
        from .graphs.cgraph import CGraph
        from .linear_extract import extract_linear_cgraph

        cgraphs = getattr(self.topology, "cgraphs", None) or []
        if not cgraphs:
            raise ValueError(
                "Нет CGraph. Сначала вызовите NetworkTopology.build_from_*"
            )
        if cgraph_index < 0 or cgraph_index >= len(cgraphs):
            raise ValueError(f"cgraph_index={cgraph_index} вне диапазона")

        if start_type == TYPE_SPLITTER and port is None:
            raise ValueError("для splitter укажите порт")
        if start_type in (TYPE_FIBER, TYPE_CROSS, TYPE_CWDM) and side is None:
            # side обязателен для side-types при неоднозначности
            pass  # extract_linear_cgraph сам разрулит / кинет

        return extract_linear_cgraph(
            cgraphs[cgraph_index],
            start_type,
            start_id,
            end_type=None,
            end_id=None,
            port=port,
            side=side,
        )
