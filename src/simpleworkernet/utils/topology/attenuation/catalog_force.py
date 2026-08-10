# simpleworkernet/utils/topology/attenuation/catalog_force.py
"""Force overrides for fiber/cross/object/edge."""
from __future__ import annotations
from .catalog_helpers import _as_db_pair, _pick_wl

class CatalogForceMixin:
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
