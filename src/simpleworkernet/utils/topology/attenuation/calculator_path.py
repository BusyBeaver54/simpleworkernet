# simpleworkernet/utils/topology/attenuation/calculator_path.py
"""Path report assembly for Attenuation."""
from __future__ import annotations
from typing import Any, List, Optional
from ..constants import TYPE_FIBER, TYPE_SPLITTER
from .models import AttenuationSegment, PathReport
from .calculator_segments import (
    _label_vertex, _obj_display_name, _olt_host, _cable_name,
    _SPLITTER_IN_SIDE, _SPLITTER_OUT_SIDE,
)


class AttenuationPathMixin:
    def _fiber_segments(self, fiber_vertex_attrs: dict) -> List[AttenuationSegment]:
        fiber_id = fiber_vertex_attrs.get("obj_id")
        length_m = fiber_vertex_attrs.get("length_m")
        length_source = fiber_vertex_attrs.get("length_source") or "unknown"
        cable_name = None
        if hasattr(self, "_resolve_cable_name"):
            cable_name = self._resolve_cable_name(fiber_vertex_attrs)
        if not cable_name:
            cable_name = _cable_name(fiber_vertex_attrs)

        if length_m is None and self.cache is not None and self.client is not None:
            try:
                length_m, length_source = self._fiber_length_m(fiber_id)
            except Exception:
                try:
                    length_m, length_source = self._fiber_length(
                        fiber_id, fiber_vertex_attrs.get("api_obj")
                    )
                except Exception:
                    length_m, length_source = None, "missing"

        db_km = self.catalog.fiber_db_per_km(
            wavelength_nm=self.wavelength,
            use_max=self.use_max,
        )
        src = "default"
        try:
            if cable_name and hasattr(self.catalog, "cable_db_per_km"):
                db_km = self.catalog.cable_db_per_km(
                    name=cable_name,
                    wavelength_nm=self.wavelength,
                    use_max=self.use_max,
                )
                src = "cable"
        except Exception:
            pass

        name_part = f" {cable_name}" if cable_name else ""
        if length_m is None:
            return [
                AttenuationSegment(
                    kind="fiber", db=0.0,
                    description=f"fiber:{fiber_id}{name_part} length unknown",
                    obj_type=TYPE_FIBER, obj_id=str(fiber_id),
                    obj_name=cable_name,
                    wavelength_nm=self.wavelength, source=src,
                    length_source=length_source,
                    meta={"cable_name": cable_name},
                )
            ]
        db = (float(length_m) / 1000.0) * float(db_km)
        return [
            AttenuationSegment(
                kind="fiber", db=db,
                description=(
                    f"fiber:{fiber_id}{name_part} "
                    f"{length_m:.1f}m × {db_km:.3f} dB/km"
                ),
                obj_type=TYPE_FIBER, obj_id=str(fiber_id),
                obj_name=cable_name,
                length_m=float(length_m), length_source=length_source,
                wavelength_nm=self.wavelength, source=src,
                meta={"cable_name": cable_name, "db_per_km": db_km},
            )
        ]

    def _splitter_port_name(self, splitter_obj, port: int) -> Optional[str]:
        """Имя порта из модели сплиттера (API), если есть."""
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
        self,
        splitter_vertex_attrs: dict,
        *,
        direction: str = "unknown",
        edge_side=None,
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
                topology = (
                    getattr(splitter_obj, "topology_type", None)
                    or getattr(splitter_obj, "topology", None)
                )
        if not topology:
            topology = splitter_vertex_attrs.get("splitter_type")

        name = None
        if hasattr(self, "_resolve_splitter_name"):
            name = self._resolve_splitter_name(splitter_vertex_attrs)
        if not name:
            name = _obj_display_name(splitter_vertex_attrs)

        # имя порта: сначала API, затем JSON-каталог (через splitter_port_db)
        port_name = self._splitter_port_name(splitter_obj, port)
        if not port_name:
            port_name = splitter_vertex_attrs.get("port_name")

        ratio_key = None
        if name:
            from .catalog_helpers import guess_ratio_key
            ratio_key = guess_ratio_key(str(name))

        result = self.catalog.splitter_port_db(
            splitter_id=splitter_id,
            catalog_id=catalog_id,
            catalog_name=name,
            ratio_key=ratio_key,
            topology_type=topology,
            port=port if port else None,
            port_name=port_name,
            port_count_out=pout or 0,
            wavelength_nm=self.wavelength,
            use_max=self.use_max,
            prefer_name=True,
        )
        # (db, source) или (db, source, port_name)
        if len(result) == 3:
            db, source, cat_port_name = result
        else:
            db, source = result[0], result[1]
            cat_port_name = None

        # JSON-каталог имеет приоритет для отображаемого имени порта
        if cat_port_name:
            port_name = cat_port_name

        port_label = str(port) if port else "?"
        if port_name:
            port_label = f"{port}/{port_name}"
        name_label = name or f"id={splitter_id}"

        return [
            AttenuationSegment(
                kind="splitter", db=db,
                description=(
                    f"splitter {name_label} port={port_label} "
                    f"side={side} ({topology or '?'}) [{direction}] src={source}"
                ),
                obj_type=TYPE_SPLITTER,
                obj_id=str(splitter_id),
                obj_name=str(name) if name else None,
                port=port if port else None,
                port_name=str(port_name) if port_name else None,
                side=side,
                wavelength_nm=self.wavelength,
                source=source,
                meta={
                    "catalog_id": catalog_id,
                    "topology": topology,
                    "direction": direction,
                    "ratio_key": ratio_key,
                    "in_side": _SPLITTER_IN_SIDE,
                    "out_side": _SPLITTER_OUT_SIDE,
                },
            )
        ]

    def _report_from_vpath(
        self, vpath: List[int], *, direction: Optional[str] = None,
    ) -> PathReport:
        if direction is None:
            direction = self._direction_of_path(vpath)
        segs: List[AttenuationSegment] = []
        for a, b in zip(vpath, vpath[1:]):
            segs.extend(self._edge_segments(a, b, direction=direction))
        total = sum(s.db for s in segs)
        warnings, missing = [], []
        for s in segs:
            if s.source == "estimated":
                warnings.append(f"estimated: {s.description}")
            if s.kind == "fiber" and s.length_m is None:
                missing.append(f"fiber length:{s.obj_id}")
        return PathReport(
            total_db=total,
            wavelength_nm=self.wavelength,
            segments=segs,
            vertex_path=list(vpath),
            direction=direction or "",
            from_label=_label_vertex(self._vertex_attrs(vpath[0])),
            to_label=_label_vertex(self._vertex_attrs(vpath[-1])),
            warnings=warnings,
            missing=missing,
        )
