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

    @property
    def count(self) -> int:
        return len(self.branches)

    @property
    def total_db_min(self) -> float:
        return min((getattr(b, "total_db_min", b.total_db) for b in self.branches), default=0.0)

    @property
    def total_db_max(self) -> float:
        return max((getattr(b, "total_db_max", b.total_db) for b in self.branches), default=0.0)

    @property
    def total_db_avg(self) -> float:
        if not self.branches:
            return 0.0
        return sum(b.total_db for b in self.branches) / len(self.branches)

    @property
    def total_db(self) -> float:
        return self.total_db_avg

    def branch_for(self, obj_type: str, obj_id) -> Optional[PathReport]:
        key = f"{obj_type}:{obj_id}"
        for b in self.branches:
            fe, te = getattr(b, "from_endpoint", None), getattr(b, "to_endpoint", None)
            if fe and fe.obj_type == obj_type and str(fe.obj_id) == str(obj_id):
                return b
            if te and te.obj_type == obj_type and str(te.obj_id) == str(obj_id):
                return b
            if key in (getattr(b, "to_label", "") or "") or key in (getattr(b, "from_label", "") or ""):
                return b
        return None

    def to_dict(self) -> dict:
        return {
            "schema": "simpleworkernet.attenuation.MultiPathReport/v2",
            "wavelength_nm": self.wavelength_nm,
            "count": self.count,
            "total_db": round(self.total_db, 4),
            "total_db_min": round(self.total_db_min, 4),
            "total_db_max": round(self.total_db_max, 4),
            "total_db_avg": round(self.total_db_avg, 4),
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
        )

    def to_table(self) -> str:
        lines = [
            f"MultiPath  λ={self.wavelength_nm} nm  branches={self.count}  "
            f"calc(avg)={self.total_db_avg:.3f}  "
            f"min={self.total_db_min:.3f}  max={self.total_db_max:.3f} dB",
            "=" * 72,
        ]
        for i, b in enumerate(self.branches, 1):
            tmin = getattr(b, "total_db_min", b.total_db)
            tmax = getattr(b, "total_db_max", b.total_db)
            lines.append(
                f"--- branch {i}/{self.count}: "
                f"calc={b.total_db:.3f} min={tmin:.3f} max={tmax:.3f} dB ---"
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
            f"calc={self.total_db_avg:.3f}, "
            f"min={self.total_db_min:.3f}, max={self.total_db_max:.3f} dB)"
        )
