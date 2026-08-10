# simpleworkernet/utils/topology/attenuation/models.py
"""Модели отчёта и сегментов затухания."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from ..constants import TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO, TYPE_CUSTOMER

_DEVICE_EP = frozenset({TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO})


@dataclass
class EndpointInfo:
    obj_type: str = ""
    obj_id: str = ""
    obj_name: Optional[str] = None
    side: Optional[int] = None
    port: Optional[int] = None
    port_name: Optional[str] = None
    host: Optional[str] = None
    commutation_index: Optional[int] = None
    label: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "obj_type": self.obj_type,
            "obj_id": self.obj_id,
            "obj_name": self.obj_name,
            "side": self.side,
            "port": self.port,
            "port_name": self.port_name,
            "host": self.host,
            "commutation_index": self.commutation_index,
            "label": self.label,
        }
        if self.meta:
            d["meta"] = self.meta
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EndpointInfo":
        if not d:
            return cls()
        return cls(
            obj_type=str(d.get("obj_type") or ""),
            obj_id=str(d.get("obj_id") or ""),
            obj_name=str(d["obj_name"]) if d.get("obj_name") is not None else None,
            side=int(d["side"]) if d.get("side") is not None else None,
            port=int(d["port"]) if d.get("port") is not None else None,
            port_name=str(d["port_name"]) if d.get("port_name") is not None else None,
            host=str(d["host"]) if d.get("host") is not None else None,
            commutation_index=int(d["commutation_index"]) if d.get("commutation_index") is not None else None,
            label=str(d.get("label") or ""),
            meta=dict(d.get("meta") or {}),
        )

    def __str__(self) -> str:
        parts = [f"{self.obj_type}:{self.obj_id}"]
        if self.obj_name:
            parts.append(self.obj_name)
        if self.host:
            parts.append(f"host={self.host}")
        if self.port is not None:
            p = str(self.port)
            if self.port_name:
                p = f"{p}/{self.port_name}"
            parts.append(f"port={p}")
        if self.commutation_index is not None:
            parts.append(f"comm={self.commutation_index}")
        if self.side is not None:
            parts.append(f"side={self.side}")
        return " ".join(parts)


@dataclass
class AttenuationSegment:
    kind: str
    db: float
    description: str = ""
    obj_type: Optional[str] = None
    obj_id: Optional[str] = None
    obj_name: Optional[str] = None
    port: Optional[int] = None
    port_name: Optional[str] = None
    side: Optional[int] = None
    length_m: Optional[float] = None
    length_source: Optional[str] = None
    wavelength_nm: Optional[int] = None
    source: str = "default"
    db_min: Optional[float] = None
    db_max: Optional[float] = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.db_min is None:
            self.db_min = self.db
        if self.db_max is None:
            self.db_max = self.db

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "db": round(self.db, 4),
            "db_min": round(self.db_min if self.db_min is not None else self.db, 4),
            "db_max": round(self.db_max if self.db_max is not None else self.db, 4),
            "description": self.description,
            "obj_type": self.obj_type,
            "obj_id": self.obj_id,
            "obj_name": self.obj_name,
            "port": self.port,
            "port_name": self.port_name,
            "side": self.side,
            "length_m": self.length_m,
            "length_source": self.length_source,
            "wavelength_nm": self.wavelength_nm,
            "source": self.source,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AttenuationSegment":
        db = float(d.get("db") or 0.0)
        return cls(
            kind=str(d.get("kind") or "unknown"),
            db=db,
            description=str(d.get("description") or ""),
            obj_type=d.get("obj_type"),
            obj_id=str(d["obj_id"]) if d.get("obj_id") is not None else None,
            obj_name=str(d["obj_name"]) if d.get("obj_name") is not None else None,
            port=int(d["port"]) if d.get("port") is not None else None,
            port_name=str(d["port_name"]) if d.get("port_name") is not None else None,
            side=int(d["side"]) if d.get("side") is not None else None,
            length_m=float(d["length_m"]) if d.get("length_m") is not None else None,
            length_source=d.get("length_source"),
            wavelength_nm=int(d["wavelength_nm"]) if d.get("wavelength_nm") is not None else None,
            source=str(d.get("source") or "default"),
            db_min=float(d["db_min"]) if d.get("db_min") is not None else db,
            db_max=float(d["db_max"]) if d.get("db_max") is not None else db,
            meta=dict(d.get("meta") or {}),
        )


@dataclass
class PathReport:
    total_db: float = 0.0
    total_db_min: float = 0.0
    total_db_max: float = 0.0
    wavelength_nm: int = 1550
    segments: List[AttenuationSegment] = field(default_factory=list)
    vertex_path: List[int] = field(default_factory=list)
    direction: str = ""
    from_label: str = ""
    to_label: str = ""
    from_endpoint: Optional[EndpointInfo] = None
    to_endpoint: Optional[EndpointInfo] = None
    device_endpoint: Optional[EndpointInfo] = None
    customer_endpoint: Optional[EndpointInfo] = None
    warnings: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    query_meta: dict = field(default_factory=dict)

    @property
    def fiber_length_m(self) -> float:
        return sum(s.length_m or 0.0 for s in self.segments if s.kind == "fiber")

    @property
    def fiber_db(self) -> float:
        return sum(s.db for s in self.segments if s.kind == "fiber")

    @property
    def splitter_db(self) -> float:
        return sum(s.db for s in self.segments if s.kind == "splitter")

    @property
    def joint_db(self) -> float:
        return sum(s.db for s in self.segments if s.kind in ("splice", "adapter", "connector"))

    def by_kind(self) -> dict:
        out = {}
        for s in self.segments:
            out[s.kind] = out.get(s.kind, 0.0) + s.db
        return {k: round(v, 4) for k, v in out.items()}

    def _pick_device_customer(self):
        device = self.device_endpoint
        customer = self.customer_endpoint
        for ep in (self.from_endpoint, self.to_endpoint):
            if ep is None:
                continue
            if ep.obj_type in _DEVICE_EP and device is None:
                device = ep
            if ep.obj_type == TYPE_CUSTOMER and customer is None:
                customer = ep
        return device, customer

    def to_table(self) -> str:
        device, customer = self._pick_device_customer()
        lines = [
            f"Path  λ={self.wavelength_nm} nm  "
            f"calc={self.total_db:.3f}  min={self.total_db_min:.3f}  "
            f"max={self.total_db_max:.3f} dB "
            f"(fiber={self.fiber_db:.3f}, splitter={self.splitter_db:.3f}, "
            f"joints={self.joint_db:.3f})",
        ]
        if customer:
            bits = [f"{customer.obj_type}:{customer.obj_id}"]
            if customer.obj_name:
                bits.append(f"name={customer.obj_name}")
            if customer.commutation_index is not None:
                bits.append(f"commutation={customer.commutation_index}")
            if customer.port is not None:
                bits.append(f"port={customer.port}")
            lines.append("  customer: " + ", ".join(bits))
        if device:
            bits = [f"{device.obj_type}:{device.obj_id}"]
            if device.obj_name:
                bits.append(f"name={device.obj_name}")
            if device.host:
                bits.append(f"host={device.host}")
            if device.port is not None:
                p = str(device.port)
                if device.port_name:
                    p = f"{p}/{device.port_name}"
                bits.append(f"port={p}")
            lines.append(f"  {device.obj_type}: " + ", ".join(bits))
        lines.append("-" * 72)
        for i, s in enumerate(self.segments, 1):
            bits = []
            if s.obj_type and s.obj_id:
                bits.append(f"{s.obj_type}:{s.obj_id}")
            if s.obj_name:
                bits.append(f"name={s.obj_name}")
            if s.port is not None:
                p = str(s.port)
                if s.port_name:
                    p = f"{p}/{s.port_name}"
                bits.append(f"port={p}")
            if s.side is not None:
                bits.append(f"side={s.side}")
            if s.length_m is not None:
                bits.append(f"L={s.length_m:.1f}m")
            if s.length_source:
                bits.append(f"Lsrc={s.length_source}")
            bits.append(f"min={s.db_min:.3f}")
            bits.append(f"max={s.db_max:.3f}")
            if s.source:
                bits.append(f"src={s.source}")
            extra = " [" + ", ".join(bits) + "]"
            lines.append(f"{i:3d}. {s.kind:10s} {s.db:7.3f} dB  {s.description}{extra}")
        if self.warnings:
            lines.append("warnings: " + "; ".join(self.warnings))
        if self.missing:
            lines.append("missing: " + "; ".join(self.missing))
        return "\n".join(lines)

    def to_dict(self) -> dict:
        device, customer = self._pick_device_customer()
        return {
            "schema": "simpleworkernet.attenuation.PathReport/v3",
            "total_db": round(self.total_db, 4),
            "total_db_min": round(self.total_db_min, 4),
            "total_db_max": round(self.total_db_max, 4),
            "wavelength_nm": self.wavelength_nm,
            "from_endpoint": self.from_endpoint.to_dict() if self.from_endpoint else None,
            "to_endpoint": self.to_endpoint.to_dict() if self.to_endpoint else None,
            "device_endpoint": device.to_dict() if device else None,
            "customer_endpoint": customer.to_dict() if customer else None,
            "direction": self.direction,
            "segments": [s.to_dict() for s in self.segments],
            "vertex_path": self.vertex_path,
            "warnings": self.warnings,
            "missing": self.missing,
            "query_meta": self.query_meta,
            "by_kind": self.by_kind(),
            "fiber_length_m": round(self.fiber_length_m, 2),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PathReport":
        segs = [AttenuationSegment.from_dict(s) for s in (d.get("segments") or [])]
        fe, te = d.get("from_endpoint"), d.get("to_endpoint")
        de, ce = d.get("device_endpoint"), d.get("customer_endpoint")
        total = float(d.get("total_db") or 0.0)
        return cls(
            total_db=total,
            total_db_min=float(d["total_db_min"]) if d.get("total_db_min") is not None else total,
            total_db_max=float(d["total_db_max"]) if d.get("total_db_max") is not None else total,
            wavelength_nm=int(d.get("wavelength_nm") or 1550),
            segments=segs,
            vertex_path=list(d.get("vertex_path") or []),
            direction=str(d.get("direction") or ""),
            from_label=str(d.get("from") or d.get("from_label") or ""),
            to_label=str(d.get("to") or d.get("to_label") or ""),
            from_endpoint=EndpointInfo.from_dict(fe) if fe else None,
            to_endpoint=EndpointInfo.from_dict(te) if te else None,
            device_endpoint=EndpointInfo.from_dict(de) if de else None,
            customer_endpoint=EndpointInfo.from_dict(ce) if ce else None,
            warnings=list(d.get("warnings") or []),
            missing=list(d.get("missing") or []),
            query_meta=dict(d.get("query_meta") or {}),
        )

    def save(self, path: Union[str, Path] = None, **kwargs):
        from .report_io import save_path_report
        return save_path_report(self, path, **kwargs)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "PathReport":
        from .report_io import load_path_report
        return load_path_report(path)

    def __repr__(self) -> str:
        return (
            f"PathReport(calc={self.total_db:.3f}, "
            f"min={self.total_db_min:.3f}, max={self.total_db_max:.3f} dB, "
            f"segs={len(self.segments)})"
        )
