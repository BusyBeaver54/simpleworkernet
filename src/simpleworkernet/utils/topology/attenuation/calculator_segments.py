# simpleworkernet/utils/topology/attenuation/calculator_segments.py
"""Segment helpers for Attenuation."""
from __future__ import annotations
from typing import Any, Optional, Sequence
from ..constants import TYPE_CUSTOMER, TYPE_OLT, TYPE_SPLITTER
from .length import resolve_fiber_length_m

_SPLITTER_IN_SIDE = 1
_SPLITTER_OUT_SIDE = 2

def _label_vertex(vattrs: dict) -> str:
    return (
        f"{vattrs.get('obj_type')}:{vattrs.get('obj_id')}"
        f" s{vattrs.get('side')}p{vattrs.get('port')}"
    )

class AttenuationSegmentsMixin:
    def _direction_of_path(self, vpath: Sequence[int]) -> str:
        if not vpath:
            return "unknown"
        types = [self.g.vs[i]["obj_type"] for i in vpath]
        if TYPE_OLT in types and TYPE_CUSTOMER in types:
            if types.index(TYPE_OLT) < types.index(TYPE_CUSTOMER):
                return "downstream"
            return "upstream"
        if TYPE_OLT in types:
            return "downstream" if types[0] == TYPE_OLT else "upstream"
        if TYPE_CUSTOMER in types:
            return "upstream" if types[0] == TYPE_CUSTOMER else "downstream"
        return "unknown"

    @staticmethod
    def _splitter_out_vertex(ua: dict, va: dict) -> dict:
        if (
            ua.get("obj_type") == TYPE_SPLITTER
            and va.get("obj_type") == TYPE_SPLITTER
            and str(ua.get("obj_id")) == str(va.get("obj_id"))
        ):
            us, vs_ = int(ua.get("side", 1)), int(va.get("side", 1))
            if us == _SPLITTER_OUT_SIDE and vs_ == _SPLITTER_IN_SIDE:
                return ua
            if vs_ == _SPLITTER_OUT_SIDE and us == _SPLITTER_IN_SIDE:
                return va
            if us != vs_:
                return ua if us > vs_ else va
            return ua if int(ua.get("port", 0)) >= int(va.get("port", 0)) else va
        if ua.get("obj_type") == TYPE_SPLITTER:
            return ua
        return va

    def _fiber_length(self, fiber_id, fiber_obj):
        return resolve_fiber_length_m(
            fiber_id, fiber_obj, self.client, self.cache, self.catalog
        )

    def _splitter_catalog_id(self, splitter_obj: Any) -> Optional[int]:
        if splitter_obj is None:
            return None
        inv_id = getattr(splitter_obj, "inventory_id", None)
        if inv_id is None or self.cache is None or self.client is None:
            return getattr(splitter_obj, "catalog_id", None)
        inv = self.cache.get_inventory_item(self.client, int(inv_id))
        if inv is None:
            return None
        return getattr(inv, "catalog_id", None)
