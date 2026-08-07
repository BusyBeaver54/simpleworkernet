# simpleworkernet/utils/topology/attenuation/catalog_merge.py
"""Merge cables/splitters from live API into user JSON (non-destructive)."""
from __future__ import annotations
import copy
from .catalog_helpers import guess_ratio_key
from .catalog_fill import _ports_from_ratio, _backfill_att_wl

class CatalogMergeMixin:
    def merge_cable_catalog(self, items):
        root = self._cables_root()
        default_table = self.defaults.get("fiber_db_per_km", {})
        for it in items:
            cid = getattr(it, "id", None)
            if cid is None:
                continue
            name = (
                f"{getattr(it, 'brand', '')} {getattr(it, 'model', '')}".strip()
                or getattr(it, "name", "") or str(cid)
            )
            entry = root["by_id"].setdefault(str(cid), {})
            entry.setdefault("name", name)
            entry.setdefault("fiber_count", getattr(it, "fiber_count", None))
            entry.setdefault("cable_line_type_id", getattr(it, "cable_line_type_id", None))
            if not entry.get("db_per_km"):
                entry["db_per_km"] = copy.deepcopy(default_table)
            else:
                _backfill_att_wl(entry["db_per_km"], default_table)
            if name:
                named = root["by_name"].setdefault(name, {})
                named.setdefault("cabletype_id", str(cid))
                named.setdefault("name", name)
                if not named.get("db_per_km"):
                    named["db_per_km"] = copy.deepcopy(default_table)
                else:
                    _backfill_att_wl(named["db_per_km"], default_table)

    def merge_splitter_inventory(
        self, splitters, inventory_by_id, catalog_by_id, *, auto_fill_ratio=True
    ):
        by_cat = self._data.setdefault("splitters", {}).setdefault("by_catalog_id", {})
        by_name = self._data.setdefault("splitters", {}).setdefault("by_catalog_name", {})
        by_topo = self._data.setdefault("splitters", {}).setdefault("by_topology", {})
        by_ratio = self._data.get("splitters", {}).get("by_ratio", {})
        for sp in splitters:
            sid = getattr(sp, "id", None)
            inv_id = getattr(sp, "inventory_id", None)
            pin = getattr(sp, "port_count_in", 0) or 0
            pout = getattr(sp, "port_count_out", 0) or 0
            inv = inventory_by_id.get(inv_id) if inv_id else None
            catalog_id = getattr(inv, "catalog_id", None) if inv else None
            cat_name = ""
            if catalog_id is not None and catalog_id in catalog_by_id:
                cat_name = str(getattr(catalog_by_id[catalog_id], "name", ""))
            ratio = guess_ratio_key(cat_name) if cat_name else None
            ports = _ports_from_ratio(by_ratio, ratio) if auto_fill_ratio else {}
            if catalog_id is not None:
                entry = by_cat.setdefault(str(catalog_id), {
                    "name": cat_name, "topology": f"{pin}x{pout}",
                    "ratio": ratio or "", "ports": {},
                })
                if cat_name and not entry.get("name"):
                    entry["name"] = cat_name
                if ratio and not entry.get("ratio"):
                    entry["ratio"] = ratio
                if ports and not entry.get("ports"):
                    entry["ports"] = ports
                if cat_name:
                    nentry = by_name.setdefault(cat_name, {
                        "catalog_id": str(catalog_id), "topology": f"{pin}x{pout}",
                        "ratio": ratio or "", "ports": {},
                    })
                    if ports and not nentry.get("ports"):
                        nentry["ports"] = ports
                    if ratio and not nentry.get("ratio"):
                        nentry["ratio"] = ratio
            if sid is not None:
                tentry = by_topo.setdefault(str(sid), {
                    "inventory_id": inv_id, "catalog_id": catalog_id,
                    "name": cat_name or getattr(sp, "description", ""),
                    "topology": f"{pin}x{pout}", "ratio": ratio or "", "ports": {},
                })
                if ports and not tentry.get("ports"):
                    tentry["ports"] = copy.deepcopy(ports)
