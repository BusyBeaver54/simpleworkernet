# simpleworkernet/utils/topology/attenuation/template_fetch.py
"""Fetch cables / inventory sections for attenuation template."""
from __future__ import annotations
from typing import Any, Sequence

def fetch_cables(client: Any) -> list:
    try:
        cables = client.Fiber.catalog_cables_get()
        return cables.to_list() if cables else []
    except Exception:
        return []

def section_ids_by_names(client: Any, catalog_names: Sequence[str]) -> list:
    names_lower = {str(n).strip().lower() for n in catalog_names if n}
    if not names_lower:
        return []
    try:
        sections = client.Inventory.get_inventory_section_catalog()
        items = sections.to_list() if sections else []
    except Exception:
        return []
    ids = []
    for sec in items:
        name = str(getattr(sec, "name", "") or "").strip().lower()
        if name in names_lower:
            sid = getattr(sec, "id", None)
            if sid is not None:
                ids.append(sid)
    return ids

def fetch_catalog_items(client: Any, section_ids: Sequence[Any]) -> list:
    out, seen = [], set()
    for sid in section_ids:
        try:
            res = client.Inventory.get_inventory_catalog(section_id=sid)
            items = res.to_list() if res else []
        except Exception:
            items = []
        for it in items:
            cid = getattr(it, "id", None)
            if cid is None or cid in seen:
                continue
            seen.add(cid)
            out.append(it)
    return out

def fetch_topology_splitters(client: Any, cache: Any = None):
    try:
        splitters = client.Splitter.get()
        sp_list = splitters.to_list() if splitters else []
    except Exception:
        sp_list = []
    inventory_by_id, catalog_by_id = {}, {}
    for sp in sp_list:
        inv_id = getattr(sp, "inventory_id", None)
        if inv_id is None:
            continue
        inv = None
        if cache is not None and hasattr(cache, "get_inventory"):
            inv = cache.get_inventory(client, inv_id)
        else:
            try:
                inv_res = client.Inventory.get_inventory(id=inv_id)
                inv = inv_res[0] if inv_res and len(inv_res) > 0 else None
            except Exception:
                inv = None
        if inv is None:
            continue
        inventory_by_id[inv_id] = inv
        cid = getattr(inv, "catalog_id", None)
        if cid is None:
            continue
        if cache is not None and hasattr(cache, "get_inventory_catalog_item"):
            item = cache.get_inventory_catalog_item(client, cid)
            if item is not None:
                catalog_by_id[cid] = item
        else:
            try:
                cat_res = client.Inventory.get_inventory_catalog(id=cid)
                item = cat_res[0] if cat_res and len(cat_res) > 0 else None
                if item is not None:
                    catalog_by_id[cid] = item
            except Exception:
                pass
    return sp_list, inventory_by_id, catalog_by_id
