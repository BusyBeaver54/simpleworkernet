# simpleworkernet/utils/topology/attenuation/catalog_core.py
"""Core AttenuationCatalog: defaults, cables, force fiber/edge/object."""
from __future__ import annotations
import copy, json
from pathlib import Path
from .catalog_helpers import _DEFAULTS_PATH, _as_db_pair, _pick_wl

class CatalogCoreMixin:
    def __init__(self, data=None):
        if data is None:
            data = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        self._data = data
        self._normalize_structure()

    def _normalize_structure(self):
        """Миграция старых by_id/by_name → списки."""
        cables = self._data.get("cables")
        if isinstance(cables, dict) and ("by_id" in cables or "by_name" in cables):
            items, seen = [], set()
            for cid, entry in (cables.get("by_id") or {}).items():
                e = dict(entry)
                e["id"] = str(cid)
                items.append(e)
                seen.add(str(cid))
            for name, entry in (cables.get("by_name") or {}).items():
                cid = str(entry.get("cabletype_id") or entry.get("id") or "")
                if cid and cid in seen:
                    continue
                e = dict(entry)
                e.setdefault("name", name)
                if cid:
                    e["id"] = cid
                items.append(e)
            self._data["cables"] = items
        elif not isinstance(self._data.get("cables"), list):
            self._data["cables"] = []

        sp = self._data.setdefault("splitters", {})
        if "items" not in sp:
            items, seen_c = [], set()
            for cid, entry in (sp.pop("by_catalog_id", None) or {}).items():
                e = dict(entry)
                e["catalog_id"] = str(cid)
                items.append(e)
                seen_c.add(str(cid))
            for name, entry in (sp.pop("by_catalog_name", None) or {}).items():
                cid = str(entry.get("catalog_id") or "")
                if cid and cid in seen_c:
                    continue
                e = dict(entry)
                e.setdefault("name", name)
                if cid:
                    e["catalog_id"] = cid
                items.append(e)
            for sid, entry in (sp.pop("by_topology", None) or {}).items():
                e = dict(entry)
                e["id"] = str(sid)
                items.append(e)
            sp["items"] = items
        sp.pop("by_ratio", None)

    @classmethod
    def with_defaults(cls):
        return cls()

    @classmethod
    def from_json(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data):
        return cls(copy.deepcopy(data))

    def to_dict(self):
        data = copy.deepcopy(self._data)
        if isinstance(data.get("splitters"), dict):
            data["splitters"].pop("ratio_defaults", None)
            data["splitters"].pop("by_ratio", None)
        return data

    def save(self, path):
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def merge_from_json(self, path):
        other = json.loads(Path(path).read_text(encoding="utf-8"))
        self._deep_merge(self._data, other)
        self._normalize_structure()

    @staticmethod
    def _deep_merge(dst, src):
        for k, v in src.items():
            if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
                CatalogCoreMixin._deep_merge(dst[k], v)
            elif k not in dst or dst[k] in (None, {}, []):
                dst[k] = copy.deepcopy(v)

    @property
    def defaults(self):
        return self._data.setdefault("defaults", {})

    def fiber_db_per_km(self, wavelength_nm, *, use_max=False):
        table = self.defaults.get("fiber_db_per_km", {})
        picked = _pick_wl(table, wavelength_nm, context="defaults.fiber_db_per_km")
        if picked is None:
            return 0.25
        return picked[1] if use_max else picked[0]

    def splice_db(self, *, use_max=False):
        pair = _as_db_pair(self.defaults.get("splice_db", 0.05))
        return (pair[1] if use_max else pair[0]) if pair else 0.05

    def connector_db(self, *, use_max=False):
        pair = _as_db_pair(self.defaults.get("connector_db", 0.3))
        return (pair[1] if use_max else pair[0]) if pair else 0.3

    def adapter_db(self, adapter_type=None, *, use_max=False):
        adapters = self._data.setdefault("cross_adapters", {})
        raw = adapters.get(adapter_type) if adapter_type else None
        if raw is None:
            raw = adapters.get("default", self.defaults.get("adapter_db", 0.2))
        pair = _as_db_pair(raw)
        return (pair[1] if use_max else pair[0]) if pair else 0.2

    def geo_slack_k(self):
        return float(self.defaults.get("geo_slack_k", 1.03))

    def splitter_excess_db(self):
        return float(self.defaults.get("splitter_excess_db", 0.5))

    def _cables(self) -> list:
        if not isinstance(self._data.get("cables"), list):
            self._normalize_structure()
        return self._data["cables"]

    def _find_cable(self, *, cabletype_id=None, name=None):
        for entry in self._cables():
            if cabletype_id is not None and str(entry.get("id")) == str(cabletype_id):
                return entry
            if name and str(entry.get("name") or "") == str(name):
                return entry
        return None

    def set_cable(self, cabletype_id=None, *, name="", db_per_km=None):
        entry = self._find_cable(cabletype_id=cabletype_id, name=name if not cabletype_id else None)
        if entry is None:
            entry = {}
            if cabletype_id is not None:
                entry["id"] = str(cabletype_id)
            if name:
                entry["name"] = name
            self._cables().append(entry)
        if name:
            entry["name"] = name
        if cabletype_id is not None:
            entry["id"] = str(cabletype_id)
        if db_per_km is not None:
            norm = {}
            for k, v in db_per_km.items():
                pair = _as_db_pair(v)
                if pair:
                    norm[str(k)] = {"db": pair[0], "db_max": pair[1]}
            entry["db_per_km"] = norm

    def cable_db_per_km(self, cabletype_id=None, wavelength_nm=1550, *, name=None, use_max=False):
        entry = self._find_cable(cabletype_id=cabletype_id, name=name)
        if entry and entry.get("db_per_km"):
            picked = _pick_wl(
                entry["db_per_km"], wavelength_nm,
                context=f"cable id={cabletype_id} name={name!r}",
            )
            if picked is not None:
                return picked[1] if use_max else picked[0]
        return self.fiber_db_per_km(wavelength_nm, use_max=use_max)

    def force_fiber(self, fiber_id, db_per_km):
        node = self._data.setdefault("force", {}).setdefault("fibers", {})
        if isinstance(db_per_km, (int, float)):
            node[str(fiber_id)] = float(db_per_km)
            return
        norm = {}
        for k, v in db_per_km.items():
            pair = _as_db_pair(v)
            if pair:
                norm[str(k)] = {"db": pair[0], "db_max": pair[1]}
        node[str(fiber_id)] = norm

    def forced_fiber_db_per_km(self, fiber_id, wavelength_nm=1550, *, use_max=False):
        raw = self._data.get("force", {}).get("fibers", {}).get(str(fiber_id))
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, dict):
            picked = _pick_wl(raw, wavelength_nm, context=f"force fiber:{fiber_id}")
            if picked is None:
                return None
            return picked[1] if use_max else picked[0]
        return None

    def force_object(self, obj_type, obj_id, db):
        self._data.setdefault("force", {}).setdefault("objects", {})[f"{obj_type}:{obj_id}"] = float(db)

    def forced_object_db(self, obj_type, obj_id):
        v = self._data.get("force", {}).get("objects", {}).get(f"{obj_type}:{obj_id}")
        return float(v) if v is not None else None

    def force_edge(self, connect_id, db):
        self._data.setdefault("force", {}).setdefault("edges", {})[str(connect_id)] = float(db)

    def forced_edge_db(self, connect_id):
        v = self._data.get("force", {}).get("edges", {}).get(str(connect_id))
        return float(v) if v is not None else None

    def force_cross(self, cross_id, db):
        self._data.setdefault("force", {}).setdefault("crosses", {})[str(cross_id)] = float(db)

    def forced_cross_db(self, cross_id):
        v = self._data.get("force", {}).get("crosses", {}).get(str(cross_id))
        return float(v) if v is not None else None
