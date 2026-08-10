# simpleworkernet/utils/topology/attenuation/calculator_segments.py
"""Segment helpers for Attenuation."""
from __future__ import annotations
from typing import Any, Optional, Sequence, Tuple
from ..constants import (
    TYPE_CUSTOMER, TYPE_OLT, TYPE_ONU, TYPE_RADIO, TYPE_SPLITTER, TYPE_SWITCH,
    TYPE_FIBER, TYPE_CROSS,
)
from .length import resolve_fiber_length_m

_SPLITTER_IN_SIDE = 1
_SPLITTER_OUT_SIDE = 2

_DEVICE_TYPES = frozenset({
    TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO, TYPE_CUSTOMER,
})


def _attr(obj, *names, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        return default
    for n in names:
        v = getattr(obj, n, None)
        if v not in (None, ""):
            return v
    return default


def _obj_display_name(vattrs: dict) -> Optional[str]:
    """Человекочитаемое имя объекта из вершины / api_obj."""
    if not vattrs:
        return None
    for key in ("obj_name", "name", "title", "label"):
        v = vattrs.get(key)
        if v not in (None, ""):
            s = str(v)
            # Interface(...) — не имя
            if not s.startswith("Interface(") and not s.startswith("ObjKey("):
                return s
    obj = vattrs.get("api_obj")
    name = _attr(obj, "name", "title", "label", "code", "mark")
    if name:
        return str(name)
    return None


def _olt_host(vattrs: dict) -> Optional[str]:
    obj = vattrs.get("api_obj") if vattrs else None
    host = _attr(
        obj,
        "host", "hostname", "ip", "ip_address", "mgmt_ip", "address",
        "host_name",
    )
    if host:
        return str(host)
    # иногда host вложен
    if obj is not None:
        nested = _attr(obj, "device", "info", "net")
        host = _attr(nested, "host", "hostname", "ip")
        if host:
            return str(host)
    return None


def _cable_name(vattrs: dict) -> Optional[str]:
    if not vattrs:
        return None
    for key in ("cable_name", "cable_title", "fiber_name"):
        v = vattrs.get(key)
        if v not in (None, ""):
            return str(v)
    obj = vattrs.get("api_obj")
    name = _attr(obj, "name", "title", "code", "mark", "cable_name")
    if name:
        return str(name)
    # тип кабеля
    ctype = _attr(obj, "cable_type", "cabletype", "type_name")
    if ctype:
        return str(ctype)
    return None


def _label_vertex(vattrs: dict) -> str:
    ot = vattrs.get("obj_type")
    oid = vattrs.get("obj_id")
    base = f"{ot}:{oid} s{vattrs.get('side')}p{vattrs.get('port')}"
    name = _obj_display_name(vattrs)
    host = _olt_host(vattrs) if ot == TYPE_OLT else None
    cable = _cable_name(vattrs) if ot == TYPE_FIBER else None
    extras = []
    if name and ot != TYPE_FIBER:
        extras.append(name)
    if cable:
        extras.append(cable)
    if host:
        extras.append(f"host={host}")
    if extras:
        return f"{base} ({', '.join(extras)})"
    return base


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

    def _fiber_length(self, fiber_id, fiber_obj) -> Tuple[Optional[float], str]:
        slack = 1.03
        try:
            slack = float(self.catalog.geo_slack_k())
        except Exception:
            pass
        return resolve_fiber_length_m(fiber_obj, slack_k=slack)

    def _splitter_catalog_id(self, splitter_obj: Any) -> Optional[int]:
        if splitter_obj is None:
            return None
        inv_id = getattr(splitter_obj, "inventory_id", None)
        if inv_id is None or self.cache is None or self.client is None:
            return getattr(splitter_obj, "catalog_id", None)
        inv = None
        for name in ("get_inventory_item", "get_inventory"):
            fn = getattr(self.cache, name, None)
            if callable(fn):
                try:
                    inv = fn(self.client, int(inv_id))
                    break
                except Exception:
                    pass
        if inv is None:
            return getattr(splitter_obj, "catalog_id", None)
        return getattr(inv, "catalog_id", None)

    def _resolve_cable_name(self, fiber_vertex_attrs: dict) -> Optional[str]:
        name = _cable_name(fiber_vertex_attrs)
        if name:
            return name
        # из кэша/API
        fid = fiber_vertex_attrs.get("obj_id")
        if fid is None or self.client is None:
            return None
        fiber = fiber_vertex_attrs.get("api_obj")
        if fiber is None and hasattr(self, "_load_fiber"):
            try:
                fiber = self._load_fiber(int(fid))
            except Exception:
                fiber = None
        return _cable_name({"api_obj": fiber}) if fiber is not None else None
