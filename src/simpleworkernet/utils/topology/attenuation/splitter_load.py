# simpleworkernet/utils/topology/attenuation/splitter_load.py
"""Загрузка api_obj сплиттера: cache → API."""
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


def splitter_obj_usable(obj: Any) -> bool:
    """Есть ли у объекта имя или catalog_id для каталога затуханий."""
    if obj is None:
        return False
    name = _attr(obj, "name", "title", "label", "caption")
    if name not in (None, ""):
        return True
    cid = _attr(obj, "catalog_id")
    return cid not in (None, "")


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

    if obj is None:
        try:
            splitter_api = getattr(client, "Splitter", None)
            if splitter_api is not None:
                if hasattr(splitter_api, "get") and callable(splitter_api.get):
                    obj = splitter_api.get(sid)
                elif hasattr(splitter_api, "get_list") and callable(splitter_api.get_list):
                    result = splitter_api.get_list(object_id=sid)
                    if result is not None:
                        if hasattr(result, "to_list") and callable(result.to_list):
                            items = result.to_list()
                            obj = items[0] if items else None
                        elif isinstance(result, (list, tuple)):
                            obj = result[0] if result else None
                        else:
                            obj = result
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
    """Подтянуть api_obj: customer/прочие — cache; splitter — cache→API."""
    if not vattrs:
        return vattrs
    if vattrs.get("api_obj") is not None:
        existing = vattrs.get("api_obj")
        ot0 = str(vattrs.get("obj_type") or "")
        if ot0 != TYPE_SPLITTER or splitter_obj_usable(existing):
            return vattrs

    ot = str(vattrs.get("obj_type") or "")
    oid = vattrs.get("obj_id")
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
    return vattrs
