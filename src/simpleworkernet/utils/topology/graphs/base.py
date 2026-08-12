# simpleworkernet/utils/topology/graphs/base.py
"""Базовая обёртка над igraph (composition, не inheritance)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import igraph as ig


class BaseGraph:
    """
    Thin wrapper around igraph.Graph.

    Composition вместо inheritance — проще сериализация, типизация и тесты.
    """

    def __init__(self, directed: bool = False, **kwargs: Any) -> None:
        self._g = ig.Graph(directed=directed, **kwargs)

    # --- proxies ---

    @property
    def g(self) -> ig.Graph:
        return self._g

    def vcount(self) -> int:
        return self._g.vcount()

    def ecount(self) -> int:
        return self._g.ecount()

    @property
    def vs(self):
        return self._g.vs

    @property
    def es(self):
        return self._g.es

    def add_vertex(self, **attrs: Any):
        return self._g.add_vertex(**attrs)

    def add_edge(self, source: int, target: int, **attrs: Any):
        return self._g.add_edge(source, target, **attrs)

    def are_connected(self, v1: int, v2: int) -> bool:
        return bool(self._g.are_connected(v1, v2))

    def is_connected(self) -> bool:
        if self._g.vcount() == 0:
            return False
        return bool(self._g.is_connected())

    def incident(self, vid: int, mode: str = "all"):
        return self._g.incident(vid, mode=mode)

    def get_eid(self, v1: int, v2: int, error: bool = True) -> int:
        return self._g.get_eid(v1, v2, error=error)

    def get_shortest_paths(
        self, source: int, target: int, mode: str = "all"
    ) -> List[List[int]]:
        """Кратчайшие пути source→target.

        Если target недостижим, igraph пишет RuntimeWarning
        «Couldn't reach some vertices» — подавляем и возвращаем [].
        """
        import warnings
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Couldn't reach some vertices",
                    category=RuntimeWarning,
                )
                paths = self._g.get_shortest_paths(source, to=target, mode=mode)
        except Exception:
            return []
        out: List[List[int]] = []
        for pth in paths or []:
            if pth:
                out.append([int(x) for x in pth])
        return out

    def write_graphml(self, filename: str) -> None:
        self._g.write_graphml(filename)
