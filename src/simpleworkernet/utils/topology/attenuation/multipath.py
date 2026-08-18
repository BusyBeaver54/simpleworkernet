# simpleworkernet/utils/topology/attenuation/multipath.py
"""Отчёт по ветвям нелинейного CGraph."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union
from .models import PathReport, DATA_VERSION


@dataclass
class MultiPathReport:
    branches: List[PathReport] = field(default_factory=list)
    wavelength_nm: int = 1550
    dataversion: str = DATA_VERSION
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
        """Первая ветка, где объект встречается на любом конце (legacy)."""
        found = self.branches_for(obj_type, obj_id)
        return found[0] if found else None

    def resolved_direction(self) -> str:
        """upstream|downstream из query или первой ветки. Иначе ValueError."""
        d = ""
        if self.query:
            d = str(self.query.get("direction") or "")
        if not d and self.branches:
            d = str(self.branches[0].direction or "")
        d = d.strip().lower()
        if d not in ("upstream", "downstream"):
            raise ValueError(
                "MultiPathReport: не задано direction (upstream|downstream). "
                "Передайте direction при calculate() или в query."
            )
        return d

    def branches_for(
        self,
        obj_type: str,
        obj_id,
        *,
        port: Optional[int] = None,
        side: Optional[int] = None,
    ) -> List[PathReport]:
        """PathReport'ы, у которых конечная точка = заданный объект.

        Направление MultiPathReport обязательно:
          - upstream  — корень (OLT) в from_endpoint, ищем в **to_endpoint**
          - downstream — корень в to_endpoint, ищем в **from_endpoint**

        Примеры:
          branches_for("cross", uuid, port=20)     → 0..1 ветка
          branches_for("splitter", 49942)          → все порты сплиттера
          branches_for("splitter", 49942, port=2)  → один выход
          branches_for("customer", 62229)          → ветка до абонента
        """
        direction = self.resolved_direction()
        oid = str(obj_id)
        out: List[PathReport] = []
        for b in self.branches:
            ep = b.to_endpoint if direction == "upstream" else b.from_endpoint
            if ep is None:
                continue
            if str(ep.obj_type or "") != str(obj_type):
                continue
            if str(ep.obj_id) != oid:
                continue
            if port is not None:
                if ep.port is None or int(ep.port) != int(port):
                    continue
            if side is not None:
                if ep.side is None or int(ep.side) != int(side):
                    continue
            out.append(b)
        return out

    def to_dict(self) -> dict:
        return {
            "schema": "simpleworkernet.attenuation.MultiPathReport/v3",
            "dataversion": self.dataversion or DATA_VERSION,
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
            dataversion=str(d.get("dataversion") or DATA_VERSION),
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
