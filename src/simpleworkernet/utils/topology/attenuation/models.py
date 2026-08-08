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
    port: Optional[int] = None
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
            "port": self.port,
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
            port=int(d["port"]) if d.get("port") is not None else None,
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
    def length_m(self) -> float:
        return sum(s.length_m or 0.0 for s in self.segments if s.kind == "fiber")

    @property
    def fiber_db(self) -> float:
        return sum(s.db for s in self.segments if s.kind == "fiber")

    @property
    def splitter_db(self) -> float:
        return sum(s.db for s in self.segments if s.kind == "splitter")

    @property
    def passive_db(self) -> float:
        return sum(
            s.db for s in self.segments
            if s.kind in ("splice", "adapter", "connector")
        )

    def by_kind(self) -> dict:
        out: dict = {}
        for s in self.segments:
            out[s.kind] = out.get(s.kind, 0.0) + s.db
        return {k: round(v, 4) for k, v in out.items()}

    def to_table(self) -> str:
        lines = [
            f"{self.from_label} → {self.to_label}  λ={self.wavelength_nm} nm  "
            f"total={self.total_db:.3f} dB "
            f"(fiber={self.fiber_db:.3f}, splitter={self.splitter_db:.3f}, "
            f"passive={self.passive_db:.3f})  L={self.length_m:.1f} m",
            "-" * 72,
            f"{'#':>3} {'kind':12} {'dB':>8} {'L,m':>8}  description",
        ]
        for i, s in enumerate(self.segments, 1):
            lm = f"{s.length_m:.1f}" if s.length_m is not None else "-"
            lines.append(
                f"{i:>3} {s.kind:12} {s.db:>8.3f} {lm:>8}  {s.description}"
            )
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ! {w}")
        if self.missing:
            lines.append("Missing profiles:")
            for m in self.missing:
                lines.append(f"  ? {m}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        d = {
            "schema": "simpleworkernet.attenuation.PathReport/v1",
            "total_db": round(self.total_db, 4),
            "wavelength_nm": self.wavelength_nm,
            "direction": self.direction,
            "from": self.from_label,
            "to": self.to_label,
            "length_m": round(self.length_m, 2),
            "by_kind": self.by_kind(),
            "segments": [s.to_dict() for s in self.segments],
            "vertex_path": self.vertex_path,
            "warnings": self.warnings,
            "missing": self.missing,
        }
        if self.query_meta:
            for k, v in self.query_meta.items():
                if k not in d and v is not None:
                    d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PathReport":
        segs = [AttenuationSegment.from_dict(s) for s in (d.get("segments") or [])]
        meta_keys = (
            "obj1_type", "obj1_id", "obj1_side", "obj1_port",
            "obj2_type", "obj2_id", "obj2_side", "obj2_port",
            "computed_at", "strategy", "host",
        )
        qm = {k: d[k] for k in meta_keys if k in d}
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
            query_meta=qm,
        )

    def save(self, path: Optional[Union[str, Path]] = None, **kwargs) -> Path:
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
