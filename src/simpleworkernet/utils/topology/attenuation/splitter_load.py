# simpleworkernet/utils/topology/attenuation/splitter_load.py
"""Загрузка api_obj сплиттера + имя/затухания из JSON-каталога.

WorkerNet Splitter.Get даёт inventory_id (без name).
Имя / ratio / ports / catalog_id — из AttenuationCatalog JSON по inventory_id.

Абоненты (customer) по API не загружаются — только in-memory cache.
Inventory API не вызывается (всё из JSON).
"""
from __future__ import annotations
from typing import Any, Optional, Set
from ..constants import TYPE_SPLITTER, TYPE_CUSTOMER

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
    """Только in-memory cache.get_object (без API)."""
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


def _resolve_client(att: Any) -> Any:
    client = getattr(att, "client", None)
    if client is not None:
        return client
    for src in (
        getattr(att, "g", None),
        getattr(att, "topology", None),
        (att.cgraphs[0] if getattr(att, "cgraphs", None) else None),
    ):
        if src is None:
            continue
        c = getattr(src, "client", None)
        if c is not None:
            return c
    return None


def load_splitter_api(att: Any, oid: Any) -> Any:
    """cache → Splitter.get; один HTTP на id (neg-cache)."""
    cache = getattr(att, "cache", None)
    client = _resolve_client(att)
    if client is None:
        return None

    try:
        sid = int(oid)
    except (TypeError, ValueError):
        sid = oid
    key = str(sid)

    obj = None
    if cache is not None:
        obj = cache_get_object(cache, TYPE_SPLITTER, sid)
        if obj is None:
            fn = getattr(cache, "get_splitter", None)
            if callable(fn):
                try:
                    obj = fn(client, sid)
                except Exception:
                    obj = None

    if obj is not None:
        return obj

    if key in _TRIED_API:
        return None
    _TRIED_API.add(key)

    try:
        splitter_api = getattr(client, "Splitter", None)
        if splitter_api is not None and hasattr(splitter_api, "get"):
            try:
                obj = _unwrap_api_result(splitter_api.get(id=sid))
            except TypeError:
                obj = _unwrap_api_result(splitter_api.get(sid))
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


def _catalog_entry_for_splitter(att: Any, *, inventory_id=None, splitter_id=None) -> Optional[dict]:
    """Запись из JSON-каталога: inventory_id → id сплиттера."""
    cat = getattr(att, "catalog", None)
    if cat is None or not hasattr(cat, "_find_splitter"):
        return None
    if inventory_id is not None:
        entry = cat._find_splitter(inventory_id=inventory_id)
        if entry is not None:
            return entry
    if splitter_id is not None:
        return cat._find_splitter(splitter_id=splitter_id)
    return None


def _topology_from_obj(obj: Any) -> Optional[str]:
    pin = _attr(obj, "port_count_in", "portCountIn")
    pout = _attr(obj, "port_count_out", "portCountOut")
    try:
        a, b = int(pin or 0), int(pout or 0)
        if a >= 1 and b >= 1:
            return f"{a}x{b}"
    except (TypeError, ValueError):
        pass
    return None


def _write_vertex_attrs(att: Any, vattrs: dict, updates: dict) -> None:
    g = getattr(att, "g", None)
    if g is None or not updates:
        return
    ot = vattrs.get("obj_type")
    oid = vattrs.get("obj_id")
    side = vattrs.get("side")
    port = vattrs.get("port")
    try:
        vs = g.vs
    except Exception:
        return
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
            for k, val in updates.items():
                try:
                    v[k] = val
                except Exception:
                    pass
    except Exception:
        pass


