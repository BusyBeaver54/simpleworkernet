# simpleworkernet/utils/topology/attenuation/calculator_core.py
"""Attenuation mixins — segments, path, edge, build, fiber, graph (единый модуль)."""
from __future__ import annotations

import re
from typing import Any, Optional, Sequence, Tuple
from ..constants import (
    TYPE_CUSTOMER, TYPE_OLT, TYPE_ONU, TYPE_RADIO, TYPE_SPLITTER, TYPE_SWITCH,
    TYPE_FIBER, TYPE_CROSS,
)
from .length import resolve_fiber_length_m
from . import splitter_load
from typing import Any, List, Optional
from ..constants import TYPE_FIBER
from .models import AttenuationSegment
from ..constants import (
    TYPE_CUSTOMER, TYPE_FIBER, TYPE_OLT, TYPE_SPLITTER,
    TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
)
from .models import AttenuationSegment, EndpointInfo, PathReport
from typing import List, Optional, Set
from ..constants import (
    TYPE_CROSS, TYPE_CUSTOMER, TYPE_FIBER, TYPE_OLT, TYPE_ONU,
    TYPE_RADIO, TYPE_SPLITTER, TYPE_SWITCH,
)
from typing import Any, Optional, Union
from .errors import AttenuationError
from typing import Any, Set
from typing import Any, List, Optional, Set
from typing import List, Optional
from ..paths import simple_paths, shortest_simple_path
from ..constants import TYPE_OLT, TYPE_ONU, TYPE_RADIO, TYPE_SWITCH
from typing import Any, List, Optional, Union
from .models import PathReport

# === calculator_segments.py ===
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
        "username", "login",
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


def _cable_name(vattrs: dict, catalog=None) -> Optional[str]:
    """Марка кабеля: vattrs → cablecode → catalog model → поля api_obj."""
    if not vattrs:
        return None
    oid = str(vattrs.get("obj_id") or "")
    for key in ("cable_name", "cable_title", "fiber_name"):
        v = vattrs.get(key)
        if v not in (None, "") and str(v) != oid and not _looks_like_iface_label(v):
            return str(v)

    obj = vattrs.get("api_obj")

    # cablecode на линии = id записи в Fiber.catalog_cables_get(); марка = model
    cablecode = _attr(obj, "cablecode", "cable_code", "cabletype_id", "cable_type_id")
    if cablecode is not None and str(cablecode).strip() and str(cablecode) != "0":
        code = str(cablecode).strip()
        if catalog is not None and hasattr(catalog, "_find_cable"):
            try:
                entry = catalog._find_cable(cabletype_id=code)
            except Exception:
                entry = None
            if entry:
                n = entry.get("name")  # merge_cable_catalog: name = model
                if n not in (None, "") and str(n).strip():
                    return str(n).strip()

    for key in (
        "cable_name", "cabletype_name", "cable_type_name",
        "type_name", "cabletypename", "cable_mark", "marking", "model",
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
        """api_obj + catalog_id/name (splitter: Inventory); customer без API."""
        return splitter_load.ensure_api_obj(self, vattrs)

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
        """catalog_id с api_obj (редко) или None — обычно из vattrs после ensure."""
        return splitter_load.extract_catalog_id(splitter_obj)

    def _resolve_cable_name(self, fiber_vertex_attrs: dict) -> Optional[str]:
        """Марка по cablecode → catalog_cables model (или attenuation catalog)."""
        fiber_vertex_attrs = self._ensure_api_obj(fiber_vertex_attrs)
        cat = getattr(self, "catalog", None)
        name = _cable_name(fiber_vertex_attrs, catalog=cat)
        if name:
            return name

        obj = fiber_vertex_attrs.get("api_obj")
        cablecode = _attr(obj, "cablecode", "cable_code", "cabletype_id", "cable_type_id")
        if cablecode is None or not str(cablecode).strip() or str(cablecode) == "0":
            return None
        code = str(cablecode).strip()

        client = getattr(self, "client", None)
        if client is None:
            return None
        try:
            items = client.Fiber.catalog_cables_get()
            if items is not None and hasattr(items, "to_list") and callable(items.to_list):
                items = items.to_list()
            items = items or []
            for it in items:
                if isinstance(it, dict):
                    iid = it.get("id")
                    model = it.get("model") or it.get("name")
                else:
                    iid = getattr(it, "id", None)
                    model = getattr(it, "model", None) or getattr(it, "name", None)
                if iid is not None and str(iid) == code:
                    if model not in (None, "") and str(model).strip():
                        return str(model).strip()
        except Exception:
            pass
        return None

    def _resolve_splitter_name(self, splitter_vertex_attrs: dict) -> Optional[str]:
        splitter_vertex_attrs = self._ensure_api_obj(splitter_vertex_attrs)
        return _obj_display_name(splitter_vertex_attrs)
