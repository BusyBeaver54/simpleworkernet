# simpleworkernet/utils/topology/attenuation/models.py
"""Модели отчёта и сегментов затухания."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class AttenuationSegment:
    """Один вклад в суммарное затухание на пути."""

    kind: str  # fiber | splitter | splice | adapter | connector | force | unknown
    db: float
    description: str = ""
    obj_type: Optional[str] = None
    obj_id: Optional[str] = None
    port: Optional[int] = None
    side: Optional[int] = None
    length_m: Optional[float] = None
    length_source: Optional[str] = None  # opticalen2 | opticalen | geo | geo_api | forced | none
    wavelength_nm: Optional[int] = None
    source: str = "default"  # force | profile | default | estimated
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


@dataclass
class PathReport:
    """Результат расчёта затухания вдоль пути."""

    total_db: float = 0.0
    wavelength_nm: int = 1550
    segments: List[AttenuationSegment] = field(default_factory=list)
    vertex_path: List[int] = field(default_factory=list)
    direction: str = ""  # downstream | upstream | unknown
    from_label: str = ""
    to_label: str = ""
    warnings: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

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
            s.db
            for s in self.segments
            if s.kind in ("splice", "adapter", "connector")
        )

    def by_kind(self) -> dict:
        out: dict = {}
        for s in self.segments:
            out[s.kind] = out.get(s.kind, 0.0) + s.db
        return {k: round(v, 4) for k, v in out.items()}

    def to_table(self) -> str:
        lines = [
            f"Path: {self.from_label} → {self.to_label}  "
            f"[{self.direction}]  λ={self.wavelength_nm} nm",
            f"Total: {self.total_db:.3f} dB  "
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
        return {
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

    def __repr__(self) -> str:
        return (
            f"PathReport({self.from_label!r}→{self.to_label!r}, "
            f"{self.total_db:.3f} dB, segs={len(self.segments)})"
        )