def ensure_api_obj(att: Any, vattrs: dict) -> dict:
    """api_obj: customer — только память (без API); splitter — cache→API + JSON-каталог.

    Затухания/имя сплиттера — из JSON по inventory_id, не из Inventory API.
    """
    if not vattrs:
        return vattrs

    ot = str(vattrs.get("obj_type") or "")
    oid = vattrs.get("obj_id")

    # --- абоненты: API запрещён ---
    if ot == TYPE_CUSTOMER:
        if vattrs.get("api_obj") is not None:
            return vattrs
        if not ot or oid is None or oid == "":
            return vattrs
        obj = cache_get_object(getattr(att, "cache", None), ot, oid)
        if obj is not None:
            vattrs = dict(vattrs)
            vattrs["api_obj"] = obj
        return vattrs

    # --- прочие не-сплиттеры: только память ---
    if ot != TYPE_SPLITTER:
        if vattrs.get("api_obj") is not None:
            return vattrs
        if not ot or oid is None or oid == "":
            return vattrs
        obj = cache_get_object(getattr(att, "cache", None), ot, oid)
        if obj is not None:
            vattrs = dict(vattrs)
            vattrs["api_obj"] = obj
        return vattrs

    # --- splitter ---
    if vattrs.get("_api_load_done") and vattrs.get("api_obj") is not None:
        if vattrs.get("inventory_id") is not None or vattrs.get("obj_name"):
            return vattrs

    if not ot or oid is None or oid == "":
        return vattrs

    obj = vattrs.get("api_obj")
    if obj is None:
        obj = cache_get_object(getattr(att, "cache", None), ot, oid)
    if obj is None:
        obj = load_splitter_api(att, oid)

    vattrs = dict(vattrs)
    vattrs["_api_load_done"] = True
    updates = {}
    if obj is not None:
        vattrs["api_obj"] = obj
        updates["api_obj"] = obj

        inv_id = _attr(obj, "inventory_id", "inventoryId")
        if inv_id is not None:
            vattrs["inventory_id"] = inv_id
            updates["inventory_id"] = inv_id

        topo = _topology_from_obj(obj)
        if topo and not vattrs.get("splitter_type"):
            vattrs["splitter_type"] = topo
            updates["splitter_type"] = topo

        entry = _catalog_entry_for_splitter(
            att, inventory_id=inv_id, splitter_id=oid,
        )
        if entry:
            if entry.get("name") and not vattrs.get("obj_name"):
                vattrs["obj_name"] = str(entry["name"])
                updates["obj_name"] = vattrs["obj_name"]
            if entry.get("catalog_id") is not None and vattrs.get("catalog_id") is None:
                vattrs["catalog_id"] = entry["catalog_id"]
                updates["catalog_id"] = entry["catalog_id"]
            if entry.get("topology") and not vattrs.get("splitter_type"):
                vattrs["splitter_type"] = str(entry["topology"])
                updates["splitter_type"] = vattrs["splitter_type"]

    if updates:
        _write_vertex_attrs(att, vattrs, updates)
    return vattrs


def preload_splitters_from_graph(att: Any) -> int:
    """Уникальные splitter id → Splitter API + JSON-каталог (без Inventory API)."""
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
        inv_id = _attr(obj, "inventory_id", "inventoryId")
        topo = _topology_from_obj(obj)
        entry = _catalog_entry_for_splitter(
            att, inventory_id=inv_id, splitter_id=sid,
        )
        try:
            for v in g.vs:
                a = v.attributes()
                if str(a.get("obj_type") or "") != TYPE_SPLITTER:
                    continue
                if str(a.get("obj_id") or "") != sid:
                    continue
                v["api_obj"] = obj
                if inv_id is not None:
                    v["inventory_id"] = inv_id
                if topo and not a.get("splitter_type"):
                    v["splitter_type"] = topo
                if entry:
                    if entry.get("name"):
                        v["obj_name"] = str(entry["name"])
                    if entry.get("catalog_id") is not None:
                        v["catalog_id"] = entry["catalog_id"]
                    if entry.get("topology") and not a.get("splitter_type"):
                        v["splitter_type"] = str(entry["topology"])
        except Exception:
            pass
    return loaded


def extract_splitter_name(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    for candidate in (
        _attr(obj, "name", "title", "label"),
        _attr(_attr(obj, "inventory", "inv"), "name", "title"),
    ):
        if candidate not in (None, ""):
            return str(candidate).strip() or None
    return None


def extract_catalog_id(obj: Any) -> Optional[int]:
    if obj is None:
        return None
    for candidate in (
        _attr(obj, "catalog_id", "catalogId"),
        _attr(_attr(obj, "inventory", "inv"), "catalog_id", "catalogId"),
    ):
        if candidate in (None, ""):
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            return candidate
    return None
