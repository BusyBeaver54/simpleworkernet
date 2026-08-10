# simpleworkernet/utils/topology/attenuation/calculator_path.py
"""Path report assembly for Attenuation."""
from __future__ import annotations
from typing import Any, List, Optional
from ..constants import (
    TYPE_CUSTOMER, TYPE_FIBER, TYPE_OLT, TYPE_SPLITTER,
    TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
)
from .models import AttenuationSegment, EndpointInfo, PathReport
from .calculator_segments import (
    _label_vertex, _obj_display_name, _olt_host, _cable_name, _attr,
    _SPLITTER_IN_SIDE, _SPLITTER_OUT_SIDE,
)


class AttenuationPathMixin:
    def _fiber_segments(self, fiber_vertex_attrs: dict) -> List[AttenuationSegment]:
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
        port = fiber_vertex_attrs.get("port")
        if length_m is None:
            return [AttenuationSegment(
                kind="fiber", db=0.0,
                description=f"fiber:{fiber_id}{name_part} length unknown (Lsrc={length_source})",
                obj_type=TYPE_FIBER, obj_id=str(fiber_id), obj_name=cable_name,
                side=int(side) if side is not None else None,
                port=int(port) if port is not None else None,
                wavelength_nm=self.wavelength, source=src, length_source=length_source,
                meta={"cable_name": cable_name, "length_source": length_source},
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
            length_m=float(length_m), length_source=length_source,
            wavelength_nm=self.wavelength, source=src,
            meta={
                "cable_name": cable_name, "db_per_km": db_km,
                "db_per_km_min": db_min_km, "db_per_km_max": db_max_km,
                "length_source": length_source,
            },
        )]

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
        splitter_id = splitter_vertex_attrs.get("obj_id")
        side = int(splitter_vertex_attrs.get("side") or edge_side or 0)
        port = int(splitter_vertex_attrs.get("port") or 0)
        splitter_obj = splitter_vertex_attrs.get("api_obj")
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
        name = None
        if hasattr(self, "_resolve_splitter_name"):
            name = self._resolve_splitter_name(splitter_vertex_attrs)
        if not name:
            name = _obj_display_name(splitter_vertex_attrs)
        port_name = self._splitter_port_name(splitter_obj, port)
        if not port_name:
            port_name = splitter_vertex_attrs.get("port_name")
        ratio_key = None
        if name:
            from .catalog_helpers import guess_ratio_key
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
                "catalog_id": catalog_id, "topology": topology,
                "direction": direction, "ratio_key": ratio_key,
                "in_side": _SPLITTER_IN_SIDE, "out_side": _SPLITTER_OUT_SIDE,
            },
        )]

    def _endpoint_from_vertex(self, vindex: int) -> EndpointInfo:
        va = self._vertex_attrs(vindex)
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
        if port_name is None and obj is not None and port_i is not None:
            port_name = self._device_port_name(obj, port_i)
        commutation_index = None
        if ot == TYPE_CUSTOMER:
            commutation_index = self._customer_commutation_index(va, port_i)
        meta = {}
        if ot == TYPE_FIBER:
            cn = _cable_name(va)
            if cn:
                meta["cable_name"] = cn
                if not name:
                    name = cn
        return EndpointInfo(
            obj_type=ot, obj_id=oid,
            obj_name=str(name) if name else None,
            side=side_i, port=port_i,
            port_name=str(port_name) if port_name else None,
            host=str(host) if host else None,
            commutation_index=commutation_index,
            label=_label_vertex(va), meta=meta,
        )

    def _device_port_name(self, obj: Any, port: int) -> Optional[str]:
        if obj is None:
            return None
        for attr in ("ports", "ifaces", "interfaces", "port_list"):
            ports = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
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
                    num = p.get("number") or p.get("port") or p.get("id") or p.get("index")
                    try:
                        if int(num) == int(port):
                            return p.get("name") or p.get("title") or p.get("label")
                    except (TypeError, ValueError):
                        continue
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

    def _report_from_vpath(
        self, vpath: List[int], *, direction: Optional[str] = None,
    ) -> PathReport:
        if direction is None:
            direction = self._direction_of_path(vpath)
        segs: List[AttenuationSegment] = []
        for a, b in zip(vpath, vpath[1:]):
            segs.extend(self._edge_segments(a, b, direction=direction))
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
