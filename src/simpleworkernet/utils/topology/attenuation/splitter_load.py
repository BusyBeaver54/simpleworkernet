# simpleworkernet/utils/topology/attenuation/splitter_load.py
"""Загрузка api_obj сплиттера: cache → API; нормализация name/catalog_id.

Важно: после первой попытки API результат (даже «пустой») кэшируется —
повторных HTTP на тот же splitter_id не будет.
"""
from __future__ import annotations
from typing import Any, Optional, Set
from ..constants import TYPE_SPLITTER

# id сплиттеров, для которых API уже вызывали в этом процессе (neg-cache)
_TRIED_API: Set[str] = set()


def _attr(obj, *names, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        return default
    for n in names:
        v = getattr(obj, n, None)
        if v not in (None, ""):
            return v
    return default


def cache_get_object(cache: Any, ot: str, oid: Any) -> Any:
    """get_object с перебором int/str ключей."""
    if cache is None:
        return None
    fn = getattr(cache, "get_object", None)
    if not callable(fn):
        return None
    keys = [oid]
    try:
        keys.append(int(oid))
    except (TypeError, ValueError):
        pass
    s = str(oid)
    if s not in keys:
        keys.append(s)
    seen = set()
    for k in keys:
        marker = (type(k), k)
        if marker in seen:
            continue
        seen.add(marker)
        try:
            obj = fn(ot, k)
        except Exception:
            obj = None
        if obj is not None:
            return obj
    return None


def _nested_inventory(obj: Any) -> Any:
    if obj is None:
        return None
    return _attr(obj, "inventory", "inv", "catalog_item", "catalog_obj", "item")


def extract_splitter_name(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    for candidate in (
        _attr(obj, "name", "title", "label", "caption", "model", "mark"),
        _attr(_nested_inventory(obj), "name", "title", "label", "model", "mark"),
        _attr(_attr(obj, "catalog"), "name", "title", "label"),
    ):
        if candidate not in (None, ""):
            s = str(candidate).strip()
            if s:
                return s
    return None


def extract_catalog_id(obj: Any) -> Optional[int]:
    if obj is None:
        return None
    for candidate in (
        _attr(obj, "catalog_id", "catalogId", "inventory_catalog_id"),
        _attr(_nested_inventory(obj), "catalog_id", "catalogId", "id"),
        _attr(_attr(obj, "catalog"), "id", "catalog_id"),
    ):
        if candidate in (None, ""):
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            return candidate
    return None


def splitter_obj_usable(obj: Any) -> bool:
    if obj is None:
        return False
    if extract_splitter_name(obj):
        return True
    if extract_catalog_id(obj) is not None:
        return True
    return False


def _unwrap_api_result(result: Any) -> Any:
    if result is None:
        return None
    if hasattr(result, "to_list") and callable(result.to_list):
        items = result.to_list()
        return items[0] if items else None
    if isinstance(result, (list, tuple)):
        return result[0] if result else None
    if isinstance(result, (str, bytes, int, float)):
        return None
    return result


def _sid_key(oid: Any) -> str:
    return str(oid)


def load_splitter_api(att: Any, oid: Any) -> Any:
    """cache.get_splitter(client) → client.Splitter; кладёт в cache.

    Если API уже вызывали для этого id — не повторяем (даже при «пустом» ответе).
    """
    cache = getattr(att, "cache", None)
    client = getattr(att, "client", None)
    if client is None:
        for src in (
            getattr(att, "g", None),
            getattr(att, "topology", None),
            (att.cgraphs[0] if getattr(att, "cgraphs", None) else None),
        ):
            if src is None:
                continue
            c = getattr(src, "client", None)
            if c is not None:
                client = c
                break
    if client is None:
        return None

    try:
        sid = int(oid)
    except (TypeError, ValueError):
        sid = oid
    key = _sid_key(sid)

    # 1) cache hit
    obj = None
    if cache is not None:
        fn = getattr(cache, "get_splitter", None)
        if callable(fn):
            try:
                obj = fn(client, sid)
            except Exception:
                obj = None
        if obj is None:
            obj = cache_get_object(cache, TYPE_SPLITTER, sid)

    if obj is not None:
        return obj

    # 2) уже ходили в API — не долбим снова
    if key in _TRIED_API:
        return None

    _TRIED_API.add(key)
    try:
        splitter_api = getattr(client, "Splitter", None)
        if splitter_api is not None:
            if hasattr(splitter_api, "get") and callable(splitter_api.get):
                try:
                    obj = _unwrap_api_result(splitter_api.get(id=sid))
                except TypeError:
                    obj = _unwrap_api_result(splitter_api.get(sid))
            if obj is None and hasattr(splitter_api, "get_list") and callable(splitter_api.get_list):
                try:
                    obj = _unwrap_api_result(splitter_api.get_list(object_id=sid))
                except TypeError:
                    obj = _unwrap_api_result(splitter_api.get_list(id=sid))
    except Exception:
        obj = None

    if obj is not None and cache is not None:
        set_fn = getattr(cache, "set_object", None)
        if callable(set_fn):
            try:
                set_fn(TYPE_SPLITTER, sid, obj)
            except Exception:
                try:
                    set_fn(TYPE_SPLITTER, str(sid), obj)
                except Exception:
                    pass
    return obj


def _write_vertex_api_obj(att: Any, vattrs: dict, obj: Any) -> None:
    """Записать api_obj на вершину графа, чтобы соседние сегменты/пути не грузили снова."""
    g = getattr(att, "g", None)
    if g is None:
        return
    ot = vattrs.get("obj_type")
    oid = vattrs.get("obj_id")
    side = vattrs.get("side")
    port = vattrs.get("port")
    try:
        vs = g.vs
    except Exception:
        return
    vid = vattrs.get("_vid")
    if vid is not None:
        try:
            vs[int(vid)]["api_obj"] = obj
            return
        except Exception:
            pass
    try:
        for v in vs:
            a = v.attributes()
            if str(a.get("obj_type") or "") != str(ot or ""):
                continue
            if str(a.get("obj_id") or "") != str(oid or ""):
                continue
            if side is not None and int(a.get("side") or 0) != int(side or 0):
                continue
            if port is not None and int(a.get("port") or 0) != int(port or 0):
                continue
            v["api_obj"] = obj
    except Exception:
        pass


def ensure_api_obj(att: Any, vattrs: dict) -> dict:
    """Подтянуть api_obj: cache; splitter — cache→API один раз на id.

    Пишет api_obj обратно в вершину графа.
    """
    if not vattrs:
        return vattrs

    ot = str(vattrs.get("obj_type") or "")
    oid = vattrs.get("obj_id")

    existing = vattrs.get("api_obj")
    if existing is not None:
        if ot == TYPE_SPLITTER:
            return _enrich_splitter_attrs(vattrs, existing)
        return vattrs

    if vattrs.get("_api_load_done"):
        return vattrs

    if not ot or oid is None or oid == "":
        return vattrs

    cache = getattr(att, "cache", None)
    obj = cache_get_object(cache, ot, oid)

    if ot == TYPE_SPLITTER and obj is None:
        obj = load_splitter_api(att, oid)

    vattrs = dict(vattrs)
    vattrs["_api_load_done"] = True
    if obj is not None:
        vattrs["api_obj"] = obj
        _write_vertex_api_obj(att, vattrs, obj)
        if ot == TYPE_SPLITTER:
            vattrs = _enrich_splitter_attrs(vattrs, obj)
    else:
        _write_vertex_api_obj(att, vattrs, None)
    return vattrs


def _enrich_splitter_attrs(vattrs: dict, obj: Any) -> dict:
    vattrs = dict(vattrs)
    name = extract_splitter_name(obj)
    if name and not vattrs.get("obj_name"):
        vattrs["obj_name"] = name
    cid = extract_catalog_id(obj)
    if cid is not None and vattrs.get("catalog_id") is None:
        vattrs["catalog_id"] = cid
    if not vattrs.get("splitter_type"):
        topo = _attr(obj, "topology_type", "topology", "splitter_type", "type")
        if topo not in (None, ""):
            vattrs["splitter_type"] = str(topo)
    return vattrs


def preload_splitters_from_graph(att: Any) -> int:
    """Один проход по вершинам текущего g: уникальные splitter id → cache/API.

    Возвращает число загруженных объектов.
    """
    g = getattr(att, "g", None)
    if g is None:
        return 0
    ids: Set[str] = set()
    try:
        for v in g.vs:
            a = v.attributes()
            if str(a.get("obj_type") or "") != TYPE_SPLITTER:
                continue
            oid = a.get("obj_id")
            if oid is None or oid == "":
                continue
            ids.add(str(oid))
    except Exception:
        return 0

    loaded = 0
    for sid in ids:
        obj = load_splitter_api(att, sid)
        if obj is None:
            continue
        loaded += 1
        try:
            for v in g.vs:
                a = v.attributes()
                if str(a.get("obj_type") or "") != TYPE_SPLITTER:
                    continue
                if str(a.get("obj_id") or "") != sid:
                    continue
                if a.get("api_obj") is None:
                    v["api_obj"] = obj
        except Exception:
            pass
    return loaded
