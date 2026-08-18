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


def _cablecode_from_obj(obj) -> Optional[str]:
    """cablecode линии = id записи в Fiber.catalog_cables_get()."""
    code = _attr(obj, "cablecode", "cable_code", "cabletype_id", "cable_type_id")
    if code is None:
        return None
    s = str(code).strip()
    if not s or s in ("0", "None"):
        return None
    return s


def _cable_name(vattrs: dict, catalog=None) -> Optional[str]:
    """Марка кабеля: vattrs → cablecode→catalog.model → поля api_obj."""
    if not vattrs:
        return None
    oid = str(vattrs.get("obj_id") or "")
    for key in ("cable_name", "cable_title", "fiber_name"):
        v = vattrs.get(key)
        if v not in (None, "") and str(v) != oid and not _looks_like_iface_label(v):
            return str(v)

    obj = vattrs.get("api_obj")
    code = _cablecode_from_obj(obj)

    # 1) AttenuationCatalog: id = cablecode, name = model (марка)
    if code and catalog is not None and hasattr(catalog, "_find_cable"):
        try:
            entry = catalog._find_cable(cabletype_id=code)
        except Exception:
            entry = None
        if entry:
            n = entry.get("name")
            if n not in (None, "") and str(n).strip():
                return str(n).strip()

    # 2) прямые поля api_obj
    for key in (
        "cable_name", "cabletype_name", "cable_type_name",
        "type_name", "cabletypename", "cable_mark", "marking",
        "model",
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
        """Марка кабеля: cablecode → catalog_cables_get().model / attenuation catalog."""
        fiber_vertex_attrs = self._ensure_api_obj(fiber_vertex_attrs)
        cat = getattr(self, "catalog", None)
        name = _cable_name(fiber_vertex_attrs, catalog=cat)
        if name:
            return name

        obj = fiber_vertex_attrs.get("api_obj")
        code = _cablecode_from_obj(obj)
        if not code:
            return None

        client = getattr(self, "client", None)
        if client is None:
            return None
        try:
            items = client.Fiber.catalog_cables_get()
            if items is None:
                return None
            if hasattr(items, "to_list") and callable(items.to_list):
                items = items.to_list()
            elif not isinstance(items, (list, tuple)):
                items = [items]
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

# === calculator_path_fiber.py ===
class AttenuationPathFiberMixin:
    def _fiber_core_info(self, fiber_vertex_attrs: dict) -> dict:
        raw_port = fiber_vertex_attrs.get("port")
        try:
            raw_port_i = int(raw_port) if raw_port is not None else None
        except (TypeError, ValueError):
            raw_port_i = None

        obj = fiber_vertex_attrs.get("api_obj")
        fibers = None
        if obj is not None:
            fibers = (
                getattr(obj, "fibers", None)
                if not isinstance(obj, dict)
                else obj.get("fibers")
            )
        if not fibers and getattr(self, "client", None) is not None:
            fid = fiber_vertex_attrs.get("obj_id")
            try:
                result = None
                if hasattr(self, "cache") and self.cache is not None:
                    try:
                        cached = self.cache.get_fiber(self.client, int(fid))
                        if cached is not None:
                            result = cached
                    except Exception:
                        pass
                if result is None:
                    result = self.client.Fiber.get_list(object_id=int(fid))
                    if result is not None:
                        if hasattr(result, "to_list") and callable(result.to_list):
                            items = result.to_list()
                            result = items[0] if items else None
                        elif isinstance(result, (list, tuple)):
                            result = result[0] if result else None
                if result is not None:
                    fibers = (
                        getattr(result, "fibers", None)
                        if not isinstance(result, dict)
                        else result.get("fibers")
                    )
                    if fibers and obj is None:
                        fiber_vertex_attrs = dict(fiber_vertex_attrs)
                        fiber_vertex_attrs["api_obj"] = result
            except Exception:
                fibers = None

        core_id = None
        number = None
        module_number = None
        fiber_color = None
        module_color = None
        matched = None

        def _f_attr(f, *names, default=None):
            if f is None:
                return default
            if isinstance(f, dict):
                for n in names:
                    if n in f and f[n] not in (None, ""):
                        return f[n]
                return default
            for n in names:
                v = getattr(f, n, None)
                if v not in (None, ""):
                    return v
            return default

        def _color_obj_name(color) -> Optional[str]:
            if color is None:
                return None
            if isinstance(color, str):
                s = color.strip()
                return s or None
            name = _f_attr(color, "name", "Name")
            if name not in (None, ""):
                return str(name).strip() or None
            return None

        def _fiber_color_name(f) -> Optional[str]:
            return _color_obj_name(_f_attr(f, "color", "Color"))

        def _module_color_name(f) -> Optional[str]:
            return _color_obj_name(_f_attr(f, "moduleColor", "module_color", "ModuleColor"))

        if fibers and raw_port_i is not None:
            for f in fibers:
                fid = _f_attr(f, "id")
                try:
                    if fid is not None and int(fid) == raw_port_i:
                        matched = f
                        break
                except (TypeError, ValueError):
                    continue
            if matched is None:
                for f in fibers:
                    num = _f_attr(f, "number", "port")
                    try:
                        if num is not None and int(num) == raw_port_i:
                            matched = f
                            break
                    except (TypeError, ValueError):
                        continue

        if matched is not None:
            try:
                core_id = int(_f_attr(matched, "id")) if _f_attr(matched, "id") is not None else None
            except (TypeError, ValueError):
                core_id = None
            try:
                number = int(_f_attr(matched, "number", "port")) if _f_attr(matched, "number", "port") is not None else None
            except (TypeError, ValueError):
                number = None
            module_number = self._fiber_module_index(matched, fibers)
            fiber_color = _fiber_color_name(matched)
            module_color = _module_color_name(matched)
        elif raw_port_i is not None:
            if raw_port_i < 10000:
                number = raw_port_i
            else:
                core_id = raw_port_i

        mf_path = None
        if number is not None and module_number is not None:
            mf_path = f"m{module_number}f{number}"
        elif number is not None:
            mf_path = f"f{number}"

        port_name = fiber_color
        if not port_name and mf_path:
            port_name = mf_path

        return {
            "fiber_number": number,
            "fiber_core_id": core_id,
            "module_number": module_number,
            "fiber_color": fiber_color,
            "module_color": module_color,
            "mf_path": mf_path,
            "port_name": port_name,
            "port": number if number is not None else raw_port_i,
        }

    def _fiber_module_index(self, fiber, fibers) -> Optional[int]:
        if fiber is None or not fibers:
            return None

        def _key(f):
            if isinstance(f, dict):
                mc = f.get("moduleColor") or f.get("module_color")
                mid = f.get("module_color_id") or f.get("module_id")
            else:
                mc = getattr(f, "moduleColor", None) or getattr(f, "module_color", None)
                mid = getattr(f, "module_color_id", None) or getattr(f, "module_id", None)
            if mid not in (None, ""):
                return ("id", str(mid))
            if mc is not None:
                if isinstance(mc, dict):
                    code = mc.get("htmlCode") or mc.get("name") or mc.get("tag_color")
                else:
                    code = (
                        getattr(mc, "htmlCode", None)
                        or getattr(mc, "name", None)
                        or getattr(mc, "tag_color", None)
                    )
                if code not in (None, ""):
                    return ("color", str(code))
            return None

        order = []
        seen = set()
        for f in fibers:
            k = _key(f)
            if k is None or k in seen:
                continue
            seen.add(k)
            order.append(k)
        fk = _key(fiber)
        if fk is None or fk not in order:
            return 1 if order else None
        return order.index(fk) + 1

    def _fiber_segments(self, fiber_vertex_attrs: dict) -> List[AttenuationSegment]:
        fiber_vertex_attrs = self._ensure_api_obj(fiber_vertex_attrs)
        fiber_id = fiber_vertex_attrs.get("obj_id")
        length_m = fiber_vertex_attrs.get("length_m")
        length_source = fiber_vertex_attrs.get("length_source") or None
        cable_name = None
        if hasattr(self, "_resolve_cable_name"):
            cable_name = self._resolve_cable_name(fiber_vertex_attrs)
        if not cable_name:
            cable_name = _cable_name(
                fiber_vertex_attrs, catalog=getattr(self, "catalog", None)
            )
        if length_m is None:
            try:
                length_m, length_source = self._fiber_length_m(fiber_id)
            except Exception:
                try:
                    length_m, length_source = self._fiber_length(
                        fiber_id, fiber_vertex_attrs.get("api_obj")
                    )
                except Exception:
                    length_m, length_source = None, "missing"
        if not length_source:
            length_source = "unknown"
        try:
            if cable_name and hasattr(self.catalog, "cable_db_triple"):
                db_min_km, db_km, db_max_km = self.catalog.cable_db_triple(
                    name=cable_name, wavelength_nm=self.wavelength,
                )
                src = "cable"
            elif hasattr(self.catalog, "fiber_db_triple"):
                db_min_km, db_km, db_max_km = self.catalog.fiber_db_triple(self.wavelength)
                src = "default"
            else:
                db_km = self.catalog.fiber_db_per_km(
                    wavelength_nm=self.wavelength, use_max=self.use_max,
                )
                db_min_km = db_max_km = db_km
                src = "default"
        except Exception:
            db_km = self.catalog.fiber_db_per_km(
                wavelength_nm=self.wavelength, use_max=self.use_max,
            )
            db_min_km = db_max_km = db_km
            src = "default"
        name_part = f" {cable_name}" if cable_name else ""
        side = fiber_vertex_attrs.get("side")
        core = self._fiber_core_info(fiber_vertex_attrs)
        port = core.get("port")
        port_name = core.get("port_name")
        meta_base = {
            "cable_name": cable_name,
            "length_source": length_source,
            "fiber_core_id": core.get("fiber_core_id"),
            "fiber_number": core.get("fiber_number"),
            "module_number": core.get("module_number"),
            "fiber_color": core.get("fiber_color"),
            "module_color": core.get("module_color"),
            "mf_path": core.get("mf_path"),
        }
        if length_m is None:
            return [AttenuationSegment(
                kind="fiber", db=0.0,
                description=f"fiber:{fiber_id}{name_part} length unknown (Lsrc={length_source})",
                obj_type=TYPE_FIBER, obj_id=str(fiber_id), obj_name=cable_name,
                side=int(side) if side is not None else None,
                port=int(port) if port is not None else None,
                port_name=str(port_name) if port_name else None,
                wavelength_nm=self.wavelength, source=src, length_source=length_source,
                meta=meta_base,
            )]
        km = float(length_m) / 1000.0
        db, db_min, db_max = km * float(db_km), km * float(db_min_km), km * float(db_max_km)
        return [AttenuationSegment(
            kind="fiber", db=db, db_min=db_min, db_max=db_max,
            description=(
                f"fiber:{fiber_id}{name_part} {length_m:.1f}m × {db_km:.3f} dB/km "
                f"(Lsrc={length_source}, att={src})"
            ),
            obj_type=TYPE_FIBER, obj_id=str(fiber_id), obj_name=cable_name,
            side=int(side) if side is not None else None,
            port=int(port) if port is not None else None,
            port_name=str(port_name) if port_name else None,
            length_m=float(length_m), length_source=length_source,
            wavelength_nm=self.wavelength, source=src,
            meta={
                **meta_base,
                "db_per_km": db_km,
                "db_per_km_min": db_min_km,
                "db_per_km_max": db_max_km,
            },
        )]

# === calculator_path.py ===
class AttenuationPathMixin(AttenuationPathFiberMixin):
    def _splitter_port_name(self, splitter_obj, port: int) -> Optional[str]:
        if splitter_obj is None or not port:
            return None
        for attr in ("ports", "port_list", "ifaces", "out_ports"):
            ports = (
                getattr(splitter_obj, attr, None)
                if not isinstance(splitter_obj, dict)
                else splitter_obj.get(attr)
            )
            if not ports:
                continue
            if isinstance(ports, dict):
                entry = ports.get(port) or ports.get(str(port))
                if isinstance(entry, dict):
                    return entry.get("name") or entry.get("title") or entry.get("label")
                if isinstance(entry, str):
                    return entry
            if isinstance(ports, list):
                for p in ports:
                    if not isinstance(p, dict):
                        continue
                    num = p.get("number") or p.get("port") or p.get("id")
                    try:
                        if int(num) == int(port):
                            return p.get("name") or p.get("title") or p.get("label")
                    except (TypeError, ValueError):
                        continue
        return None

    def _splitter_segments(
        self, splitter_vertex_attrs: dict, *, direction: str = "unknown", edge_side=None,
    ) -> List[AttenuationSegment]:
        splitter_vertex_attrs = self._ensure_api_obj(splitter_vertex_attrs)
        splitter_id = splitter_vertex_attrs.get("obj_id")
        side = int(splitter_vertex_attrs.get("side") or edge_side or 0)
        port = int(splitter_vertex_attrs.get("port") or 0)
        splitter_obj = splitter_vertex_attrs.get("api_obj")
        # catalog_id / name проставляет ensure_api_obj через Inventory
        catalog_id = splitter_vertex_attrs.get("catalog_id")
        if catalog_id is None:
            catalog_id = self._splitter_catalog_id(splitter_obj)
        pout = None
        if splitter_obj is not None:
            pout = (
                getattr(splitter_obj, "port_count_out", None)
                if not isinstance(splitter_obj, dict)
                else splitter_obj.get("port_count_out")
            )
        topology = None
        if splitter_obj is not None:
            if isinstance(splitter_obj, dict):
                topology = splitter_obj.get("topology_type") or splitter_obj.get("topology")
            else:
                topology = getattr(splitter_obj, "topology_type", None) or getattr(splitter_obj, "topology", None)
        if not topology:
            topology = splitter_vertex_attrs.get("splitter_type")
        name = splitter_vertex_attrs.get("obj_name")
        if not name and hasattr(self, "_resolve_splitter_name"):
            name = self._resolve_splitter_name(splitter_vertex_attrs)
        if not name:
            name = _obj_display_name(splitter_vertex_attrs)
        port_name = self._splitter_port_name(splitter_obj, port)
        if not port_name:
            port_name = splitter_vertex_attrs.get("port_name")
        ratio_key = None
        if name:
            from .catalog import guess_ratio_key
            ratio_key = guess_ratio_key(str(name))
        if hasattr(self.catalog, "splitter_port_db_triple"):
            db_min, db, db_max, source, cat_port_name = self.catalog.splitter_port_db_triple(
                splitter_id=splitter_id, catalog_id=catalog_id, catalog_name=name,
                ratio_key=ratio_key, topology_type=topology,
                port=port if port else None, port_name=port_name,
                port_count_out=pout or 0, wavelength_nm=self.wavelength, prefer_name=True,
            )
        else:
            result = self.catalog.splitter_port_db(
                splitter_id=splitter_id, catalog_id=catalog_id, catalog_name=name,
                ratio_key=ratio_key, topology_type=topology,
                port=port if port else None, port_name=port_name,
                port_count_out=pout or 0, wavelength_nm=self.wavelength,
                use_max=self.use_max, prefer_name=True,
            )
            db, source = result[0], result[1]
            cat_port_name = result[2] if len(result) > 2 else None
            db_min = db_max = db
        if cat_port_name:
            port_name = cat_port_name
        port_label = str(port) if port else "?"
        if port_name:
            port_label = f"{port}/{port_name}"
        name_label = name or f"id={splitter_id}"
        return [AttenuationSegment(
            kind="splitter", db=db, db_min=db_min, db_max=db_max,
            description=(
                f"splitter {name_label} port={port_label} "
                f"side={side} ({topology or '?'}) [{direction}] src={source}"
            ),
            obj_type=TYPE_SPLITTER, obj_id=str(splitter_id),
            obj_name=str(name) if name else None,
            port=port if port else None,
            port_name=str(port_name) if port_name else None,
            side=side, wavelength_nm=self.wavelength, source=source,
            meta={
                "catalog_id": catalog_id,
                "topology": topology,
                "direction": direction, "ratio_key": ratio_key,
                "in_side": _SPLITTER_IN_SIDE, "out_side": _SPLITTER_OUT_SIDE,
            },
        )]

    def _endpoint_from_vertex(self, vindex: int) -> EndpointInfo:
        va = self._ensure_api_obj(self._vertex_attrs(vindex))
        ot = str(va.get("obj_type") or "")
        oid = str(va.get("obj_id") or "")
        side = va.get("side")
        port = va.get("port")
        try:
            side_i = int(side) if side is not None else None
        except (TypeError, ValueError):
            side_i = None
        try:
            port_i = int(port) if port is not None else None
        except (TypeError, ValueError):
            port_i = None
        name = _obj_display_name(va)
        _dev = {TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO}
        host = _olt_host(va) if ot in _dev else None
        port_name = va.get("port_name")
        obj = va.get("api_obj")
        if ot in _dev and port_i is not None:
            resolved = self._device_port_name(obj, port_i)
            if resolved:
                port_name = resolved
        elif port_name is None and obj is not None and port_i is not None:
            port_name = self._device_port_name(obj, port_i)
        commutation_index = None
        login = None
        if ot == TYPE_CUSTOMER:
            commutation_index = self._customer_commutation_index(va, port_i)
            login = self._customer_login(obj)
        meta = {}
        if ot == TYPE_FIBER:
            cn = _cable_name(va)
            if cn:
                meta["cable_name"] = cn
                if not name:
                    name = cn
            core = self._fiber_core_info(va)
            if core.get("port") is not None:
                port_i = int(core["port"])
            if core.get("port_name"):
                port_name = core["port_name"]
            if core.get("fiber_core_id") is not None:
                meta["fiber_core_id"] = core["fiber_core_id"]
            if core.get("fiber_number") is not None:
                meta["fiber_number"] = core["fiber_number"]
            if core.get("module_number") is not None:
                meta["module_number"] = core["module_number"]
            if core.get("fiber_color"):
                meta["fiber_color"] = core["fiber_color"]
            if core.get("module_color"):
                meta["module_color"] = core["module_color"]
            if core.get("mf_path"):
                meta["mf_path"] = core["mf_path"]
        node_id = va.get("node_id")
        try:
            node_id = int(node_id) if node_id is not None else None
        except (TypeError, ValueError):
            node_id = None
        return EndpointInfo(
            obj_type=ot, obj_id=oid,
            obj_name=str(name) if name else None,
            node_id=node_id,
            side=side_i, port=port_i,
            port_name=str(port_name) if port_name else None,
            host=str(host) if host else None,
            commutation_index=commutation_index,
            login=str(login) if login else None,
            label=_label_vertex(va), meta=meta,
        )

    def _device_port_name(self, obj: Any, port: int) -> Optional[str]:
        if obj is None:
            return None

        def _entry_name(entry) -> Optional[str]:
            if entry is None:
                return None
            if isinstance(entry, str):
                s = entry.strip()
                return s or None
            if isinstance(entry, dict):
                for key in ("ifName", "if_name", "name", "title", "label", "caption", "ifDescr"):
                    v = entry.get(key)
                    if v not in (None, ""):
                        return str(v).strip() or None
                return None
            for key in ("ifName", "if_name", "name", "title", "label", "caption", "ifDescr"):
                v = getattr(entry, key, None)
                if v not in (None, ""):
                    return str(v).strip() or None
            return None

        def _entry_nums(entry) -> list:
            nums = []
            if isinstance(entry, dict):
                keys = ("ifNumber", "if_number", "ifIndex", "if_index", "number", "port", "id", "index", "position")
                for k in keys:
                    v = entry.get(k)
                    if v is not None:
                        try:
                            nums.append(int(v))
                        except (TypeError, ValueError):
                            pass
            else:
                for k in ("ifNumber", "if_number", "ifIndex", "if_index", "number", "port", "id", "index", "position"):
                    v = getattr(entry, k, None)
                    if v is not None:
                        try:
                            nums.append(int(v))
                        except (TypeError, ValueError):
                            pass
            return nums

        for attr in ("ifaces", "interfaces", "ports", "port_list"):
            ports = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
            if not ports:
                continue
            if isinstance(ports, dict):
                entry = ports.get(port) or ports.get(str(port))
                name = _entry_name(entry)
                if name:
                    return name
                for entry in ports.values():
                    if port in _entry_nums(entry):
                        name = _entry_name(entry)
                        if name:
                            return name
            if isinstance(ports, (list, tuple)):
                for p in ports:
                    if port in _entry_nums(p):
                        name = _entry_name(p)
                        if name:
                            return name
        return None

    def _customer_commutation_index(self, vattrs: dict, port: Optional[int]) -> Optional[int]:
        obj = vattrs.get("api_obj")
        if obj is None:
            return port
        for attr in ("commutation_index", "commutation", "comm_index", "index"):
            val = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
        meta = vattrs.get("meta") or {}
        if "commutation_index" in meta:
            try:
                return int(meta["commutation_index"])
            except (TypeError, ValueError):
                pass
        return port

    def _customer_login(self, obj: Any) -> Optional[str]:
        """Номер договора: Customer.login."""
        if obj is None:
            return None
        for key in ("login", "Login", "dognumber", "agreement_number", "contract"):
            val = getattr(obj, key, None) if not isinstance(obj, dict) else obj.get(key)
            if val is not None and val != "":
                return str(val).strip() or None
        return None

    def _dedupe_cross_adapters(
        self, segs: List[AttenuationSegment],
    ) -> List[AttenuationSegment]:
        """Оставить ровно один adapter на cross_id (первый по пути)."""
        seen: set = set()
        out: List[AttenuationSegment] = []
        for s in segs:
            if s.kind == "adapter" and s.obj_id:
                cid = str(s.obj_id)
                if cid in seen:
                    continue
                seen.add(cid)
            out.append(s)
        return out

    def _orient_vpath_for_cumulative(
        self, vpath: List[int], direction: str,
    ) -> List[int]:
        """Ориентировать путь по direction (upstream/downstream)."""
        if not vpath or len(vpath) < 2 or self.g is None:
            return list(vpath)
        d = (direction or "unknown").strip().lower()
        if d not in ("upstream", "downstream"):
            return list(vpath)

        device_types = {TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO}
        try:
            t0 = self.g.vs[vpath[0]]["obj_type"]
            t1 = self.g.vs[vpath[-1]]["obj_type"]
        except Exception:
            return list(vpath)

        start_dev = t0 in device_types
        end_dev = t1 in device_types
        start_cust = t0 == TYPE_CUSTOMER
        end_cust = t1 == TYPE_CUSTOMER

        if d == "upstream":
            if start_cust and end_dev:
                return list(reversed(vpath))
            return list(vpath)
        if start_dev and end_cust:
            return list(reversed(vpath))
        return list(vpath)

    def _stamp_node_ids(self, segs, vpath) -> None:
        """Проставить node_id (сооружение связи) на сегменты по вершинам пути."""
        if self.g is None or not segs:
            return
        node_by_obj = {}
        for vi in vpath or []:
            try:
                va = self._vertex_attrs(int(vi))
            except Exception:
                continue
            ot, oid = va.get("obj_type"), va.get("obj_id")
            nid = va.get("node_id")
            if ot is None or oid is None or nid is None:
                continue
            try:
                node_by_obj[(str(ot), str(oid))] = int(nid)
            except (TypeError, ValueError):
                continue
        for s in segs:
            if s.node_id is not None:
                continue
            if s.obj_type is None or s.obj_id is None:
                continue
            s.node_id = node_by_obj.get((str(s.obj_type), str(s.obj_id)))

    def _report_from_vpath(
        self, vpath: List[int], *, direction: Optional[str] = None,
    ) -> PathReport:
        if direction is None:
            direction = self._direction_of_path(vpath)
        vpath = self._orient_vpath_for_cumulative(vpath, direction or "unknown")
        segs: List[AttenuationSegment] = []
        endpoints = {vpath[0], vpath[-1]} if len(vpath) >= 1 else set()
        cross_adapter_seen: set = set()
        for a, b in zip(vpath, vpath[1:]):
            segs.extend(self._edge_segments(
                a, b, direction=direction, path_endpoints=endpoints,
                cross_adapter_seen=cross_adapter_seen,
            ))
        segs = self._dedupe_cross_adapters(segs)
        self._stamp_node_ids(segs, vpath)
        total = sum(s.db for s in segs)
        total_min = sum((s.db_min if s.db_min is not None else s.db) for s in segs)
        total_max = sum((s.db_max if s.db_max is not None else s.db) for s in segs)
        warnings, missing = [], []
        for s in segs:
            if s.source == "estimated":
                warnings.append(f"estimated: {s.description}")
            if s.kind == "fiber" and s.length_m is None:
                missing.append(f"fiber length:{s.obj_id}")
        from_ep = self._endpoint_from_vertex(vpath[0])
        to_ep = self._endpoint_from_vertex(vpath[-1])
        device_ep = customer_ep = None
        for ep in (from_ep, to_ep):
            if ep.obj_type == TYPE_CUSTOMER and customer_ep is None:
                customer_ep = ep
        for prefer in (TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO):
            for ep in (from_ep, to_ep):
                if ep.obj_type == prefer:
                    device_ep = ep
                    break
            if device_ep is not None:
                break
        return PathReport(
            total_db=total, total_db_min=total_min, total_db_max=total_max,
            wavelength_nm=self.wavelength, segments=segs,
            vertex_path=list(vpath), direction=direction or "",
            from_label=str(from_ep), to_label=str(to_ep),
            from_endpoint=from_ep, to_endpoint=to_ep,
            device_endpoint=device_ep, customer_endpoint=customer_ep,
            warnings=warnings, missing=missing,
        )

# === calculator_edge.py ===
_TERMINAL_CONNECTOR_TYPES = frozenset({
    TYPE_OLT, TYPE_CUSTOMER, TYPE_ONU, TYPE_RADIO, TYPE_SWITCH,
})


class AttenuationEdgeMixin:
    def _edge_segments(
        self, u: int, v: int, *, direction: str = "unknown",
        path_endpoints: Optional[set] = None,
        cross_adapter_seen: Optional[Set[str]] = None,
    ) -> List[AttenuationSegment]:
        path_endpoints = path_endpoints or set()
        segs: List[AttenuationSegment] = []
        ua = self._vertex_attrs(u)
        va = self._vertex_attrs(v)
        try:
            eid = self.g.get_eid(u, v, error=False)
        except Exception:
            eid = -1
        is_internal = False
        connect_id = None
        if eid is not None and eid >= 0:
            eattrs = self.g.es[eid].attributes()
            is_internal = bool(eattrs.get("is_internal", False))
            connect_id = eattrs.get("connect_id")

        forced_edge = self.catalog.forced_edge_db(connect_id) if connect_id else None
        if forced_edge is not None:
            segs.append(AttenuationSegment(
                kind="force", db=forced_edge,
                description=f"force edge connect_id={connect_id}",
                source="force", meta={"connect_id": connect_id},
            ))
            return segs

        ta, tb = ua.get("obj_type"), va.get("obj_type")
        ida, idb = str(ua.get("obj_id")), str(va.get("obj_id"))

        if (
            ta == TYPE_FIBER and tb == TYPE_FIBER
            and ida == idb
            and int(ua.get("side", 0)) != int(va.get("side", 0))
        ):
            segs.extend(self._fiber_segments(ua))
            return segs

        if ta == TYPE_SPLITTER and tb == TYPE_SPLITTER and ida == idb:
            out_v = self._splitter_out_vertex(ua, va)
            segs.extend(self._splitter_segments(out_v, direction=direction))
            return segs

        # Внутренняя коммутация кросса (порт↔порт): один adapter на проход.
        if is_internal and ta == TYPE_CROSS and tb == TYPE_CROSS and ida == idb:
            seg = self._maybe_cross_adapter(
                ua, cross_id=ida, connect_id=connect_id, reason="internal",
                cross_adapter_seen=cross_adapter_seen,
            )
            if seg is not None:
                segs.append(seg)
            return segs

        if not is_internal:
            segs.extend(self._external_joint_segments(
                ua, va,
                connect_id=connect_id,
                path_endpoints=path_endpoints,
                u_idx=u,
                v_idx=v,
                cross_adapter_seen=cross_adapter_seen,
            ))
        return segs

    def _connector_db_triple(self):
        if hasattr(self.catalog, "connector_db_triple"):
            return self.catalog.connector_db_triple()
        db = self.catalog.connector_db(use_max=self.use_max)
        return db, db, db

    def _adapter_db_triple(self):
        if hasattr(self.catalog, "adapter_db_triple"):
            return self.catalog.adapter_db_triple()
        db = self.catalog.adapter_db(use_max=self.use_max)
        return db, db, db

    def _maybe_cross_adapter(
        self, cross_attrs: dict, *, cross_id, connect_id=None, reason: str = "",
        cross_adapter_seen: Optional[Set[str]] = None,
    ) -> Optional[AttenuationSegment]:
        """Один adapter на кросс за путь (не на каждый коннектор пришёл/ушёл)."""
        cid = str(cross_id)
        if cross_adapter_seen is not None:
            if cid in cross_adapter_seen:
                return None
            cross_adapter_seen.add(cid)
        return self._cross_adapter_segment(
            cross_attrs, cross_id=cid, connect_id=connect_id, reason=reason,
        )

    def _cross_adapter_segment(
        self, cross_attrs: dict, *, cross_id, connect_id=None, reason: str = "",
    ) -> AttenuationSegment:
        db_min, db, db_max = self._adapter_db_triple()
        return AttenuationSegment(
            kind="adapter", db=db, db_min=db_min, db_max=db_max,
            description=(
                f"adapter cross:{cross_id} port={cross_attrs.get('port')} "
                f"({reason or 'through'})"
            ),
            obj_type=TYPE_CROSS, obj_id=str(cross_id),
            port=cross_attrs.get("port"),
            wavelength_nm=self.wavelength, source="default",
            meta={"connect_id": connect_id, "cross_loss": "adapter", "reason": reason},
        )

    def _cross_connector_segment(
        self, cross_attrs: dict, other_attrs: dict, *, connect_id=None,
    ) -> AttenuationSegment:
        db_min, db, db_max = self._connector_db_triple()
        other_label = self._terminal_label(other_attrs)
        return AttenuationSegment(
            kind="connector", db=db, db_min=db_min, db_max=db_max,
            description=f"connector at cross:{cross_attrs.get('obj_id')} ↔ {other_label}",
            obj_type=TYPE_CROSS,
            obj_id=str(cross_attrs.get("obj_id")),
            port=cross_attrs.get("port"),
            obj_name=_obj_display_name(cross_attrs),
            source="default", wavelength_nm=self.wavelength,
            meta={"connect_id": connect_id, "cross_loss": "connector"},
        )

    def _terminal_label(self, vattrs: dict) -> str:
        ot = vattrs.get("obj_type")
        oid = vattrs.get("obj_id")
        name = _obj_display_name(vattrs)
        host = _olt_host(vattrs) if ot == TYPE_OLT else None
        parts = [f"{ot}:{oid}"]
        if name:
            parts.append(name)
        if host:
            parts.append(f"host={host}")
        return " ".join(parts)

    def _external_joint_segments(
        self, ua: dict, va: dict, *, connect_id=None,
        path_endpoints: Optional[set] = None,
        u_idx: Optional[int] = None,
        v_idx: Optional[int] = None,
        cross_adapter_seen: Optional[Set[str]] = None,
    ) -> List[AttenuationSegment]:
        ta, tb = ua.get("obj_type"), va.get("obj_type")
        ida, idb = str(ua.get("obj_id")), str(va.get("obj_id"))
        kinds = {ta, tb}
        meta = {"connect_id": connect_id}
        path_endpoints = path_endpoints or set()

        if ta == TYPE_SPLITTER and tb == TYPE_SPLITTER and ida != idb:
            if hasattr(self.catalog, "splice_db_triple"):
                db_min, db, db_max = self.catalog.splice_db_triple()
            else:
                db = self.catalog.splice_db(use_max=self.use_max)
                db_min = db_max = db
            na = _obj_display_name(ua) or ida
            nb = _obj_display_name(va) or idb
            return [AttenuationSegment(
                kind="splice", db=db, db_min=db_min, db_max=db_max,
                description=f"splice splitter {na} ↔ {nb}",
                source="default", wavelength_nm=self.wavelength, meta=meta,
            )]

        if TYPE_CROSS in kinds:
            # Кросс — конец/начало пути → connector (на стыке с терминалом).
            # Кросс промежуточный → ровно 1 adapter на весь проход
            # (два коннектора пришёл/ушёл сидят в одном адаптере).
            cross_is_endpoint = False
            if ta == TYPE_CROSS and u_idx is not None and u_idx in path_endpoints:
                cross_is_endpoint = True
            if tb == TYPE_CROSS and v_idx is not None and v_idx in path_endpoints:
                cross_is_endpoint = True

            cross_attrs = ua if ta == TYPE_CROSS else va
            other_attrs = va if ta == TYPE_CROSS else ua
            cross_id = ida if ta == TYPE_CROSS else idb

            if cross_is_endpoint:
                return [self._cross_connector_segment(
                    cross_attrs, other_attrs, connect_id=connect_id,
                )]
            seg = self._maybe_cross_adapter(
                cross_attrs, cross_id=cross_id, connect_id=connect_id,
                reason="through", cross_adapter_seen=cross_adapter_seen,
            )
            return [seg] if seg is not None else []

        terminal = kinds & _TERMINAL_CONNECTOR_TYPES
        if terminal:
            if hasattr(self.catalog, "connector_db_triple"):
                db_min, db, db_max = self.catalog.connector_db_triple()
            else:
                db = self.catalog.connector_db(use_max=self.use_max)
                db_min = db_max = db
            tattrs = ua if ta in _TERMINAL_CONNECTOR_TYPES else va
            label = self._terminal_label(tattrs)
            host = _olt_host(tattrs) if tattrs.get("obj_type") == TYPE_OLT else None
            return [AttenuationSegment(
                kind="connector", db=db, db_min=db_min, db_max=db_max,
                description=f"connector at {label}",
                obj_type=tattrs.get("obj_type"),
                obj_id=str(tattrs.get("obj_id")),
                obj_name=_obj_display_name(tattrs),
                source="default", wavelength_nm=self.wavelength,
                meta={**meta, "host": host} if host else meta,
            )]

        if TYPE_FIBER in kinds:
            if hasattr(self.catalog, "splice_db_triple"):
                db_min, db, db_max = self.catalog.splice_db_triple()
            else:
                db = self.catalog.splice_db(use_max=self.use_max)
                db_min = db_max = db
            return [AttenuationSegment(
                kind="splice", db=db, db_min=db_min, db_max=db_max,
                description="splice at fiber joint",
                source="default", wavelength_nm=self.wavelength, meta=meta,
            )]

        if hasattr(self.catalog, "splice_db_triple"):
            db_min, db, db_max = self.catalog.splice_db_triple()
        else:
            db = self.catalog.splice_db(use_max=self.use_max)
            db_min = db_max = db
        la = self._terminal_label(ua)
        lb = self._terminal_label(va)
        return [AttenuationSegment(
            kind="splice", db=db, db_min=db_min, db_max=db_max,
            description=f"splice {la} ↔ {lb}",
            source="default", wavelength_nm=self.wavelength, meta=meta,
        )]

# === calculator_build.py ===
class AttenuationBuildMixin:
    def _ensure_cgraph(
        self, obj1_type, obj1_id, obj2_type=None, obj2_id=None,
        *, obj1_side=None, obj1_port=None, obj2_side=None, obj2_port=None,
    ) -> None:
        def has_obj(g, otype, oid) -> bool:
            if g is None or otype is None or oid is None:
                return False
            for v in g.vs:
                if v["obj_type"] == otype and str(v["obj_id"]) == str(oid):
                    return True
            return False

        has_b = obj2_type is not None and obj2_id is not None and obj2_id != ""

        if has_b:
            need_build = self.g is None or not (
                has_obj(self.g, obj1_type, obj1_id)
                and has_obj(self.g, obj2_type, obj2_id)
            )
        else:
            need_build = self.g is None or not has_obj(self.g, obj1_type, obj1_id)

        if not need_build:
            return
        if self.client is None:
            raise AttenuationError(
                "CGraph не задан и нет client — невозможно построить граф"
            )

        from ..constants import TYPE_FIBER

        plan = pair_plan(obj1_type, obj2_type if has_b else None)

        # fiber↔fiber corridor
        if has_b and (
            plan.strategy == "fn_corridor"
            or (obj1_type == TYPE_FIBER and obj2_type == TYPE_FIBER)
        ):
            cg = self._build_cgraph_via_fngraph(
                int(obj1_id), int(obj2_id),
                port1=obj1_port, port2=obj2_port,
                side1=obj1_side, side2=obj2_side,
            )
            if cg is not None and has_obj(cg, obj1_type, obj1_id) and has_obj(
                cg, obj2_type, obj2_id
            ):
                self.g = cg
                return

        # только obj1 — строим от него
        if not has_b:
            g = self._build_cgraph_from(
                obj1_type, obj1_id, side=obj1_side, port=obj1_port,
            )
            if g is None or not has_obj(g, obj1_type, obj1_id):
                raise AttenuationError(
                    f"не удалось построить CGraph от {obj1_type}:{obj1_id}"
                )
            self.g = g
            return

        if plan.strategy == "from_b":
            order = [
                ("b", obj2_type, obj2_id, obj2_side, obj2_port),
                ("a", obj1_type, obj1_id, obj1_side, obj1_port),
            ]
        elif plan.strategy == "from_a":
            order = [
                ("a", obj1_type, obj1_id, obj1_side, obj1_port),
                ("b", obj2_type, obj2_id, obj2_side, obj2_port),
            ]
        else:
            order = [
                ("a", obj1_type, obj1_id, obj1_side, obj1_port),
                ("b", obj2_type, obj2_id, obj2_side, obj2_port),
            ]

        built = {}
        for key, ot, oid, side, port in order:
            if ot is None or oid is None:
                continue
            g = self._build_cgraph_from(ot, oid, side=side, port=port)
            built[key] = g
            if g is not None and has_obj(g, obj1_type, obj1_id) and has_obj(
                g, obj2_type, obj2_id
            ):
                self.g = g
                return

        g1, g2 = built.get("a"), built.get("b")
        candidates = [g for g in (g1, g2) if g is not None]
        if len(candidates) == 2:
            try:
                from ..merge import merge_cgraphs
                merged = merge_cgraphs(candidates, self.client, self.cache)
                if merged is not None and has_obj(merged, obj1_type, obj1_id) and has_obj(
                    merged, obj2_type, obj2_id
                ):
                    self.g = merged
                    return
            except Exception:
                pass

        for g in (g1, g2, self.g):
            if g is not None and (
                has_obj(g, obj1_type, obj1_id) or has_obj(g, obj2_type, obj2_id)
            ):
                self.g = g
                break

        if self.g is None:
            raise AttenuationError(
                f"не удалось построить CGraph для {obj1_type}:{obj1_id}"
                + (f" / {obj2_type}:{obj2_id}" if has_b else "")
            )
        if not has_obj(self.g, obj1_type, obj1_id):
            raise AttenuationError(
                f"объект не найден в графе после построения: {obj1_type}:{obj1_id}"
            )
        if has_b and not has_obj(self.g, obj2_type, obj2_id):
            raise AttenuationError(
                f"объект не найден в графе после построения: {obj2_type}:{obj2_id}"
            )

    def _build_cgraph_from(self, obj_type, obj_id, *, side=None, port=None) -> Any:
        from ..graphs.cgraph import CGraph
        cg = CGraph(self.client, cache=self.cache)
        try:
            cg.build(obj_type, obj_id, port=port, side=side)
        except TypeError:
            try:
                cg.build(obj_type, obj_id, port=port)
            except Exception:
                return None
        except Exception:
            return None
        if cg.vcount() == 0:
            return None
        return cg

    def _require_fiber_port(
        self, obj1_type, obj1_id, obj1_port, obj2_type, obj2_id, obj2_port,
        obj1_side=None, obj2_side=None,
    ):
        return validate_pair_inputs(
            obj1_type, obj1_id, obj1_side, obj1_port,
            obj2_type, obj2_id, obj2_side, obj2_port,
        )

    def _pick_endpoint_pair(
        self, obj1_type, obj1_id, obj2_type, obj2_id,
        *, obj1_side=None, obj1_port=None, obj2_side=None, obj2_port=None,
    ):
        def candidates(otype, oid, side, port):
            hits = self.find_vertices(otype, oid, side=side, port=port)
            if hits:
                return hits
            if port is not None:
                hits = self.find_vertices(otype, oid, side=side)
                if hits:
                    return hits
            return self.find_vertices(otype, oid)

        c1 = candidates(obj1_type, obj1_id, obj1_side, obj1_port)
        c2 = candidates(obj2_type, obj2_id, obj2_side, obj2_port)
        if not c1:
            raise AttenuationError(f"объект не найден в графе: {obj1_type}:{obj1_id}")
        if not c2:
            raise AttenuationError(f"объект не найден в графе: {obj2_type}:{obj2_id}")
        best = None
        for a in c1:
            for b in c2:
                if a == b:
                    return a, b
                path = self.shortest_path(a, b)
                if not path or len(path) < 2:
                    continue
                score = len(path)
                if best is None or score < best[0]:
                    best = (score, a, b)
        if best is not None:
            return best[1], best[2]
        raise AttenuationError(
            f"нет связи в CGraph между {obj1_type}:{obj1_id} и {obj2_type}:{obj2_id}"
        )

# === calculator_fn.py ===
def _log():
    try:
        from ....core.logger import log
        return log
    except Exception:
        return None


class AttenuationFNMixin:
    def _build_cgraph_via_fngraph(
        self, fiber1_id: int, fiber2_id: int, *,
        port1=None, port2=None, side1=None, side2=None,
    ) -> Any:
        from ..graphs.cgraph import CGraph
        from ..graphs.fngraph import FNGraph
        lg = _log()
        fiber1_id, fiber2_id = int(fiber1_id), int(fiber2_id)

        start_node = self._fiber_side_node(fiber1_id, side1) if side1 is not None else None
        end_node = self._fiber_side_node(fiber2_id, side2) if side2 is not None else None
        if start_node is None:
            ns = self._fiber_nodes(fiber1_id)
            start_node = ns[0] if ns else None
        if end_node is None:
            ns = self._fiber_nodes(fiber2_id)
            end_node = ns[-1] if ns else None
        if lg:
            lg.info(
                f"FN-corridor: fiber {fiber1_id} side={side1} → node {start_node}; "
                f"fiber {fiber2_id} side={side2} → node {end_node}"
            )
        if start_node is None or end_node is None:
            if lg:
                lg.warning("FN-corridor: нет node_id для сторон кабелей")
            return None

        fn = FNGraph(self.client, cache=self.cache)
        try:
            fn.build(start_node)
        except Exception as e:
            if lg:
                lg.warning(f"FNGraph.build({start_node}) failed: {e}")
            return None
        if fn.vcount() == 0:
            if lg:
                lg.warning("FN-corridor: FNGraph пустой")
            return None

        node_to_v = {int(v["node_id"]): v.index for v in fn.vs}
        if start_node not in node_to_v or end_node not in node_to_v:
            try:
                fn2 = FNGraph(self.client, cache=self.cache)
                fn2.build(end_node)
                if fn2.vcount() > 0:
                    fn = fn2
                    node_to_v = {int(v["node_id"]): v.index for v in fn.vs}
            except Exception:
                pass
        if start_node not in node_to_v or end_node not in node_to_v:
            if lg:
                lg.warning(f"FN-corridor: узлы {start_node}/{end_node} не в FNGraph")
            return None

        try:
            paths = fn.get_shortest_paths(node_to_v[start_node], node_to_v[end_node])
        except Exception as e:
            if lg:
                lg.warning(f"FN path failed: {e}")
            return None
        if not paths or not paths[0]:
            if lg:
                lg.warning(f"FN-corridor: нет пути {start_node} → {end_node}")
            return None
        best_path = paths[0]
        if lg:
            lg.info(f"FN-corridor: path nodes={[fn.vs[i]['node_id'] for i in best_path]}")

        corridor: Set[int] = {
            fiber1_id, fiber2_id,
            self._fiber_code(fiber1_id), self._fiber_code(fiber2_id),
        }
        for a, b in zip(best_path, best_path[1:]):
            try:
                eid = fn.get_eid(a, b, error=False)
            except Exception:
                eid = -1
            if eid is None or eid < 0:
                continue
            fid = fn.es[eid].attributes().get("fiber_id")
            if fid is not None:
                corridor.add(int(fid))

        end_cables = self._fibers_at_node(end_node)
        excluded: Set[int] = {fid for fid in end_cables if fid not in corridor}
        if lg:
            lg.info(
                f"FN-corridor: included={sorted(corridor)}, "
                f"excluded_at_end={sorted(excluded)[:30]}"
            )

        port = port1 if port1 is not None else port2
        attempts = [
            (fiber1_id, port1 if port1 is not None else port, side1),
            (fiber2_id, port2 if port2 is not None else port, side2),
        ]
        for start_fid, p, s in attempts:
            if p is None:
                continue
            for use_exc in (True, False):
                cg = CGraph(self.client, cache=self.cache)
                try:
                    kw = dict(port=p, side=s, included_fibers=corridor)
                    if use_exc and excluded:
                        kw["excluded_fibers"] = excluded
                    cg.build(TYPE_FIBER, start_fid, **kw)
                except Exception as e:
                    if lg:
                        lg.debug(f"CGraph from {start_fid}: {e}")
                    continue
                if cg.vcount() == 0:
                    continue
                ids = {
                    str(v["obj_id"])
                    for v in cg.vs
                    if v["obj_type"] == TYPE_FIBER
                }
                if str(fiber1_id) in ids and str(fiber2_id) in ids:
                    if lg:
                        lg.info(
                            f"FN-corridor: CGraph ok from fiber:{start_fid} "
                            f"v={cg.vcount()}"
                        )
                    return cg
        return None

# === calculator_fiber.py ===
def _log():
    try:
        from ....core.logger import log
        return log
    except Exception:
        return None


def _as_list(result) -> list:
    if result is None:
        return []
    if isinstance(result, list):
        return result
    if hasattr(result, "to_list"):
        try:
            return list(result.to_list() or [])
        except Exception:
            pass
    for attr in ("items", "data", "results", "objects"):
        v = getattr(result, attr, None)
        if v is not None:
            return list(v) if not isinstance(v, list) else v
    if hasattr(result, "node1_id") or hasattr(result, "code") or (
        isinstance(result, dict) and ("node1_id" in result or "code" in result)
    ):
        return [result]
    return []


class AttenuationFiberMixin:
    def _load_fiber(self, fiber_id: int) -> Any:
        """client.Fiber.get_list(object_id=...) → объект с node1_id/node2_id."""
        fid = int(fiber_id)
        lg = _log()
        fiber = None

        if self.cache is not None and self.client is not None:
            try:
                fiber = self.cache.get_fiber(self.client, fid)
            except Exception as e:
                if lg:
                    lg.debug(f"cache.get_fiber({fid}) failed: {e}")

        if fiber is not None:
            if (
                self._fiber_attr(fiber, "node1_id") is not None
                or self._fiber_attr(fiber, "node2_id") is not None
            ):
                return fiber
            fiber = None

        if self.client is None:
            return None

        try:
            result = self.client.Fiber.get_list(object_id=fid)
            items = _as_list(result)
            if items:
                fiber = items[0]
                if lg:
                    lg.info(
                        f"Fiber.get_list(object_id={fid}) → "
                        f"node1_id={self._fiber_attr(fiber, 'node1_id')} "
                        f"node2_id={self._fiber_attr(fiber, 'node2_id')} "
                        f"code={self._fiber_attr(fiber, 'code')}"
                    )
                return fiber
        except Exception as e:
            if lg:
                lg.warning(f"Fiber.get_list(object_id={fid}) failed: {e}")

        if lg:
            lg.warning(f"не удалось загрузить fiber object_id={fid}")
        return None

    def _fiber_attr(self, fiber: Any, name: str):
        if fiber is None:
            return None
        v = getattr(fiber, name, None)
        if v is None and isinstance(fiber, dict):
            v = fiber.get(name)
        if v is None and hasattr(fiber, "__dict__"):
            v = fiber.__dict__.get(name)
        return v

    def _fiber_nodes(self, fiber_id: int) -> List[int]:
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return []
        nodes = []
        for attr in ("node1_id", "node2_id"):
            n = self._fiber_attr(fiber, attr)
            if n is not None:
                nodes.append(int(n))
        return nodes

    def _fiber_side_node(self, fiber_id: int, side: int) -> Optional[int]:
        """side 1 → node1_id, side 2 → node2_id."""
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return None
        side = int(side)
        if side == 1:
            n = self._fiber_attr(fiber, "node1_id")
        elif side == 2:
            n = self._fiber_attr(fiber, "node2_id")
        else:
            return None
        if n is None:
            lg = _log()
            if lg:
                lg.warning(
                    f"fiber {fiber_id}: нет node для side={side} "
                    f"(node1_id={self._fiber_attr(fiber, 'node1_id')}, "
                    f"node2_id={self._fiber_attr(fiber, 'node2_id')})"
                )
            return None
        return int(n)

    def _fiber_code(self, fiber_id: int) -> int:
        fiber = self._load_fiber(fiber_id)
        if fiber is None:
            return int(fiber_id)
        code = self._fiber_attr(fiber, "code")
        return int(code) if code is not None else int(fiber_id)

    def _fibers_at_node(self, node_id: int) -> Set[int]:
        out: Set[int] = set()
        if self.client is None:
            return out
        try:
            result = self.client.Fiber.get_list(node_id=int(node_id))
            for f in _as_list(result):
                fid = self._fiber_attr(f, "code") or self._fiber_attr(f, "id")
                if fid is not None:
                    out.add(int(fid))
        except Exception as e:
            lg = _log()
            if lg:
                lg.debug(f"Fiber.get_list(node_id={node_id}) failed: {e}")
        return out

# === calculator_paths.py ===
_AUTO_TARGETS = frozenset({
    TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
})

_DEVICE_TYPE_PRIORITY = {
    TYPE_OLT: 0,
    TYPE_ONU: 1,
    TYPE_RADIO: 2,
    TYPE_SWITCH: 3,
}


class AttenuationPathsMixin:
    def find_vertices(
        self,
        obj_type: str,
        obj_id,
        *,
        side: Optional[int] = None,
        port: Optional[int] = None,
    ) -> List[int]:
        """Индексы вершин CGraph, совпадающих с объектом."""
        if self.g is None:
            return []
        oid = str(obj_id)
        hits: List[int] = []
        for v in self.g.vs:
            if v["obj_type"] != obj_type:
                continue
            if str(v["obj_id"]) != oid:
                continue
            if side is not None and int(v["side"] or 0) != int(side):
                continue
            if port is not None and int(v["port"] or 0) != int(port):
                continue
            hits.append(int(v.index))
        return hits

    def resolve_vertex(self, ref) -> Optional[int]:
        """Interface / (type,id,side,port) / int / 'type:id' → индекс вершины."""
        if isinstance(ref, int):
            return ref
        if self.g is None:
            return None
        if hasattr(ref, "obj") and hasattr(ref, "side"):
            ot = ref.obj.obj_type
            oid = ref.obj.id
            hits = self.find_vertices(ot, oid, side=ref.side, port=getattr(ref, "port", None))
            return hits[0] if hits else None
        if isinstance(ref, (tuple, list)) and len(ref) >= 2:
            ot, oid = ref[0], ref[1]
            side = ref[2] if len(ref) > 2 else None
            port = ref[3] if len(ref) > 3 else None
            hits = self.find_vertices(ot, oid, side=side, port=port)
            return hits[0] if hits else None
        if isinstance(ref, str) and ":" in ref:
            ot, oid = ref.split(":", 1)
            hits = self.find_vertices(ot, oid)
            return hits[0] if hits else None
        return None

    def all_simple_paths(
        self, source: int, target: int, *, cutoff: int = 200, max_paths=None,
    ) -> List[List[int]]:
        return simple_paths(
            self.g, source, target, cutoff=cutoff, max_paths=max_paths,
        )

    def shortest_path(self, source: int, target: int) -> List[int]:
        path = shortest_simple_path(self.g, source, target)
        if path:
            return path
        try:
            paths = self.g.get_shortest_paths(source, target)
            if paths and paths[0]:
                return list(paths[0])
        except TypeError:
            try:
                paths = self.g.get_shortest_paths(source, to=target, output="vpath")
                if paths and paths[0]:
                    return list(paths[0])
            except Exception:
                pass
        except Exception:
            pass
        return []

    def shortest_paths_batch(
        self, source: int, targets: List[int],
    ) -> List[List[int]]:
        """Кратчайшие пути от source ко всем targets одним вызовом igraph.

        Возвращает список путей (пустой список, если пути нет).
        Порядок соответствует targets.
        """
        if self.g is None or not targets:
            return [[] for _ in targets]
        if len(targets) == 1:
            return [self.shortest_path(source, targets[0])]
        try:
            paths = self.g.get_shortest_paths(source, to=targets, output="vpath")
            out: List[List[int]] = []
            for p in paths:
                out.append(list(p) if p else [])
            while len(out) < len(targets):
                out.append([])
            return out[: len(targets)]
        except Exception:
            return [self.shortest_path(source, t) for t in targets]

    def find_paths(
        self,
        obj1_type: str,
        obj1_id,
        obj2_type: Optional[str] = None,
        obj2_id=None,
        *,
        obj1_side: Optional[int] = None,
        obj1_port: Optional[int] = None,
        obj2_side: Optional[int] = None,
        obj2_port: Optional[int] = None,
        cutoff: int = 200,
        max_paths: Optional[int] = None,
    ) -> List[List[int]]:
        """Все простые пути между объектами (или от obj1 до авто-терминалов)."""
        if self.g is None:
            raise AttenuationError("CGraph не задан")

        sources = self.find_vertices(
            obj1_type, obj1_id, side=obj1_side, port=obj1_port,
        )
        if not sources:
            sources = self.find_vertices(obj1_type, obj1_id, side=obj1_side)
        if not sources:
            sources = self.find_vertices(obj1_type, obj1_id)
        if not sources:
            raise AttenuationError(
                f"объект не найден в графе: {obj1_type}:{obj1_id}"
            )

        if obj2_type is not None and obj2_id is not None:
            targets = self.find_vertices(
                obj2_type, obj2_id, side=obj2_side, port=obj2_port,
            )
            if not targets:
                targets = self.find_vertices(obj2_type, obj2_id, side=obj2_side)
            if not targets:
                targets = self.find_vertices(obj2_type, obj2_id)
            if not targets:
                raise AttenuationError(
                    f"объект не найден в графе: {obj2_type}:{obj2_id}"
                )
        else:
            targets = self._auto_targets(exclude_type=obj1_type, exclude_id=obj1_id)
            if not targets:
                raise AttenuationError(
                    f"конечная точка не указана и в графе нет OLT/switch/onu/radio "
                    f"для пути от {obj1_type}:{obj1_id}"
                )

        collected: List[List[int]] = []
        seen = set()
        only_shortest = max_paths is not None and max_paths <= 1
        for s in sources:
            tgts = [t for t in targets if t != s]
            if not tgts:
                continue
            for sp in self.shortest_paths_batch(s, tgts):
                if sp and len(sp) >= 2:
                    key = tuple(sp)
                    if key not in seen:
                        seen.add(key)
                        collected.append(sp)
                    if max_paths and len(collected) >= max_paths:
                        return collected
            if only_shortest:
                continue
            for t in tgts:
                for p in self.all_simple_paths(s, t, cutoff=cutoff, max_paths=max_paths):
                    if len(p) < 2:
                        continue
                    key = tuple(p)
                    if key not in seen:
                        seen.add(key)
                        collected.append(p)
                    if max_paths and len(collected) >= max_paths:
                        return collected

        if not collected:
            raise AttenuationError(
                f"нет пути в CGraph от {obj1_type}:{obj1_id}"
                + (f" к {obj2_type}:{obj2_id}" if obj2_type else " к терминалу")
            )
        return collected

    def _auto_targets(
        self, *,
        exclude_type: Optional[str] = None,
        exclude_id=None,
    ) -> List[int]:
        """Терминалы OLT/switch/onu/radio."""
        if self.g is None:
            return []
        ex = str(exclude_id) if exclude_id is not None else None
        best = {}
        for v in self.g.vs:
            ot = v["obj_type"]
            if ot not in _AUTO_TARGETS:
                continue
            oid = str(v["obj_id"])
            if exclude_type and ot == exclude_type and oid == ex:
                continue
            pri = _DEVICE_TYPE_PRIORITY.get(ot, 99)
            prev = best.get(oid)
            if prev is None or pri < prev[0]:
                best[oid] = (pri, int(v.index))
        return [idx for _, idx in sorted(best.values(), key=lambda x: x[1])]

# === calculator_graph.py ===
VertexRef = Union[int, str, tuple]


class AttenuationGraphMixin:
    def _cgraph_has_object(
        self, cg: Any, obj_type: str, obj_id: Union[int, str],
        side: Optional[int] = None, port: Optional[int] = None,
    ) -> bool:
        if cg is None:
            return False
        try:
            vs = cg.vs
        except Exception:
            return False
        oid = str(obj_id)
        for v in vs:
            try:
                if v["obj_type"] != obj_type:
                    continue
                if str(v["obj_id"]) != oid:
                    continue
            except Exception:
                continue
            if side is not None:
                try:
                    if int(v["side"] if v["side"] is not None else 0) != int(side):
                        continue
                except Exception:
                    continue
            if port is not None:
                try:
                    if int(v["port"] if v["port"] is not None else 0) != int(port):
                        continue
                except Exception:
                    continue
            return True
        return False

    def _select_cgraph_for_objects(
        self, obj1_type: str, obj1_id: Union[int, str],
        obj2_type: Optional[str] = None, obj2_id: Optional[Union[int, str]] = None,
        *, obj1_side: Optional[int] = None, obj1_port: Optional[int] = None,
        obj2_side: Optional[int] = None, obj2_port: Optional[int] = None,
    ) -> None:
        graphs = list(self.cgraphs) if self.cgraphs else (
            [self.g] if self.g is not None else []
        )
        if not graphs:
            self.g = None
            return
        if len(graphs) == 1:
            self.g = graphs[0]
            return
        has_obj2 = obj2_type is not None and obj2_id is not None and obj2_id != ""
        both: List[Any] = []
        only1: List[Any] = []
        for cg in graphs:
            ok1 = self._cgraph_has_object(cg, obj1_type, obj1_id, side=obj1_side, port=obj1_port)
            if not ok1:
                ok1 = self._cgraph_has_object(cg, obj1_type, obj1_id)
            if not ok1:
                continue
            if has_obj2:
                ok2 = self._cgraph_has_object(cg, obj2_type, obj2_id, side=obj2_side, port=obj2_port)
                if not ok2:
                    ok2 = self._cgraph_has_object(cg, obj2_type, obj2_id)
                if ok2:
                    both.append(cg)
                else:
                    only1.append(cg)
            else:
                only1.append(cg)
        if both:
            self.g = both[0]
            return
        if only1:
            self.g = only1[0]
            return
        self.g = None

    def _dedupe_paths_by_endpoints(self, paths: List[List[int]]) -> List[List[int]]:
        """Оставить по одному пути на уникальную пару конечных точек.

        Ключ — сигнатуры обоих концов (тип, id, side, port), чтобы не
        схлопывать ветки к fiber/splitter/cross/customer и т.д.
        При нескольких путях между одной парой предпочитаем более
        «сильный» device-конец (OLT > ONU > radio > switch).
        """

        def _sig(idx: int):
            try:
                v = self.g.vs[idx]
                return (
                    v["obj_type"],
                    str(v["obj_id"]),
                    int(v["side"] or 0),
                    int(v["port"] or 0),
                )
            except Exception:
                return (None, None, 0, 0)

        def _dev_pri(sig) -> int:
            t = sig[0]
            if t in _AUTO_TARGETS:
                return _DEVICE_TYPE_PRIORITY.get(t, 99)
            return 99

        best = {}  # key -> (pri, path)
        for p in paths:
            if not p or len(p) < 2:
                continue
            sa, sb = _sig(p[0]), _sig(p[-1])
            # канонический ключ пары (порядок не важен)
            key = tuple(sorted([sa, sb]))
            pri = min(_dev_pri(sa), _dev_pri(sb))
            prev = best.get(key)
            if prev is None or pri < prev[0]:
                best[key] = (pri, p)

        # стабильный порядок: как впервые встретились в исходном списке
        seen = set()
        out: List[List[int]] = []
        for p in paths:
            if not p or len(p) < 2:
                continue
            sa, sb = _sig(p[0]), _sig(p[-1])
            key = tuple(sorted([sa, sb]))
            if key in seen:
                continue
            chosen = best.get(key)
            if chosen is not None:
                out.append(chosen[1])
                seen.add(key)
        return out

    def _dedupe_device_vertices(self, indices: List[int]) -> List[int]:
        if self.g is None or not indices:
            return list(indices or [])
        best = {}
        for idx in indices:
            try:
                v = self.g.vs[idx]
                ot = v["obj_type"]
                oid = str(v["obj_id"])
            except Exception:
                continue
            if ot not in _AUTO_TARGETS:
                best[f"_raw:{idx}"] = (99, idx)
                continue
            pri = _DEVICE_TYPE_PRIORITY.get(ot, 99)
            prev = best.get(oid)
            if prev is None or pri < prev[0]:
                best[oid] = (pri, idx)
        return [idx for _, idx in sorted(best.values(), key=lambda x: x[1])]

    def _vertices_of_types(self, types) -> List[int]:
        if self.g is None:
            return []
        out: List[int] = []
        for v in self.g.vs:
            if v["obj_type"] in types:
                out.append(int(v.index))
        return out

    def _terminal_endpoints(self) -> List[int]:
        """Вершины, на которых заканчивается коммутация.

        1) terminate_vertex=True (ставится билдером для любого типа),
        2) иначе degree==1,
        3) иначе TERMINAL_TYPES.
        """
        if self.g is None:
            return []
        marked: List[int] = []
        for v in self.g.vs:
            try:
                if v["terminate_vertex"]:
                    marked.append(int(v.index))
            except Exception:
                continue
        if marked:
            return marked
        leaves = self._leaf_vertices()
        if leaves:
            return leaves
        from ..constants import TERMINAL_TYPES
        return self._vertices_of_types(TERMINAL_TYPES)

    def _leaf_vertices(self) -> List[int]:
        if self.g is None:
            return []
        leaves: List[int] = []
        for v in self.g.vs:
            idx = int(v.index)
            try:
                deg = self.g.degree(idx)
            except Exception:
                try:
                    deg = len(list(self.g.neighbors(idx)))
                except Exception:
                    deg = 0
            if deg == 1:
                leaves.append(idx)
        return leaves

    def _linear_cover_path(self) -> List[int]:
        leaves = self._leaf_vertices()
        if len(leaves) != 2:
            is_lin = getattr(self.g, "is_linear", None)
            if callable(is_lin):
                try:
                    if not is_lin():
                        return []
                except Exception:
                    pass
            if len(leaves) < 2:
                return []
        s, t = leaves[0], leaves[-1]
        return self.shortest_path(s, t)

    def path_report(
        self, source: VertexRef, target: VertexRef, *,
        direction: Optional[str] = None,
    ) -> PathReport:
        if self.g is None:
            raise AttenuationError("CGraph не задан")
        s = self.resolve_vertex(source) if not isinstance(source, int) else source
        t = self.resolve_vertex(target) if not isinstance(target, int) else target
        if s is None or t is None:
            raise AttenuationError("не удалось разрешить вершины пути")
        vpath = self.shortest_path(s, t)
        if not vpath:
            raise AttenuationError("нет пути между вершинами")
        return self._report_from_vpath(vpath, direction=direction)
