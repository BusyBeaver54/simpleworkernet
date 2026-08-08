# simpleworkernet/utils/topology/attenuation/calculator_edge.py
"""Edge → attenuation segments."""
from __future__ import annotations
from typing import List, Optional
from ..constants import TYPE_CROSS, TYPE_FIBER, TYPE_SPLITTER
from .models import AttenuationSegment

class AttenuationEdgeMixin:
    def _edge_segments(
        self,
        u: int,
        v: int,
        *,
        direction: str = "unknown",
    ) -> List[AttenuationSegment]:
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
        if (
            ua.get("obj_type") == TYPE_FIBER and va.get("obj_type") == TYPE_FIBER
            and str(ua.get("obj_id")) == str(va.get("obj_id"))
            and int(ua.get("side", 0)) != int(va.get("side", 0))
        ):
            segs.extend(self._fiber_segments(ua))
            return segs
        # IL сплиттера: ребро между сторонами одного сплиттера
        if (
            ua.get("obj_type") == TYPE_SPLITTER
            and va.get("obj_type") == TYPE_SPLITTER
            and str(ua.get("obj_id")) == str(va.get("obj_id"))
        ):
            out_v = self._splitter_out_vertex(ua, va)
            segs.extend(self._splitter_segments(out_v, direction=direction))
            return segs
        if is_internal and (
            ua.get("obj_type") == TYPE_CROSS and va.get("obj_type") == TYPE_CROSS
            and str(ua.get("obj_id")) == str(va.get("obj_id"))
        ):
            db = self.catalog.adapter_db(use_max=self.use_max)
            segs.append(AttenuationSegment(
                kind="adapter", db=db,
                description=f"adapter cross:{ua.get('obj_id')} port={ua.get('port')}",
                obj_type=TYPE_CROSS, obj_id=str(ua.get("obj_id")), port=ua.get("port"),
                wavelength_nm=self.wavelength, source="default",
            ))
            return segs
        if not is_internal:
            kinds = {ua.get("obj_type"), va.get("obj_type")}
            if TYPE_FIBER in kinds:
                db = self.catalog.splice_db(use_max=self.use_max)
                segs.append(AttenuationSegment(
                    kind="splice", db=db, description="splice at fiber joint",
                    source="default", wavelength_nm=self.wavelength,
                    meta={"connect_id": connect_id},
                ))
            else:
                db = self.catalog.connector_db(use_max=self.use_max)
                segs.append(AttenuationSegment(
                    kind="connector", db=db,
                    description="connector joint" if TYPE_CROSS not in kinds else "patch to cross",
                    source="default", wavelength_nm=self.wavelength,
                    meta={"connect_id": connect_id},
                ))
        return segs
