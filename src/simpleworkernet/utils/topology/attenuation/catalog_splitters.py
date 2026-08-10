# simpleworkernet/utils/topology/attenuation/catalog_splitters.py
"""Splitter entries in AttenuationCatalog."""
from __future__ import annotations
from typing import Any, Optional


class CatalogSplittersMixin:
    def _splitter_items(self) -> list:
        return self._splitters()

    def _find_splitter(
        self, *,
        splitter_id=None, catalog_id=None, catalog_name=None,
    ) -> Optional[dict]:
        items = self._splitters()

        # name — case-insensitive, strip
        if catalog_name:
            cn = str(catalog_name).strip().lower()
            for entry in items:
                en = str(entry.get("name") or "").strip().lower()
                if en and en == cn:
                    return entry

        if splitter_id is not None:
            sid = str(splitter_id)
            for entry in items:
                if str(entry.get("id") or "") == sid:
                    return entry

        if catalog_id is not None:
            cid = str(catalog_id)
            # предпочтительно запись без instance id (каталожная)
            fallback = None
            for entry in items:
                if str(entry.get("catalog_id") or "") != cid:
                    continue
                if entry.get("id") is None:
                    return entry
                if fallback is None:
                    fallback = entry
            if fallback is not None:
                return fallback

        return None

    def _normalize_ports(self, ports) -> dict:
        if not ports:
            return {}
        if not isinstance(ports, dict):
            return {}
        out = {}
        for k, v in ports.items():
            key = str(k)
            if isinstance(v, (int, float)):
                out[key] = float(v)
            elif isinstance(v, dict):
                out[key] = dict(v)
            else:
                out[key] = v
        return out

    def set_splitter_by_catalog(self, catalog_id, *, ports, name="", ratio=""):
        entry = self._find_splitter(catalog_id=catalog_id)
        if entry is None:
            entry = {"catalog_id": str(catalog_id), "ports": {}}
            self._splitters().append(entry)
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
            self._splitters().append(entry)
        entry["ports"] = self._normalize_ports(ports)
        if ratio:
            entry["ratio"] = ratio
        if name:
            entry["name"] = name

    def set_splitter_instance(self, splitter_id, *, ports):
        entry = self._find_splitter(splitter_id=splitter_id)
        if entry is None:
            entry = {"id": str(splitter_id), "ports": {}}
            self._splitters().append(entry)
        entry["ports"] = self._normalize_ports(ports)

    def force_splitter_port(self, splitter_id, port, db, *, port_name=None):
        entry = (
            self._data.setdefault("force", {})
            .setdefault("splitters", {})
            .setdefault(str(splitter_id), {})
        )
        val = float(db) if isinstance(db, (int, float)) else db
        entry[str(port)] = val
        if port_name:
            entry.setdefault("by_name", {})[port_name] = val
