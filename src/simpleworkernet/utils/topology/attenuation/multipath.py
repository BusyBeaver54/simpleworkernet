# simpleworkernet/utils/topology/attenuation/multipath.py
"""Отчёт по ветвям нелинейного CGraph."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .models import PathReport

@dataclass
class MultiPathReport:
    branches: List[PathReport] = field(default_factory=list)
    wavelength_nm: int = 1550
    from_label: str = ""
    to_label: str = ""
    warnings: List[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.branches)

    @property
    def total_db_min(self) -> float:
        return min((b.total_db for b in self.branches), default=0.0)

    @property
    def total_db_max(self) -> float:
        return max((b.total_db for b in self.branches), default=0.0)

    @property
    def total_db_avg(self) -> float:
        if not self.branches:
            return 0.0
        return sum(b.total_db for b in self.branches) / len(self.branches)

    def branch_for(self, obj_type: str, obj_id) -> Optional[PathReport]:
        key = f"{obj_type}:{obj_id}"
        for b in self.branches:
            if key in b.to_label or key in b.from_label:
                return b
        return None

    def to_dict(self) -> dict:
        return {
            "schema": "simpleworkernet.attenuation.MultiPathReport/v1",
            "wavelength_nm": self.wavelength_nm,
            "from": self.from_label,
            "to": self.to_label,
            "count": self.count,
            "total_db_min": round(self.total_db_min, 4),
            "total_db_max": round(self.total_db_max, 4),
            "total_db_avg": round(self.total_db_avg, 4),
            "branches": [b.to_dict() for b in self.branches],
            "warnings": self.warnings,
        }

    def to_table(self) -> str:
        lines = [
            f"MultiPath {self.from_label} → {self.to_label}  λ={self.wavelength_nm} nm  "
            f"branches={self.count}  min={self.total_db_min:.3f} "
            f"max={self.total_db_max:.3f} avg={self.total_db_avg:.3f} dB",
            "=" * 72,
        ]
        for i, b in enumerate(self.branches, 1):
            lines.append(f"--- branch {i}/{self.count}: {b.total_db:.3f} dB ---")
            lines.append(b.to_table())
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"MultiPathReport(branches={self.count}, "
            f"min={self.total_db_min:.3f}, max={self.total_db_max:.3f} dB)"
        )
