# simpleworkernet/utils/topology/attenuation/calculator_path.py
"""Path report assembly for Attenuation."""
from __future__ import annotations
from typing import Any, List, Optional
from ..constants import TYPE_FIBER, TYPE_SPLITTER
from .models import AttenuationSegment, PathReport
from .calculator_segments import _label_vertex, _SPLITTER_IN_SIDE, _SPLITTER_OUT_SIDE

class AttenuationPathMixin:
    def _fiber_segments(self, fiber_vertex_attrs: dict) -> List[AttenuationSegment]:
        fiber_id = fiber_vertex_attrs.get("obj_id")
        fiber_obj = fiber_vertex_attrs.get("api_obj")
        if fiber_obj is None and self.cache is not None and self.client is not None:
            fiber_obj = self.cache.get_fiber(self.client, int(fiber_id))
        length_m, length_source = self._fiber_length(fiber_id, fiber_obj)
        forced = self.catalog.forced_fiber_db_per_km(
            fiber_id, self.wavelength, use_max=self.use_max
        )
        cabletype_id = None
        if fiber_obj is not None:
            cabletype_id = (
                getattr(fiber_obj, "cablecode", None)
                or getattr(fiber_obj, "cabletype_id", None)
                or getattr(fiber_obj, "cable_line_type_id", None)
            )
        if forced is not None:
            alpha = forced
            source = "force"
        else:
            alpha = self.catalog.cable_db_per_km(
                cabletype_id, self.wavelength, use_max=self.use_max
            )
            source = "profile" if cabletype_id is not None else "default"
        if length_m is None:
            return [
                AttenuationSegment(
                    kind="fiber", db=0.0,
                    description=f"fiber:{fiber_id} length unknown",
                    obj_type=TYPE_FIBER, obj_id=str(fiber_id),
                    length_m=None, length_source=length_source,
                    wavelength_nm=self.wavelength, source=source,
                    meta={"db_per_km": alpha, "cabletype_id": cabletype_id},
                )
            ]
        db = alpha * (length_m / 1000.0)
        return [
            AttenuationSegment(
                kind="fiber", db=db,
                description=(
                    f"fiber:{fiber_id} L={length_m:.1f}m "
                    f"α={alpha:.3f} dB/km ({length_source})"
                ),
                obj_type=TYPE_FIBER, obj_id=str(fiber_id),
                length_m=length_m, length_source=length_source,
                wavelength_nm=self.wavelength, source=source,
                meta={"db_per_km": alpha, "cabletype_id": cabletype_id},
            )
        ]

    def _splitter_segments(
        self,
        splitter_vertex_attrs: dict,
        *,
        direction: str,
        edge_side: Optional[int] = None,
    ) -> List[AttenuationSegment]:
        splitter_id = splitter_vertex_attrs.get("obj_id")
        side = int(splitter_vertex_attrs.get("side") or edge_side or 0)
        port = int(splitter_vertex_attrs.get("port") or 0)
        splitter_obj = splitter_vertex_attrs.get("api_obj")
        catalog_id = self._splitter_catalog_id(splitter_obj)
        pin = getattr(splitter_obj, "port_count_in", None) if splitter_obj else None
        pout = getattr(splitter_obj, "port_count_out", None) if splitter_obj else None
        topology = f"{pin}x{pout}" if pin and pout else None
        if not topology:
            topology = splitter_vertex_attrs.get("splitter_type")
        name = None
        if splitter_obj is not None:
            name = getattr(splitter_obj, "name", None) or getattr(
                splitter_obj, "title", None
            )
        ratio_key = None
        if name:
            from .catalog_helpers import guess_ratio_key
            ratio_key = guess_ratio_key(str(name))
        db, source = self.catalog.splitter_port_db(
            splitter_id=splitter_id,
            catalog_id=catalog_id,
            catalog_name=name,
            ratio_key=ratio_key,
            topology_type=topology,
            port=port if port else None,
            port_count_out=pout or 0,
            wavelength_nm=self.wavelength,
            use_max=self.use_max,
        )
        return [
            AttenuationSegment(
                kind="splitter", db=db,
                description=(
                    f"splitter:{splitter_id} out port={port} "
                    f"side={side} ({topology or '?'}) [{direction}] src={source}"
                ),
                obj_type=TYPE_SPLITTER, obj_id=str(splitter_id),
                port=port, side=side,
                wavelength_nm=self.wavelength, source=source,
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
        self,
        vpath: List[int],
        *,
        direction: Optional[str] = None,
    ) -> PathReport:
        if direction is None:
            direction = self._direction_of_path(vpath)
        segs: List[AttenuationSegment] = []
        for a, b in zip(vpath, vpath[1:]):
            segs.extend(self._edge_segments(a, b, direction=direction))
        total = sum(s.db for s in segs)
        warnings = []
        missing = []
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
