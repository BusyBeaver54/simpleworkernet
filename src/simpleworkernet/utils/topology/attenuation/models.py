# simpleworkernet/utils/topology/attenuation/models.py
"""Модели отчёта и сегментов затухания."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union


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
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "db": round(self.db, 4),
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
        return cls(
            kind=str(d.get("kind") or "unknown"),
            db=float(d.get("db") or 0.0),
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
            meta=dict(d.get("meta") or {}),
        )


@dataclass
class PathReport:
    total_db: float = 0.0
    wavelength_nm: int = 1550
    segments: List[AttenuationSegment] = field(default_factory=list)
    vertex_path: List[int] = field(default_factory=list)
    direction: str = ""
    from_label: str = ""
    to_label: str = ""
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
        return sum(
            s.db for s in self.segments
            if s.kind in ("splice", "adapter", "connector")
        )

    def by_kind(self) -> dict:
        out = {}
        for s in self.segments:
            out[s.kind] = out.get(s.kind, 0.0) + s.db
        return {k: round(v, 4) for k, v in out.items()}

    def to_table(self) -> str:
        lines = [
            f"Path {self.from_label} → {self.to_label}  λ={self.wavelength_nm} nm  "
            f"total={self.total_db:.3f} dB "
            f"(fiber={self.fiber_db:.3f}, splitter={self.splitter_db:.3f}, "
            f"joints={self.joint_db:.3f})",
            "-" * 72,
        ]
        for i, s in enumerate(self.segments, 1):
            bits = []
            if s.obj_name:
                bits.append(f"name={s.obj_name}")
            if s.port is not None:
                bits.append(f"port={s.port}")
            if s.port_name:
                bits.append(f"port_name={s.port_name}")
            if s.meta.get("host"):
                bits.append(f"host={s.meta['host']}")
            if s.meta.get("cable_name") and not s.obj_name:
                bits.append(f"cable={s.meta['cable_name']}")
            extra = (" [" + ", ".join(bits) + "]") if bits else ""
            lines.append(f"{i:3d}. {s.kind:10s} {s.db:7.3f} dB  {s.description}{extra}")
        if self.warnings:
            lines.append("warnings: " + "; ".join(self.warnings))
        if self.missing:
            lines.append("missing: " + "; ".join(self.missing))
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "schema": "simpleworkernet.attenuation.PathReport/v1",
            "total_db": round(self.total_db, 4),
            "wavelength_nm": self.wavelength_nm,
            "from": self.from_label,
            "to": self.to_label,
            "direction": self.direction,
            "segments": [s.to_dict() for s in self.segments],
            "vertex_path": self.vertex_path,
            "warnings": self.warnings,
            "missing": self.missing,
            "query_meta": self.query_meta,
            "by_kind": self.by_kind(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PathReport":
        segs = [AttenuationSegment.from_dict(s) for s in (d.get("segments") or [])]
        return cls(
            total_db=float(d.get("total_db") or 0.0),
            wavelength_nm=int(d.get("wavelength_nm") or 1550),
            segments=segs,
            vertex_path=list(d.get("vertex_path") or []),
            direction=str(d.get("direction") or ""),
            from_label=str(d.get("from") or d.get("from_label") or ""),
            to_label=str(d.get("to") or d.get("to_label") or ""),
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
            f"PathReport({self.from_label!r}→{self.to_label!r}, "
            f"{self.total_db:.3f} dB, segs={len(self.segments)})"
        )
