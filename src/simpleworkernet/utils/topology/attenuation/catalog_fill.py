# simpleworkernet/utils/topology/attenuation/catalog_fill.py
"""Backfill missing wavelengths from package ratio_defaults."""
from __future__ import annotations
import copy, json
from .catalog_helpers import guess_ratio_key, ports_from_ratio_key, _DEFAULTS_PATH

def _backfill_att_wl(dst_att, src_att) -> int:
    if not isinstance(dst_att, dict) or not isinstance(src_att, dict):
        return 0
    n = 0
    for wl, val in src_att.items():
        if wl not in dst_att or not dst_att[wl]:
            dst_att[wl] = copy.deepcopy(val)
            n += 1
    return n

class CatalogFillMixin:
    def fill_missing_wavelengths(self) -> int:
        added = 0
        default_fiber = self.defaults.get("fiber_db_per_km", {})
        pkg = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        src_fiber = (pkg.get("defaults") or {}).get("fiber_db_per_km") or {}
        _backfill_att_wl(self.defaults.setdefault("fiber_db_per_km", {}), src_fiber)
        for entry in self._cables():
            if entry.get("db_per_km"):
                added += _backfill_att_wl(entry["db_per_km"], default_fiber or src_fiber)
            else:
                entry["db_per_km"] = copy.deepcopy(default_fiber or src_fiber)
                added += len(entry["db_per_km"])
        for entry in self._splitters():
            ratio = entry.get("ratio") or ""
            if not ratio and entry.get("name"):
                ratio = guess_ratio_key(entry["name"]) or ""
            src_ports = ports_from_ratio_key(ratio) if ratio else {}
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
        default_table = self.defaults.get("fiber_db_per_km", {})
        if not default_table:
            pkg = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
            default_table = (pkg.get("defaults") or {}).get("fiber_db_per_km") or {}
            self.defaults["fiber_db_per_km"] = copy.deepcopy(default_table)
        for entry in self._cables():
            if not entry.get("db_per_km"):
                entry["db_per_km"] = copy.deepcopy(default_table)
        self.fill_missing_wavelengths()

    def unset_profiles(self):
        missing = []
        for entry in self._cables():
            if not entry.get("db_per_km"):
                missing.append(f"cable:{entry.get('id') or entry.get('name')}")
        for entry in self._splitters():
            if not entry.get("ports"):
                key = entry.get("id") or entry.get("catalog_id") or entry.get("name")
                missing.append(f"splitter:{key}")
        return missing
