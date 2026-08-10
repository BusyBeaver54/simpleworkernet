# simpleworkernet/utils/topology/paths.py
"""Поиск простых путей в графе (igraph-совместимый API).

Простой путь — последовательность вершин без повторов.

Алгоритм: итеративный DFS со стеком кадров
``(vertex, path, neighbor_iterator)`` — без рекурсии, с cutoff и
ограничением числа путей.
"""
from __future__ import annotations
from typing import Any, Callable, Iterable, List, Optional, Sequence, Set


def neighbors_undirected(graph: Any, v: int) -> List[int]:
    """Соседи вершины v по неориентированным рёбрам."""
    out: List[int] = []
    try:
        for eid in graph.incident(v, mode="all"):
            edge = graph.es[eid]
            n = edge.target if edge.source == v else edge.source
            out.append(int(n))
    except Exception:
        # fallback: adjacency if available
        try:
            out = [int(n) for n in graph.neighbors(v, mode="all")]
        except Exception:
            pass
    return out


def simple_paths(
    graph: Any,
    source: int,
    target: int,
    *,
    cutoff: Optional[int] = None,
    max_paths: Optional[int] = None,
    neighbors_fn: Optional[Callable[[Any, int], Iterable[int]]] = None,
) -> List[List[int]]:
    """Все простые пути source → target.

    Parameters
    ----------
    graph :
        Объект с ``incident``/``es`` или ``neighbors`` (CGraph, FNGraph, igraph.Graph).
    source, target :
        Индексы вершин.
    cutoff :
        Макс. число *рёбер* в пути (длина path-1). None — без ограничения
        (практически vcount-1).
    max_paths :
        Остановиться после нахождения N путей (None — все).
    neighbors_fn :
        Кастомная функция соседей ``(graph, v) -> iterable[int]``.

    Returns
    -------
    list[list[int]]
        Список путей, каждый путь — список индексов вершин
        ``[source, ..., target]``.

    Notes
    -----
    * source == target → ``[[source]]``
    * Сложность O(число простых путей × длина); на плотных графах
      может быть экспоненциально — используйте ``cutoff`` / ``max_paths``.
    """
    source, target = int(source), int(target)
    nget = neighbors_fn or neighbors_undirected

    if source == target:
        return [[source]]

    try:
        n_vertices = graph.vcount()
    except Exception:
        n_vertices = None

    if cutoff is None:
        # простой путь не длиннее n-1 рёбер
        max_edges = (n_vertices - 1) if n_vertices else 10**9
    else:
        max_edges = int(cutoff)

    results: List[List[int]] = []

    # Стек: (текущая вершина, путь до неё включительно)
    stack: List[tuple] = [(source, [source])]

    while stack:
        node, path = stack.pop()
        path_set = set(path)  # для O(1) проверки цикла на этом кадре
        # path_set пересоздаём — дешевле копировать path, чем поддерживать set на стеке

        for n in nget(graph, node):
            n = int(n)
            if n in path_set:
                continue  # не простой
            npath = path + [n]
            if len(npath) - 1 > max_edges:
                continue
            if n == target:
                results.append(npath)
                if max_paths is not None and len(results) >= max_paths:
                    return results
            else:
                stack.append((n, npath))

    return results


def simple_paths_from_sets(
    adjacency: dict,
    source: int,
    target: int,
    *,
    cutoff: Optional[int] = None,
    max_paths: Optional[int] = None,
) -> List[List[int]]:
    """То же для явного словаря смежности ``{v: [n1, n2, ...]}``."""

    class _Adj:
        def __init__(self, adj):
            self._adj = adj

        def vcount(self):
            return len(self._adj)

    def nget(_g, v):
        return adjacency.get(v, ())

    return simple_paths(
        _Adj(adjacency), source, target,
        cutoff=cutoff, max_paths=max_paths, neighbors_fn=nget,
    )


def has_unique_simple_path(
    graph: Any,
    source: int,
    target: int,
    *,
    cutoff: Optional[int] = None,
) -> bool:
    """True, если существует ровно один простой путь source→target."""
    paths = simple_paths(graph, source, target, cutoff=cutoff, max_paths=2)
    return len(paths) == 1


def shortest_simple_path(
    graph: Any,
    source: int,
    target: int,
    *,
    neighbors_fn: Optional[Callable[[Any, int], Iterable[int]]] = None,
) -> List[int]:
    """Кратчайший простой путь (BFS по числу рёбер).

    Быстрее полного перебора, когда нужна только кратчайшая цепочка.
    """
    source, target = int(source), int(target)
    nget = neighbors_fn or neighbors_undirected
    if source == target:
        return [source]

    from collections import deque
    prev = {source: -1}
    q = deque([source])
    while q:
        u = q.popleft()
        for v in nget(graph, u):
            v = int(v)
            if v in prev:
                continue
            prev[v] = u
            if v == target:
                # восстановить
                path = [target]
                while path[-1] != source:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            q.append(v)
    return []
