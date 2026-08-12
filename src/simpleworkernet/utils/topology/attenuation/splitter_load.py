# simpleworkernet/utils/topology/attenuation/splitter_load.py
"""Загрузка api_obj сплиттера + имя/catalog через Inventory.

WorkerNet Splitter.Get:
  id, node_id, port_count_in, port_count_out, description, inventory_id
  — имени и catalog_id НЕТ.

Имя:  inventory_id → Inventory.get_inventory → name / catalog_id
Каталог: catalog_id → Inventory.get_inventory_catalog → name (опционально)

После первой попытки API по splitter_id повторных HTTP нет (neg-cache).
"""
from __future__ import annotations
from typing import Any, Optional, Set
from ..constants import TYPE_SPLITTER

_TRIED_API: Set[str] = set()
_TRIED_INV: Set[str] = set()


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


def load_inventory(att: Any, inventory_id: Any) -> Any:
    """cache.get_inventory / Inventory.get_inventory."""
    if inventory_id in (None, ""):
        return None
    cache = getattr(att, "cache", None)
    client = _resolve_client(att)
    key = str(inventory_id)

    if cache is not None:
        fn = getattr(cache, "get_inventory", None)
        if callable(fn) and client is not None:
            try:
                inv = fn(client, inventory_id)
                if inv is not None:
                    return inv
            except Exception:
                pass
        inv_map = getattr(cache, "_inventory", None)
        if isinstance(inv_map, dict):
            for k in (inventory_id, key):
                if k in inv_map and inv_map[k] is not None:
                    return inv_map[k]
            try:
                ik = int(inventory_id)
                if ik in inv_map:
                    return inv_map[ik]
            except (TypeError, ValueError):
                pass

    if key in _TRIED_INV:
        return None
    if client is None:
        return None
    _TRIED_INV.add(key)

    inv = None
    try:
        inv_api = getattr(client, "Inventory", None)
        if inv_api is not None and hasattr(inv_api, "get_inventory"):
            inv = _unwrap_api_result(inv_api.get_inventory(id=int(inventory_id)))
    except Exception:
        inv = None

    if inv is not None and cache is not None:
        inv_map = getattr(cache, "_inventory", None)
        if isinstance(inv_map, dict):
            inv_map[inventory_id] = inv
            try:
                inv_map[int(inventory_id)] = inv
            except (TypeError, ValueError):
                pass
    return inv


def load_inventory_catalog(att: Any, catalog_id: Any) -> Any:
    if catalog_id in (None, ""):
        return None
    cache = getattr(att, "cache", None)
    client = _resolve_client(att)

    if cache is not None:
        fn = getattr(cache, "get_inventory_catalog_item", None)
        if callable(fn) and client is not None:
            try:
                item = fn(client, catalog_id)
                if item is not None:
                    return item
            except Exception:
                pass
        cat_map = getattr(cache, "_inventory_catalog", None)
        if isinstance(cat_map, dict):
            for k in (catalog_id, str(catalog_id)):
                if k in cat_map and cat_map[k] is not None:
                    return cat_map[k]
            try:
                ck = int(catalog_id)
                if ck in cat_map:
                    return cat_map[ck]
            except (TypeError, ValueError):
                pass

    if client is None:
        return None
    try:
        inv_api = getattr(client, "Inventory", None)
        if inv_api is not None and hasattr(inv_api, "get_inventory_catalog"):
            return _unwrap_api_result(inv_api.get_inventory_catalog(id=int(catalog_id)))
    except Exception:
        return None
    return None


def resolve_splitter_identity(att: Any, splitter_obj: Any) -> dict:
    """{name, catalog_id, inventory_id, topology} из splitter+inventory."""
    out = {
        "name": None,
        "catalog_id": None,
        "inventory_id": None,
        "topology": None,
        "port_count_out": None,
        "port_count_in": None,
    }
    if splitter_obj is None:
        return out

    pin = _attr(splitter_obj, "port_count_in", "portCountIn")
    pout = _attr(splitter_obj, "port_count_out", "portCountOut")
    out["port_count_in"] = pin
    out["port_count_out"] = pout
    try:
        a, b = int(pin or 0), int(pout or 0)
        if a >= 1 and b >= 1:
            out["topology"] = f"{a}x{b}"
    except (TypeError, ValueError):
        pass

    inv_id = _attr(splitter_obj, "inventory_id", "inventoryId")
    out["inventory_id"] = inv_id

    inv = load_inventory(att, inv_id) if inv_id is not None else None
    if inv is not None:
        name = _attr(inv, "name", "title", "label")
        cid = _attr(inv, "catalog_id", "catalogId")
        if name not in (None, ""):
            out["name"] = str(name).strip()
        if cid not in (None, ""):
            try:
                out["catalog_id"] = int(cid)
            except (TypeError, ValueError):
                out["catalog_id"] = cid
            if not out["name"]:
                cat = load_inventory_catalog(att, cid)
                cname = _attr(cat, "name", "title", "label")
                if cname not in (None, ""):
                    out["name"] = str(cname).strip()

    return out


def extract_splitter_name(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    for candidate in (
        _attr(obj, "name", "title", "label", "caption", "model", "mark"),
        _attr(_attr(obj, "inventory", "inv"), "name", "title", "label"),
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
    """Подтянуть splitter + inventory name/catalog_id."""
    if not vattrs:
        return vattrs

    ot = str(vattrs.get("obj_type") or "")
    oid = vattrs.get("obj_id")

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

    if vattrs.get("_api_load_done") and vattrs.get("api_obj") is not None:
        if vattrs.get("obj_name") or vattrs.get("catalog_id") is not None:
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

        ident = resolve_splitter_identity(att, obj)
        if ident.get("name") and not vattrs.get("obj_name"):
            vattrs["obj_name"] = ident["name"]
            updates["obj_name"] = ident["name"]
        if ident.get("catalog_id") is not None and vattrs.get("catalog_id") is None:
            vattrs["catalog_id"] = ident["catalog_id"]
            updates["catalog_id"] = ident["catalog_id"]
        if ident.get("topology") and not vattrs.get("splitter_type"):
            vattrs["splitter_type"] = ident["topology"]
            updates["splitter_type"] = ident["topology"]

    if updates:
        _write_vertex_attrs(att, vattrs, updates)
    return vattrs


def preload_splitters_from_graph(att: Any) -> int:
    """Уникальные splitter id → Splitter + Inventory (имя/catalog)."""
    g = getattr(att, "g", None)
    cache = getattr(att, "cache", None)
    client = _resolve_client(att)

    if cache is not None and client is not None:
        fn = getattr(cache, "preload_splitter_inventory", None)
        if callable(fn):
            try:
                fn(client)
            except Exception:
                pass

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
        ident = resolve_splitter_identity(att, obj)
        try:
            for v in g.vs:
                a = v.attributes()
                if str(a.get("obj_type") or "") != TYPE_SPLITTER:
                    continue
                if str(a.get("obj_id") or "") != sid:
                    continue
                v["api_obj"] = obj
                if ident.get("name"):
                    v["obj_name"] = ident["name"]
                if ident.get("catalog_id") is not None:
                    v["catalog_id"] = ident["catalog_id"]
                if ident.get("topology") and not a.get("splitter_type"):
                    v["splitter_type"] = ident["topology"]
        except Exception:
            pass
    return loaded
