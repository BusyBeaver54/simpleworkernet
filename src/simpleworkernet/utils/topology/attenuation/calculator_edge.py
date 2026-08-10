# simpleworkernet/utils/topology/attenuation/calculator_edge.py
"""Edge → attenuation segments."""
from __future__ import annotations
from typing import List
from ..constants import (
    TYPE_CROSS, TYPE_CUSTOMER, TYPE_FIBER, TYPE_OLT, TYPE_ONU,
    TYPE_RADIO, TYPE_SPLITTER, TYPE_SWITCH,
)
from .models import AttenuationSegment
from .calculator_segments import _obj_display_name, _olt_host

_TERMINAL_CONNECTOR_TYPES = frozenset({
    TYPE_OLT, TYPE_CUSTOMER, TYPE_ONU, TYPE_RADIO, TYPE_SWITCH,
})


class AttenuationEdgeMixin:
    def _edge_segments(
        self, u: int, v: int, *, direction: str = "unknown",
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

        if is_internal and ta == TYPE_CROSS and tb == TYPE_CROSS and ida == idb:
            mode = self._cross_loss_mode()
            if mode == "adapter":
                db = self.catalog.adapter_db(use_max=self.use_max)
                segs.append(AttenuationSegment(
                    kind="adapter", db=db,
                    description=(
                        f"adapter cross:{ida} port={ua.get('port')} "
                        f"(вход+выход={db} dB)"
                    ),
                    obj_type=TYPE_CROSS, obj_id=ida, port=ua.get("port"),
                    wavelength_nm=self.wavelength, source="default",
                    meta={"cross_loss_mode": mode},
                ))
            return segs

        if not is_internal:
            segs.extend(self._external_joint_segments(ua, va, connect_id=connect_id))
        return segs

    def _cross_loss_mode(self) -> str:
        try:
            if hasattr(self.catalog, "cross_loss_mode"):
                return self.catalog.cross_loss_mode()
        except Exception:
            pass
        try:
            mode = self.catalog.defaults.get("cross_loss_mode")
        except Exception:
            mode = None
        if mode in ("adapter", "connectors"):
            return mode
        return "adapter"

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
    ) -> List[AttenuationSegment]:
        ta, tb = ua.get("obj_type"), va.get("obj_type")
        ida, idb = str(ua.get("obj_id")), str(va.get("obj_id"))
        kinds = {ta, tb}
        meta = {"connect_id": connect_id}

        if ta == TYPE_SPLITTER and tb == TYPE_SPLITTER and ida != idb:
            db = self.catalog.splice_db(use_max=self.use_max)
            na = _obj_display_name(ua) or ida
            nb = _obj_display_name(va) or idb
            return [AttenuationSegment(
                kind="splice", db=db,
                description=f"splice splitter {na} ↔ {nb}",
                source="default", wavelength_nm=self.wavelength, meta=meta,
            )]

        if TYPE_CROSS in kinds:
            if self._cross_loss_mode() == "connectors":
                db = self.catalog.connector_db(use_max=self.use_max)
                other = ua if tb == TYPE_CROSS else va
                other_label = self._terminal_label(other)
                return [AttenuationSegment(
                    kind="connector", db=db,
                    description=f"connector → cross ({other_label})",
                    obj_type=TYPE_CROSS,
                    obj_id=ida if ta == TYPE_CROSS else idb,
                    obj_name=_obj_display_name(other),
                    source="default", wavelength_nm=self.wavelength, meta=meta,
                )]
            if TYPE_FIBER in kinds:
                db = self.catalog.splice_db(use_max=self.use_max)
                return [AttenuationSegment(
                    kind="splice", db=db,
                    description="splice fiber↔cross",
                    source="default", wavelength_nm=self.wavelength, meta=meta,
                )]
            return []

        terminal = kinds & _TERMINAL_CONNECTOR_TYPES
        if terminal:
            db = self.catalog.connector_db(use_max=self.use_max)
            tattrs = ua if ta in _TERMINAL_CONNECTOR_TYPES else va
            label = self._terminal_label(tattrs)
            host = _olt_host(tattrs) if tattrs.get("obj_type") == TYPE_OLT else None
            return [AttenuationSegment(
                kind="connector", db=db,
                description=f"connector at {label}",
                obj_type=tattrs.get("obj_type"),
                obj_id=str(tattrs.get("obj_id")),
                obj_name=_obj_display_name(tattrs),
                source="default", wavelength_nm=self.wavelength,
                meta={**meta, "host": host} if host else meta,
            )]

        if TYPE_FIBER in kinds:
            db = self.catalog.splice_db(use_max=self.use_max)
            return [AttenuationSegment(
                kind="splice", db=db,
                description="splice at fiber joint",
                source="default", wavelength_nm=self.wavelength, meta=meta,
            )]

        db = self.catalog.splice_db(use_max=self.use_max)
        la = self._terminal_label(ua)
        lb = self._terminal_label(va)
        return [AttenuationSegment(
            kind="splice", db=db,
            description=f"splice {la} ↔ {lb}",
            source="default", wavelength_nm=self.wavelength, meta=meta,
        )]
