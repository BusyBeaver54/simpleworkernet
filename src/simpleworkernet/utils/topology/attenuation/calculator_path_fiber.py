# simpleworkernet/utils/topology/attenuation/calculator_path_fiber.py
"""Fiber path segments for Attenuation."""
from __future__ import annotations
from typing import Any, List, Optional
from ..constants import TYPE_FIBER
from .models import AttenuationSegment
from .calculator_segments import _cable_name


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
            cable_name = _cable_name(fiber_vertex_attrs)
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
