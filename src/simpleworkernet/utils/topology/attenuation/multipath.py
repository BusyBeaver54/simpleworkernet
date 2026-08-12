# simpleworkernet/utils/topology/attenuation/multipath.py
"""Отчёт по ветвям нелинейного CGraph."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union
from .models import PathReport


@dataclass
class MultiPathReport:
    branches: List[PathReport] = field(default_factory=list)
    wavelength_nm: int = 1550
    from_label: str = ""
    to_label: str = ""
    warnings: List[str] = field(default_factory=list)
    # Параметры поиска/расчёта текущих веток
    query: dict = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.branches)

    @property
    def min_db(self) -> float:
        """Минимальный total_db среди веток."""
        return min((b.total_db for b in self.branches), default=0.0)

    @property
    def max_db(self) -> float:
        """Максимальный total_db среди веток."""
        return max((b.total_db for b in self.branches), default=0.0)

    @property
    def min_trace_len(self) -> float:
        """Минимальная длина трассы (волокно, м) среди веток."""
        if not self.branches:
            return 0.0
        return min(b.fiber_length_m for b in self.branches)

    @property
    def max_trace_len(self) -> float:
        """Максимальная длина трассы (волокно, м) среди веток."""
        if not self.branches:
            return 0.0
        return max(b.fiber_length_m for b in self.branches)

    def branch_for(self, obj_type: str, obj_id) -> Optional[PathReport]:
        key = f"{obj_type}:{obj_id}"
        for b in self.branches:
            if b.from_endpoint and (
                b.from_endpoint.obj_type == obj_type
                and str(b.from_endpoint.obj_id) == str(obj_id)
            ):
                return b
            if b.to_endpoint and (
                b.to_endpoint.obj_type == obj_type
                and str(b.to_endpoint.obj_id) == str(obj_id)
            ):
                return b
            if key in (b.to_label or "") or key in (b.from_label or ""):
                return b
        return None

    def to_dict(self) -> dict:
        return {
            "schema": "simpleworkernet.attenuation.MultiPathReport/v3",
            "wavelength_nm": self.wavelength_nm,
            "count": self.count,
            "min_db": round(self.min_db, 4),
            "max_db": round(self.max_db, 4),
            "min_trace_len": round(self.min_trace_len, 2),
            "max_trace_len": round(self.max_trace_len, 2),
            "query": dict(self.query or {}),
            "branches": [b.to_dict() for b in self.branches],
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MultiPathReport":
        branches = [PathReport.from_dict(b) for b in (d.get("branches") or [])]
        return cls(
            branches=branches,
            wavelength_nm=int(d.get("wavelength_nm") or 1550),
            warnings=list(d.get("warnings") or []),
            query=dict(d.get("query") or {}),
        )

    def to_table(self) -> str:
        lines = [
            f"MultiPath  λ={self.wavelength_nm} nm  branches={self.count}",
            (
                f"  db: min={self.min_db:.4f}  max={self.max_db:.4f}  "
                f"trace: min={self.min_trace_len:.2f} m  max={self.max_trace_len:.2f} m"
            ),
        ]
        if self.query:
            qbits = ", ".join(f"{k}={v}" for k, v in self.query.items() if v is not None)
            if qbits:
                lines.append(f"  query: {qbits}")
        lines.append("=" * 72)
        for i, b in enumerate(self.branches, 1):
            lines.append(
                f"--- branch {i}/{self.count}: "
                f"calc={b.total_db:.3f} len={b.fiber_length_m:.2f} m ---"
            )
            lines.append(b.to_table())
        if self.warnings:
            lines.append("warnings: " + "; ".join(self.warnings))
        return "\n".join(lines)

    def save(self, path: Union[str, Path]) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return p

    @classmethod
    def load(cls, path: Union[str, Path]) -> "MultiPathReport":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"MultiPathReport не найден: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return (
            f"MultiPathReport(branches={self.count}, "
            f"min_db={self.min_db:.3f}, max_db={self.max_db:.3f}, "
            f"min_len={self.min_trace_len:.1f}, max_len={self.max_trace_len:.1f})"
        )
