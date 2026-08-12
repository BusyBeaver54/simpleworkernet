# simpleworkernet/utils/topology/attenuation/calculator_paths.py
"""Поиск вершин и путей для Attenuation."""
from __future__ import annotations
from typing import List, Optional
from ..paths import simple_paths, shortest_simple_path
from ..constants import TYPE_OLT, TYPE_ONU, TYPE_RADIO, TYPE_SWITCH
from .errors import AttenuationError

_AUTO_TARGETS = frozenset({
    TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
})

_DEVICE_TYPE_PRIORITY = {
    TYPE_OLT: 0,
    TYPE_ONU: 1,
    TYPE_RADIO: 2,
    TYPE_SWITCH: 3,
}


class AttenuationPathsMixin:
    def find_vertices(
        self,
        obj_type: str,
        obj_id,
        *,
        side: Optional[int] = None,
        port: Optional[int] = None,
    ) -> List[int]:
        """Индексы вершин CGraph, совпадающих с объектом."""
        if self.g is None:
            return []
        oid = str(obj_id)
        hits: List[int] = []
        for v in self.g.vs:
            if v["obj_type"] != obj_type:
                continue
            if str(v["obj_id"]) != oid:
                continue
            if side is not None and int(v["side"] or 0) != int(side):
                continue
            if port is not None and int(v["port"] or 0) != int(port):
                continue
            hits.append(int(v.index))
        return hits

    def resolve_vertex(self, ref) -> Optional[int]:
        """Interface / (type,id,side,port) / int / 'type:id' → индекс вершины."""
        if isinstance(ref, int):
            return ref
        if self.g is None:
            return None
        if hasattr(ref, "obj") and hasattr(ref, "side"):
            ot = ref.obj.obj_type
            oid = ref.obj.id
            hits = self.find_vertices(ot, oid, side=ref.side, port=getattr(ref, "port", None))
            return hits[0] if hits else None
        if isinstance(ref, (tuple, list)) and len(ref) >= 2:
            ot, oid = ref[0], ref[1]
            side = ref[2] if len(ref) > 2 else None
            port = ref[3] if len(ref) > 3 else None
            hits = self.find_vertices(ot, oid, side=side, port=port)
            return hits[0] if hits else None
        if isinstance(ref, str) and ":" in ref:
            ot, oid = ref.split(":", 1)
            hits = self.find_vertices(ot, oid)
            return hits[0] if hits else None
        return None

    def all_simple_paths(
        self, source: int, target: int, *, cutoff: int = 200, max_paths=None,
    ) -> List[List[int]]:
        return simple_paths(
            self.g, source, target, cutoff=cutoff, max_paths=max_paths,
        )

    def shortest_path(self, source: int, target: int) -> List[int]:
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

    def shortest_paths_batch(
        self, source: int, targets: List[int],
    ) -> List[List[int]]:
        """Кратчайшие пути от source ко всем targets одним вызовом igraph.

        Возвращает список путей (пустой список, если пути нет).
        Порядок соответствует targets.
        """
        if self.g is None or not targets:
            return [[] for _ in targets]
        if len(targets) == 1:
            return [self.shortest_path(source, targets[0])]
        try:
            paths = self.g.get_shortest_paths(source, to=targets, output="vpath")
            out: List[List[int]] = []
            for p in paths:
                out.append(list(p) if p else [])
            while len(out) < len(targets):
                out.append([])
            return out[: len(targets)]
        except Exception:
            return [self.shortest_path(source, t) for t in targets]

    def find_paths(
        self,
        obj1_type: str,
        obj1_id,
        obj2_type: Optional[str] = None,
        obj2_id=None,
        *,
        obj1_side: Optional[int] = None,
        obj1_port: Optional[int] = None,
        obj2_side: Optional[int] = None,
        obj2_port: Optional[int] = None,
        cutoff: int = 200,
        max_paths: Optional[int] = None,
    ) -> List[List[int]]:
        """Все простые пути между объектами (или от obj1 до авто-терминалов)."""
        if self.g is None:
            raise AttenuationError("CGraph не задан")

        sources = self.find_vertices(
            obj1_type, obj1_id, side=obj1_side, port=obj1_port,
        )
        if not sources:
            sources = self.find_vertices(obj1_type, obj1_id, side=obj1_side)
        if not sources:
            sources = self.find_vertices(obj1_type, obj1_id)
        if not sources:
            raise AttenuationError(
                f"объект не найден в графе: {obj1_type}:{obj1_id}"
            )

        if obj2_type is not None and obj2_id is not None:
            targets = self.find_vertices(
                obj2_type, obj2_id, side=obj2_side, port=obj2_port,
            )
            if not targets:
                targets = self.find_vertices(obj2_type, obj2_id, side=obj2_side)
            if not targets:
                targets = self.find_vertices(obj2_type, obj2_id)
            if not targets:
                raise AttenuationError(
                    f"объект не найден в графе: {obj2_type}:{obj2_id}"
                )
        else:
            targets = self._auto_targets(exclude_type=obj1_type, exclude_id=obj1_id)
            if not targets:
                raise AttenuationError(
                    f"конечная точка не указана и в графе нет OLT/switch/onu/radio "
                    f"для пути от {obj1_type}:{obj1_id}"
                )

        collected: List[List[int]] = []
        seen = set()
        only_shortest = max_paths is not None and max_paths <= 1
        for s in sources:
            tgts = [t for t in targets if t != s]
            if not tgts:
                continue
            for sp in self.shortest_paths_batch(s, tgts):
                if sp and len(sp) >= 2:
                    key = tuple(sp)
                    if key not in seen:
                        seen.add(key)
                        collected.append(sp)
                    if max_paths and len(collected) >= max_paths:
                        return collected
            if only_shortest:
                continue
            for t in tgts:
                for p in self.all_simple_paths(s, t, cutoff=cutoff, max_paths=max_paths):
                    if len(p) < 2:
                        continue
                    key = tuple(p)
                    if key not in seen:
                        seen.add(key)
                        collected.append(p)
                    if max_paths and len(collected) >= max_paths:
                        return collected

        if not collected:
            raise AttenuationError(
                f"нет пути в CGraph от {obj1_type}:{obj1_id}"
                + (f" к {obj2_type}:{obj2_id}" if obj2_type else " к терминалу")
            )
        return collected

    def _auto_targets(
        self, *,
        exclude_type: Optional[str] = None,
        exclude_id=None,
    ) -> List[int]:
        """Терминалы OLT/switch/onu/radio."""
        if self.g is None:
            return []
        ex = str(exclude_id) if exclude_id is not None else None
        best = {}
        for v in self.g.vs:
            ot = v["obj_type"]
            if ot not in _AUTO_TARGETS:
                continue
            oid = str(v["obj_id"])
            if exclude_type and ot == exclude_type and oid == ex:
                continue
            pri = _DEVICE_TYPE_PRIORITY.get(ot, 99)
            prev = best.get(oid)
            if prev is None or pri < prev[0]:
                best[oid] = (pri, int(v.index))
        return [idx for _, idx in sorted(best.values(), key=lambda x: x[1])]
