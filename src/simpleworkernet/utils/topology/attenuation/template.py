# simpleworkernet/utils/topology/attenuation/template.py
"""Генерация JSON-шаблона затуханий из live WorkerNet."""

from __future__ import annotations

from typing import Any, Optional, Union
from pathlib import Path

from .catalog import AttenuationCatalog


def generate_template(
    client: Any,
    *,
    cache: Any = None,
    path: Optional[Union[str, Path]] = None,
    fill_defaults: bool = False,
) -> AttenuationCatalog:
    """
    Собрать шаблон:
      - catalog_cables_get → cables
      - Splitter.get + inventory → splitters.by_catalog_id / by_topology

    Пользователь дозаполняет ports / db_per_km.
    """
    cat = AttenuationCatalog.with_defaults()

    try:
        cables = client.Fiber.catalog_cables_get()
        items = cables.to_list() if cables else []
        cat.merge_cable_catalog(items)
    except Exception:
        pass

    try:
        splitters = client.Splitter.get()
        sp_list = splitters.to_list() if splitters else []
    except Exception:
        sp_list = []

    inventory_by_id = {}
    catalog_by_id = {}
    if cache is not None and hasattr(cache, "get_inventory"):
        for sp in sp_list:
            inv_id = getattr(sp, "inventory_id", None)
            if inv_id is None:
                continue
            inv = cache.get_inventory(client, inv_id)
            if inv is not None:
                inventory_by_id[inv_id] = inv
                cid = getattr(inv, "catalog_id", None)
                if cid is not None and hasattr(cache, "get_inventory_catalog_item"):
                    item = cache.get_inventory_catalog_item(client, cid)
                    if item is not None:
                        catalog_by_id[cid] = item
    else:
        for sp in sp_list:
            inv_id = getattr(sp, "inventory_id", None)
            if inv_id is None:
                continue
            try:
                inv_res = client.Inventory.get_inventory(id=inv_id)
                inv = inv_res[0] if inv_res and len(inv_res) > 0 else None
            except Exception:
                inv = None
            if inv is not None:
                inventory_by_id[inv_id] = inv

    cat.merge_splitter_inventory(sp_list, inventory_by_id, catalog_by_id)

    if fill_defaults:
        cat.fill_missing_with_defaults()

    if path is not None:
        cat.save(path)
    return cat
