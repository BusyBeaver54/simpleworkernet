# simpleworkernet/utils/topology/attenuation/calculator_segments.py
"""Segment helpers for Attenuation."""
from __future__ import annotations
import re
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

_IFACE_RE = re.compile(
    r"^(?:Interface\(|ObjKey\(|"
    r"(?:fiber|splitter|olt|customer|cross|switch|onu|radio|node|cwdm):)",
    re.I,
)


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


def _looks_like_iface_label(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    if not s:
        return True
    if s.startswith("Interface(") or s.startswith("ObjKey("):
        return True
    if " side=" in s and " port=" in s:
        return True
    if _IFACE_RE.match(s):
        return True
    return False


def _obj_display_name(vattrs: dict) -> Optional[str]:
    if not vattrs:
        return None
    obj = vattrs.get("api_obj")
    oid = str(vattrs.get("obj_id") or "")
    name = _attr(
        obj,
        "name", "title", "label", "caption",
        "fio", "full_name", "customer_name", "device_name",
        "username", "login",  # fallback для customer из get_user_list
    )
    if name is not None:
        s = str(name).strip()
        if s and not _looks_like_iface_label(s) and s != oid:
            return s
    for key in ("obj_name", "title", "label", "display_name"):
        v = vattrs.get(key)
        if v is not None and not _looks_like_iface_label(v):
            s = str(v).strip()
            if s and s != oid:
                return s
    return None


def _olt_host(vattrs: dict) -> Optional[str]:
    """Host/IP оборудования (olt, switch, onu, radio)."""
    obj = vattrs.get("api_obj") if vattrs else None
    host = _attr(
        obj,
        "host", "hostname", "ip", "ip_address", "mgmt_ip",
        "address", "host_name", "ipaddr",
    )
    if host not in (None, ""):
        return str(host)
    if obj is not None:
        nested = _attr(obj, "device", "info", "net", "network")
        host = _attr(nested, "host", "hostname", "ip", "ip_address")
        if host not in (None, ""):
            return str(host)
    return None


def _cable_name(vattrs: dict) -> Optional[str]:
    if not vattrs:
        return None
    oid = str(vattrs.get("obj_id") or "")
    for key in ("cable_name", "cable_title", "fiber_name"):
        v = vattrs.get(key)
        if v not in (None, "") and str(v) != oid and not _looks_like_iface_label(v):
            return str(v)
    obj = vattrs.get("api_obj")
    for key in (
        "cable_name", "cabletype_name", "cable_type_name",
        "type_name", "cabletypename", "cable_mark", "marking",
    ):
        v = _attr(obj, key)
        if v not in (None, "") and str(v) != oid and not str(v).isdigit():
            s = str(v).strip()
            if s and not _looks_like_iface_label(s):
                return s
    ct = _attr(obj, "cable_type", "cabletype", "cableType", "type")
    if ct is not None:
        if isinstance(ct, str) and ct.strip() and ct != oid and not ct.isdigit():
            return ct.strip()
        n = _attr(ct, "name", "title", "mark", "model", "brand", "code")
        if n not in (None, "") and str(n) != oid and not str(n).isdigit():
            return str(n)
    # Fiber.Get_list: cablecode часто числовой id типа — не имя
    for key in ("mark", "name", "title", "model", "brand"):
        v = _attr(obj, key)
        if v in (None, ""):
            continue
        s = str(v).strip()
        if not s or s == oid or s.isdigit():
            continue
        if _looks_like_iface_label(s):
            continue
        return s
    return None


def _label_vertex(vattrs: dict) -> str:
    ot = vattrs.get("obj_type")
    oid = vattrs.get("obj_id")
    base = f"{ot}:{oid} s{vattrs.get('side')}p{vattrs.get('port')}"
    name = _obj_display_name(vattrs)
    _dev = {TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO}
    host = _olt_host(vattrs) if ot in _dev else None
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
    def _vertex_attrs(self, index: int) -> dict:
        if self.g is None:
            return {}
        try:
            return dict(self.g.vs[int(index)].attributes())
        except Exception:
            try:
                v = self.g.vs[int(index)]
                return {k: v[k] for k in v.attributes()}
            except Exception:
                return {}

    def _ensure_api_obj(self, vattrs: dict) -> dict:
        """Подтянуть api_obj из cache/client, если в вершине его нет.

        Customer при построении CGraph намеренно не грузится (скорость BFS).
        Для отчёта затуханий имя/host всё же нужны — подгружаем лениво.
        """
        if not vattrs:
            return vattrs
        if vattrs.get("api_obj") is not None:
            return vattrs
        ot = str(vattrs.get("obj_type") or "")
        oid = vattrs.get("obj_id")
        if not ot or oid is None or oid == "":
            return vattrs
        cache = getattr(self, "cache", None)
        client = getattr(self, "client", None)
        obj = None
        # 1) уже в кэше (preload / предыдущие запросы)
        if cache is not None:
            try:
                obj = cache.get_object(ot, oid)
            except Exception:
                obj = None
        # 2) точечная загрузка через cache helpers
        if obj is None and cache is not None and client is not None:
            try:
                if ot == TYPE_CUSTOMER and hasattr(cache, "get_customer"):
                    obj = cache.get_customer(client, int(oid))
                elif ot == TYPE_FIBER and hasattr(cache, "get_fiber"):
                    obj = cache.get_fiber(client, int(oid))
                elif ot == TYPE_SPLITTER and hasattr(cache, "get_splitter"):
                    obj = cache.get_splitter(client, int(oid))
                elif ot in (TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO) and hasattr(cache, "get_device"):
                    obj = cache.get_device(client, ot, int(oid))
                elif ot == TYPE_CROSS and hasattr(cache, "get_cross"):
                    obj = cache.get_cross(client, str(oid))
            except Exception:
                obj = None
        if obj is not None:
            vattrs = dict(vattrs)
            vattrs["api_obj"] = obj
        return vattrs

    def _fiber_length_m(self, fiber_id) -> Tuple[Optional[float], str]:
        fid = int(fiber_id)
        if self.cache is not None:
            for name in ("get_fiber_length_m", "get_fiber_length"):
                fn = getattr(self.cache, name, None)
                if not callable(fn):
                    continue
                try:
                    r = fn(fid)
                    if r is None:
                        continue
                    if isinstance(r, (tuple, list)) and len(r) >= 2:
                        return r[0], str(r[1])
                    if isinstance(r, (int, float)):
                        return float(r), "cache"
                except Exception:
                    pass
        fiber = None
        if hasattr(self, "_load_fiber"):
            try:
                fiber = self._load_fiber(fid)
            except Exception:
                fiber = None
        return self._fiber_length(fid, fiber)

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
        if inv_id is None and isinstance(splitter_obj, dict):
            inv_id = splitter_obj.get("inventory_id")
        if inv_id is None or self.cache is None or self.client is None:
            cid = getattr(splitter_obj, "catalog_id", None)
            if cid is None and isinstance(splitter_obj, dict):
                cid = splitter_obj.get("catalog_id")
            return cid
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
            cid = getattr(splitter_obj, "catalog_id", None)
            if cid is None and isinstance(splitter_obj, dict):
                cid = splitter_obj.get("catalog_id")
            return cid
        return getattr(inv, "catalog_id", None) if not isinstance(inv, dict) else inv.get("catalog_id")

    def _resolve_cable_name(self, fiber_vertex_attrs: dict) -> Optional[str]:
        fiber_vertex_attrs = self._ensure_api_obj(fiber_vertex_attrs)
        name = _cable_name(fiber_vertex_attrs)
        if name:
            return name
        fid = fiber_vertex_attrs.get("obj_id")
        if fid is None or self.client is None:
            return None
        fiber = fiber_vertex_attrs.get("api_obj")
        if fiber is None and hasattr(self, "_load_fiber"):
            try:
                fiber = self._load_fiber(int(fid))
            except Exception:
                fiber = None
        if fiber is None and self.cache is not None:
            try:
                fiber = self.cache.get_fiber(self.client, int(fid))
            except Exception:
                fiber = None
        # попытка через каталог кабелей по cablecode / cabletype_id
        if fiber is not None:
            name = _cable_name({"api_obj": fiber, "obj_id": fid})
            if name:
                return name
            try:
                cat = self.cache.get_cable_catalog(self.client) if self.cache else []
            except Exception:
                cat = []
            code = _attr(fiber, "cablecode", "cable_code", "cabletype_id", "cable_type_id")
            if code is not None and cat:
                for item in cat:
                    iid = _attr(item, "id", "code")
                    if iid is not None and str(iid) == str(code):
                        n = _attr(item, "name", "model", "brand", "title")
                        if n and not str(n).isdigit():
                            return str(n)
        return _cable_name({"api_obj": fiber, "obj_id": fid}) if fiber is not None else None

    def _resolve_splitter_name(self, splitter_vertex_attrs: dict) -> Optional[str]:
        splitter_vertex_attrs = self._ensure_api_obj(splitter_vertex_attrs)
        name = _obj_display_name(splitter_vertex_attrs)
        if name:
            return name
        obj = splitter_vertex_attrs.get("api_obj")
        if obj is None:
            return None
        inv_id = _attr(obj, "inventory_id")
        if inv_id is not None and self.cache is not None and self.client is not None:
            inv = None
            for mname in ("get_inventory_item", "get_inventory"):
                fn = getattr(self.cache, mname, None)
                if callable(fn):
                    try:
                        inv = fn(self.client, int(inv_id))
                        break
                    except Exception:
                        pass
            if inv is not None:
                n = _attr(inv, "name", "title", "label", "mark")
                if n and not _looks_like_iface_label(n):
                    return str(n)
        return None
