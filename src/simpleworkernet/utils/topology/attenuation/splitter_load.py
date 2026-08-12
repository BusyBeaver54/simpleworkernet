# simpleworkernet/utils/topology/attenuation/splitter_load.py
"""Загрузка api_obj сплиттера: cache → API; нормализация name/catalog_id."""
from __future__ import annotations
from typing import Any, Optional
from ..constants import TYPE_SPLITTER


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
    """inventory / catalog вложенные объекты WorkerNet Splitter."""
    if obj is None:
        return None
    return _attr(obj, "inventory", "inv", "catalog_item", "catalog_obj", "item")


def extract_splitter_name(obj: Any) -> Optional[str]:
    """Имя сплиттера: obj.name → inventory.name → catalog.name."""
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
    """catalog_id: obj → inventory → catalog."""
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
    """Есть ли у объекта имя или catalog_id для каталога затуханий."""
    if obj is None:
        return False
    if extract_splitter_name(obj):
        return True
    if extract_catalog_id(obj) is not None:
        return True
    return False


def _unwrap_api_result(result: Any) -> Any:
    """Splitter.get / get_list → один объект."""
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


def load_splitter_api(att: Any, oid: Any) -> Any:
    """cache.get_splitter(client) → client.Splitter; кладёт в cache."""
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

    obj = None
    if cache is not None:
        fn = getattr(cache, "get_splitter", None)
        if callable(fn):
            try:
                obj = fn(client, sid)
            except Exception:
                obj = None
            if obj is not None and not splitter_obj_usable(obj):
                obj = None

    if obj is None:
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


def ensure_api_obj(att: Any, vattrs: dict) -> dict:
    """Подтянуть api_obj: customer/прочие — cache; splitter — cache→API.

    После загрузки проставляет obj_name / catalog_id из inventory.
    """
    if not vattrs:
        return vattrs

    ot = str(vattrs.get("obj_type") or "")
    oid = vattrs.get("obj_id")

    existing = vattrs.get("api_obj")
    if existing is not None:
        if ot != TYPE_SPLITTER or splitter_obj_usable(existing):
            if ot == TYPE_SPLITTER:
                return _enrich_splitter_attrs(vattrs, existing)
            return vattrs

    if not ot or oid is None or oid == "":
        return vattrs

    cache = getattr(att, "cache", None)
    obj = cache_get_object(cache, ot, oid)

    if ot == TYPE_SPLITTER and not splitter_obj_usable(obj):
        loaded = load_splitter_api(att, oid)
        if loaded is not None:
            obj = loaded

    if obj is not None:
        vattrs = dict(vattrs)
        vattrs["api_obj"] = obj
        if ot == TYPE_SPLITTER:
            vattrs = _enrich_splitter_attrs(vattrs, obj)
    return vattrs


def _enrich_splitter_attrs(vattrs: dict, obj: Any) -> dict:
    """Проставить obj_name / catalog_id из api_obj в attrs вершины."""
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
