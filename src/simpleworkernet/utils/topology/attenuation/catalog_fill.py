# simpleworkernet/utils/topology/attenuation/catalog_fill.py
"""Backfill missing wavelengths / ratio defaults into user catalog."""
from __future__ import annotations
import copy, json
from .catalog_helpers import _DEFAULTS_PATH, guess_ratio_key

def _backfill_att_wl(dst_att, src_att) -> int:
    if not isinstance(dst_att, dict) or not isinstance(src_att, dict):
        return 0
    n = 0
    for wl, val in src_att.items():
        if wl not in dst_att or not dst_att[wl]:
            dst_att[wl] = copy.deepcopy(val)
            n += 1
    return n

def _ports_from_ratio(by_ratio, ratio):
    if not ratio or ratio not in by_ratio:
        return {}
    r = by_ratio[ratio]
    if r.get("ports"):
        return copy.deepcopy(r["ports"])
    if r.get("equal_db"):
        return {"all": {"name": "equal", "attenuation": copy.deepcopy(r["equal_db"])}}
    return {}

class CatalogFillMixin:
    def sync_ratio_defaults(self) -> int:
        pkg = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        src_ratio = (pkg.get("splitters") or {}).get("by_ratio") or {}
        dst_ratio = self._data.setdefault("splitters", {}).setdefault("by_ratio", {})
        added = 0
        for key, src in src_ratio.items():
            if key not in dst_ratio:
                dst_ratio[key] = copy.deepcopy(src)
                added += 1
                continue
            dst_ports = dst_ratio[key].setdefault("ports", {})
            for pk, pv in (src.get("ports") or {}).items():
                if pk not in dst_ports:
                    dst_ports[pk] = copy.deepcopy(pv)
                    added += 1
                    continue
                if isinstance(pv, dict) and isinstance(dst_ports[pk], dict):
                    added += _backfill_att_wl(
                        dst_ports[pk].setdefault("attenuation", {}),
                        pv.get("attenuation") or {},
                    )
        src_fiber = (pkg.get("defaults") or {}).get("fiber_db_per_km") or {}
        added += _backfill_att_wl(self.defaults.setdefault("fiber_db_per_km", {}), src_fiber)
        return added

    def fill_missing_wavelengths(self) -> int:
        added = 0
        by_ratio = self._data.get("splitters", {}).get("by_ratio", {})
        default_fiber = self.defaults.get("fiber_db_per_km", {})
        for entry in self._cables():
            if entry.get("db_per_km"):
                added += _backfill_att_wl(entry["db_per_km"], default_fiber)
            else:
                entry["db_per_km"] = copy.deepcopy(default_fiber)
                added += len(default_fiber)
        for entry in self._splitter_items():
            ratio = entry.get("ratio") or ""
            if not ratio and entry.get("name"):
                ratio = guess_ratio_key(entry["name"]) or ""
            src_ports = _ports_from_ratio(by_ratio, ratio) if ratio else {}
            ports = entry.setdefault("ports", {})
            if not ports and src_ports:
                entry["ports"] = copy.deepcopy(src_ports)
                added += sum(len((p.get("attenuation") or {})) for p in src_ports.values() if isinstance(p, dict))
                continue
            for pk, pv in list(ports.items()):
                if not isinstance(pv, dict):
                    continue
                att = pv.setdefault("attenuation", {})
                src = None
                if pk in src_ports and isinstance(src_ports[pk], dict):
                    src = src_ports[pk].get("attenuation")
                elif "all" in src_ports:
                    src = (src_ports["all"] or {}).get("attenuation")
                if src:
                    added += _backfill_att_wl(att, src)
        return added

    def fill_missing_with_defaults(self):
        self.sync_ratio_defaults()
        default_table = self.defaults.get("fiber_db_per_km", {})
        for entry in self._cables():
            if not entry.get("db_per_km"):
                entry["db_per_km"] = copy.deepcopy(default_table)
        self.fill_missing_wavelengths()

    def unset_profiles(self):
        missing = []
        for entry in self._cables():
            if not entry.get("db_per_km"):
                missing.append(f"cable:{entry.get('id') or entry.get('name')}")
        for entry in self._splitter_items():
            if not entry.get("ports"):
                key = entry.get("id") or entry.get("catalog_id") or entry.get("name")
                missing.append(f"splitter:{key}")
        return missing
