# simpleworkernet/utils/topology/attenuation/models.py
"""Модели отчёта и сегментов затухания."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from ..constants import TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO, TYPE_CUSTOMER

# Версия схемы PathReport/MultiPathReport (для сравнения при load)
DATA_VERSION = "3.3"

_DEVICE_EP = frozenset({TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO})


@dataclass
class EndpointInfo:
    obj_type: str = ""
    obj_id: str = ""
    obj_name: Optional[str] = None
    node_id: Optional[int] = None
    side: Optional[int] = None
    port: Optional[int] = None
    port_name: Optional[str] = None
    host: Optional[str] = None
    commutation_index: Optional[int] = None
    # Для customer: login = номер договора (Customer.login)
    login: Optional[str] = None
    label: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "obj_type": self.obj_type,
            "obj_id": self.obj_id,
            "obj_name": self.obj_name,
            "node_id": self.node_id,
            "side": self.side,
            "port": self.port,
            "port_name": self.port_name,
            "host": self.host,
            "commutation_index": self.commutation_index,
            "login": self.login,
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
            node_id=int(d["node_id"]) if d.get("node_id") is not None else None,
            side=int(d["side"]) if d.get("side") is not None else None,
            port=int(d["port"]) if d.get("port") is not None else None,
            port_name=str(d["port_name"]) if d.get("port_name") is not None else None,
            host=str(d["host"]) if d.get("host") is not None else None,
            commutation_index=int(d["commutation_index"]) if d.get("commutation_index") is not None else None,
            login=str(d["login"]) if d.get("login") is not None else None,
            label=str(d.get("label") or ""),
            meta=dict(d.get("meta") or {}),
        )

    def format_sp(self) -> str:
        s = self.side if self.side is not None else "?"
        p = self.port if self.port is not None else "?"
        return f"s{s}p{p}"

    def format_header(self) -> str:
        parts = [f"{self.obj_type}:{self.obj_id}", self.format_sp()]
        if self.node_id is not None:
            parts.append(f"node={self.node_id}")
        if self.host:
            parts.append(f"host={self.host}")
        if self.obj_name:
            parts.append(f"name={self.obj_name}")
        if self.port_name:
            parts.append(f"port={self.port_name}")
        if self.commutation_index is not None:
            parts.append(f"commutation={self.commutation_index}")
        if self.login:
            parts.append(f"login={self.login}")
        return " ".join(parts)

    def __str__(self) -> str:
        return self.format_header()


@dataclass
class AttenuationSegment:
    kind: str
    db: float
    description: str = ""
    obj_type: Optional[str] = None
    obj_id: Optional[str] = None
    obj_name: Optional[str] = None
    node_id: Optional[int] = None
    port: Optional[int] = None
    port_name: Optional[str] = None
    side: Optional[int] = None
    length_m: Optional[float] = None
    length_source: Optional[str] = None
    wavelength_nm: Optional[int] = None
    source: str = "default"
    db_min: Optional[float] = None
    db_max: Optional[float] = None
    # Кумулятивное затухание от корня пути (from_endpoint) до конца этого сегмента
    path_db: Optional[float] = None
    path_db_min: Optional[float] = None
    path_db_max: Optional[float] = None
    # upstream / downstream — то же, что у PathReport (ориентация пути)
    direction: str = ""
    # Начальная и конечная точки сегмента (интерфейсы по краям ребра/стыка)
    start: Optional[EndpointInfo] = None
    end: Optional[EndpointInfo] = None
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
            "path_db": (
                round(self.path_db, 4) if self.path_db is not None else None
            ),
            "path_db_min": (
                round(self.path_db_min, 4) if self.path_db_min is not None else None
            ),
            "path_db_max": (
                round(self.path_db_max, 4) if self.path_db_max is not None else None
            ),
            "description": self.description,
            "obj_type": self.obj_type,
            "obj_id": self.obj_id,
            "obj_name": self.obj_name,
            "node_id": self.node_id,
            "port": self.port,
            "port_name": self.port_name,
            "side": self.side,
            "length_m": self.length_m,
            "length_source": self.length_source,
            "wavelength_nm": self.wavelength_nm,
            "source": self.source,
            "direction": self.direction or "",
            "start": self.start.to_dict() if self.start else None,
            "end": self.end.to_dict() if self.end else None,
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
            node_id=int(d["node_id"]) if d.get("node_id") is not None else None,
            port=int(d["port"]) if d.get("port") is not None else None,
            port_name=str(d["port_name"]) if d.get("port_name") is not None else None,
            side=int(d["side"]) if d.get("side") is not None else None,
            length_m=float(d["length_m"]) if d.get("length_m") is not None else None,
            length_source=d.get("length_source"),
            wavelength_nm=int(d["wavelength_nm"]) if d.get("wavelength_nm") is not None else None,
            source=str(d.get("source") or "default"),
            db_min=float(d["db_min"]) if d.get("db_min") is not None else db,
            db_max=float(d["db_max"]) if d.get("db_max") is not None else db,
            path_db=float(d["path_db"]) if d.get("path_db") is not None else None,
            path_db_min=float(d["path_db_min"]) if d.get("path_db_min") is not None else None,
            path_db_max=float(d["path_db_max"]) if d.get("path_db_max") is not None else None,
            direction=str(d.get("direction") or ""),
            start=EndpointInfo.from_dict(d["start"]) if d.get("start") else None,
            end=EndpointInfo.from_dict(d["end"]) if d.get("end") else None,
            meta=dict(d.get("meta") or {}),
        )


@dataclass
class PathReport:
    total_db: float = 0.0
    total_db_min: float = 0.0
    total_db_max: float = 0.0
    wavelength_nm: int = 1550
    dataversion: str = DATA_VERSION
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

    def __post_init__(self) -> None:
        """Дозаполнить total_* и кумулятивные path_db* по сегментам.

        path_db — сумма db от корня пути (from_endpoint / первый сегмент
        после ориентации upstream/downstream или obj1→obj2) до текущего
        сегмента включительно.
        """
        if not self.total_db_min:
            self.total_db_min = self.total_db
        if not self.total_db_max:
            self.total_db_max = self.total_db
        acc = acc_min = acc_max = 0.0
        for s in self.segments:
            if s.path_db is not None:
                # уже проставлено (load / calculator) — синхронизируем аккумулятор
                acc = float(s.path_db)
                acc_min = float(s.path_db_min if s.path_db_min is not None else s.path_db)
                acc_max = float(s.path_db_max if s.path_db_max is not None else s.path_db)
                continue
            acc += float(s.db or 0.0)
            acc_min += float(s.db_min if s.db_min is not None else s.db or 0.0)
            acc_max += float(s.db_max if s.db_max is not None else s.db or 0.0)
            s.path_db = acc
            s.path_db_min = acc_min
            s.path_db_max = acc_max

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
        ends = [ep for ep in (self.from_endpoint, self.to_endpoint) if ep is not None]

        if customer is None:
            for ep in ends:
                if ep.obj_type == TYPE_CUSTOMER:
                    customer = ep
                    break

        if device is None:
            for prefer in (TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO):
                for ep in ends:
                    if ep.obj_type == prefer:
                        device = ep
                        break
                if device is not None:
                    break
            if device is None:
                for ep in ends:
                    if ep.obj_type in _DEVICE_EP:
                        device = ep
                        break

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
        if customer is not None:
            lines.append(f"  customer: {customer.format_header()}")
        if device is not None:
            lines.append(f"  {device.obj_type}: {device.format_header()}")
        if customer is None and device is None:
            for tag, ep in (("from", self.from_endpoint), ("to", self.to_endpoint)):
                if ep is not None:
                    lines.append(f"  {tag}: {ep.format_header()}")
        lines.append("-" * 80)
        for i, s in enumerate(self.segments, 1):
            bits = []
            if s.obj_type and s.obj_id:
                bits.append(f"{s.obj_type}:{s.obj_id}")
            if s.node_id is not None:
                bits.append(f"node={s.node_id}")
            if s.obj_name:
                bits.append(f"name={s.obj_name}")
            if s.side is not None or s.port is not None:
                sp = f"s{s.side if s.side is not None else '?'}p{s.port if s.port is not None else '?'}"
                bits.append(sp)
            if s.port_name:
                bits.append(f"port={s.port_name}")
            if s.length_m is not None:
                bits.append(f"L={s.length_m:.1f}m")
            if s.length_source:
                bits.append(f"Lsrc={s.length_source}")
            bits.append(f"min={s.db_min:.3f}")
            bits.append(f"max={s.db_max:.3f}")
            if s.path_db is not None:
                bits.append(f"path={s.path_db:.3f}")
            if s.path_db_min is not None and s.path_db_max is not None:
                bits.append(f"path_min={s.path_db_min:.3f}")
                bits.append(f"path_max={s.path_db_max:.3f}")
            if s.source:
                bits.append(f"src={s.source}")
            if s.start is not None and (s.start.obj_type or s.start.obj_id):
                bits.append(f"from={s.start.obj_type}:{s.start.obj_id}{s.start.format_sp()}")
            if s.end is not None and (s.end.obj_type or s.end.obj_id):
                bits.append(f"to={s.end.obj_type}:{s.end.obj_id}{s.end.format_sp()}")
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
            "dataversion": self.dataversion or DATA_VERSION,
            "total_db": round(self.total_db, 4),
            "total_db_min": round(self.total_db_min, 4),
            "total_db_max": round(self.total_db_max, 4),
            "wavelength_nm": self.wavelength_nm,
            "from": self.from_label,
            "to": self.to_label,
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
            dataversion=str(d.get("dataversion") or DATA_VERSION),
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
