# simpleworkernet/utils/topology/attenuation/calculator_paths.py
"""Поиск путей для Attenuation (делегирует topology.paths)."""
from __future__ import annotations
from typing import List
from ..paths import simple_paths, shortest_simple_path


class AttenuationPathsMixin:
    def all_simple_paths(
        self, source: int, target: int, *, cutoff: int = 200, max_paths=None,
    ) -> List[List[int]]:
        """Все простые пути между вершинами CGraph."""
        return simple_paths(
            self.g, source, target, cutoff=cutoff, max_paths=max_paths,
        )

    def shortest_path(self, source: int, target: int) -> List[int]:
        """Кратчайший путь (BFS); fallback на igraph.get_shortest_paths."""
        path = shortest_simple_path(self.g, source, target)
        if path:
            return path
        try:
            paths = self.g.get_shortest_paths(source, target)
            if paths and paths[0]:
                return list(paths[0])
        except TypeError:
            try:
                paths = self.g.get_shortest_paths(source, to=target, output="vpath")
                if paths and paths[0]:
                    return list(paths[0])
            except Exception:
                pass
        except Exception:
            pass
        return []
