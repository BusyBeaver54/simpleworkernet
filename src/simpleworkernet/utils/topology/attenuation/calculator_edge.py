# simpleworkernet/utils/topology/attenuation/calculator_edge.py
"""Edge → attenuation segments."""
from __future__ import annotations
from typing import List, Optional, Set
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
