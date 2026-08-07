# simpleworkernet/utils/topology/attenuation/catalog_splitters.py
"""Splitter profiles: unified items list + by_ratio + force."""
from __future__ import annotations
from .catalog_helpers import _as_db_pair

class CatalogSplittersMixin:
    def _splitter_items(self) -> list:
        sp = self._data.setdefault("splitters", {})
        if "items" not in sp:
            self._normalize_structure()
        return sp.setdefault("items", [])

    def _find_splitter(self, *, splitter_id=None, catalog_id=None, catalog_name=None):
        for entry in self._splitter_items():
            if splitter_id is not None and str(entry.get("id")) == str(splitter_id):
                return entry
            if catalog_id is not None and str(entry.get("catalog_id")) == str(catalog_id):
                if entry.get("id") is None or splitter_id is not None:
                    return entry
            if catalog_name and str(entry.get("name") or "") == str(catalog_name):
                return entry
        if catalog_id is not None:
            for entry in self._splitter_items():
                if str(entry.get("catalog_id")) == str(catalog_id):
                    return entry
        if catalog_name:
            for entry in self._splitter_items():
                if str(entry.get("name") or "") == str(catalog_name):
                    return entry
        return None

    @staticmethod
    def _normalize_ports(ports):
        out = {}
        for k, v in ports.items():
            key = str(k)
            if isinstance(v, (int, float)):
                out[key] = {"name": key, "attenuation": {"1550": {"db": float(v), "db_max": float(v)}}}
            elif isinstance(v, dict):
                if "attenuation" in v or "name" in v:
                    att = {}
                    for wl, val in (v.get("attenuation") or {}).items():
                        pair = _as_db_pair(val)
                        if pair:
                            att[str(wl)] = {"db": pair[0], "db_max": pair[1]}
                    out[key] = {"name": v.get("name", key), "attenuation": att}
                else:
                    att = {}
                    for wl, val in v.items():
                        pair = _as_db_pair(val)
                        if pair:
                            att[str(wl)] = {"db": pair[0], "db_max": pair[1]}
                    out[key] = {"name": key, "attenuation": att}
            else:
                out[key] = v
        return out

    def set_splitter_by_catalog(self, catalog_id, *, ports, name="", ratio=""):
        entry = self._find_splitter(catalog_id=catalog_id)
        if entry is None:
            entry = {"catalog_id": str(catalog_id), "ports": {}, "ratio": ratio}
            if name:
                entry["name"] = name
            self._splitter_items().append(entry)
        entry["ports"] = self._normalize_ports(ports)
        if ratio:
            entry["ratio"] = ratio
        if name:
            entry["name"] = name

    def set_splitter_by_name(self, name, *, ports, catalog_id=None, ratio=""):
        if catalog_id is not None:
            self.set_splitter_by_catalog(catalog_id, ports=ports, name=name, ratio=ratio)
            return
        entry = self._find_splitter(catalog_name=name)
        if entry is None:
            entry = {"name": name, "ports": {}, "ratio": ratio}
            self._splitter_items().append(entry)
        entry["ports"] = self._normalize_ports(ports)
        if ratio:
            entry["ratio"] = ratio

    def set_splitter_by_ratio(self, ratio_key, *, ports):
        self._data.setdefault("splitters", {}).setdefault("by_ratio", {})[ratio_key] = {
            "ports": self._normalize_ports(ports)
        }

    def set_splitter_instance(self, splitter_id, *, ports):
        entry = self._find_splitter(splitter_id=splitter_id)
        if entry is None:
            entry = {"id": str(splitter_id), "ports": {}}
            self._splitter_items().append(entry)
        entry["ports"] = self._normalize_ports(ports)

    def force_splitter_port(self, splitter_id, port, db, *, port_name=None):
        entry = self._data.setdefault("force", {}).setdefault("splitters", {}).setdefault(str(splitter_id), {})
        val = float(db) if isinstance(db, (int, float)) else db
        entry[str(port)] = val
        if port_name:
            entry.setdefault("by_name", {})[port_name] = val

    def _resolve_port_db(self, ports, *, port, port_name, wavelength_nm, use_max, context):
        from .catalog_helpers import _pick_wl, _port_entry_attenuation
        if not ports:
            return None
        entry = None
        if port is not None and str(port) in ports:
            entry = ports[str(port)]
        elif port_name:
            for p in ports.values():
                if isinstance(p, dict) and str(p.get("name", "")).lower() == str(port_name).lower():
                    entry = p
                    break
            if entry is None and port_name in ports:
                entry = ports[port_name]
        if entry is None and "all" in ports:
            entry = ports["all"]
        if entry is None:
            return None
        if isinstance(entry, (int, float)):
            return float(entry)
        att = _port_entry_attenuation(entry)
        if att is None:
            pair = _as_db_pair(entry)
            return (pair[1] if use_max else pair[0]) if pair else None
        picked = _pick_wl(att, wavelength_nm, context=context)
        if picked is None:
            return None
        return picked[1] if use_max else picked[0]
