# simpleworkernet/utils/topology/attenuation/catalog_core.py
"""Core AttenuationCatalog: defaults, cables, force fiber/edge/object."""
from __future__ import annotations
import copy, json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from .catalog_helpers import _DEFAULTS_PATH, _as_db_pair, _pick_wl

class CatalogCoreMixin:
    def __init__(self, data=None):
        if data is None:
            data = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        self._data = data

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
        return copy.deepcopy(self._data)

    def save(self, path):
        Path(path).write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def merge_from_json(self, path):
        """Дополнить каталог из другого JSON (новые объекты / незаполненные поля)."""
        other = json.loads(Path(path).read_text(encoding="utf-8"))
        self._deep_merge(self._data, other)

    @staticmethod
    def _deep_merge(dst, src):
        for k, v in src.items():
            if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
                CatalogCoreMixin._deep_merge(dst[k], v)
            elif k not in dst or dst[k] in (None, {}, []):
                dst[k] = copy.deepcopy(v)
            elif isinstance(v, dict) and isinstance(dst[k], dict):
                for sk, sv in v.items():
                    if sk not in dst[k] or not dst[k][sk]:
                        dst[k][sk] = copy.deepcopy(sv)

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

    def _cables_root(self):
        cables = self._data.setdefault("cables", {})
        if "by_id" not in cables and "by_name" not in cables:
            migrated = {k: v for k, v in cables.items() if k not in ("by_id", "by_name")}
            self._data["cables"] = {"by_id": migrated, "by_name": {}}
            return self._data["cables"]
        cables.setdefault("by_id", {})
        cables.setdefault("by_name", {})
        return cables

    def set_cable(self, cabletype_id=None, *, name="", db_per_km=None):
        root = self._cables_root()
        entry = {}
        if name:
            entry["name"] = name
        if db_per_km is not None:
            norm = {}
            for k, v in db_per_km.items():
                pair = _as_db_pair(v)
                if pair:
                    norm[str(k)] = {"db": pair[0], "db_max": pair[1]}
            entry["db_per_km"] = norm
        if cabletype_id is not None:
            node = root["by_id"].setdefault(str(cabletype_id), {})
            node.update(entry)
            if name:
                root["by_name"].setdefault(name, {}).update({"cabletype_id": str(cabletype_id), **entry})
        elif name:
            root["by_name"].setdefault(name, {}).update(entry)

    def cable_db_per_km(self, cabletype_id=None, wavelength_nm=1550, *, name=None, use_max=False):
        root = self._cables_root()
        entry = None
        if cabletype_id is not None:
            entry = root.get("by_id", {}).get(str(cabletype_id))
        if entry is None and name:
            entry = root.get("by_name", {}).get(name)
        if entry and entry.get("db_per_km"):
            picked = _pick_wl(entry["db_per_km"], wavelength_nm, context=f"cable id={cabletype_id} name={name!r}")
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
